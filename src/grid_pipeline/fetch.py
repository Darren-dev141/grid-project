"""Bounded EIA-930 API loads with durable checkpoints."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time

import duckdb
import httpx

from grid_pipeline.storage import ingest, land


class LoadError(RuntimeError):
    """Safe diagnostic: never include authenticated URLs or response bodies."""


def utc_hour(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError('timestamps must include a UTC offset, e.g. 2026-10-01T00:00Z')
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError('timestamps must align to an hour')
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Dataset:
    route: str
    facets: tuple[tuple[str, str], ...]
    stream: str
    scope: tuple[tuple[str, str], ...]
    sort: tuple[str, ...]


DATASETS = {
    'fuel-mix': Dataset('electricity/rto/fuel-type-data', (('respondent', 'PJM'),),
                        'eia:electricity/rto/fuel-type-data:PJM', (('respondent', 'PJM'),),
                        ('period', 'fueltype')),
    'pjm-demand': Dataset('electricity/rto/region-data', (('respondent', 'PJM'), ('type', 'D')),
                          'eia:electricity/rto/region-data:PJM:D', (('respondent', 'PJM'), ('type', 'D')),
                          ('period',)),
    'bge-demand': Dataset('electricity/rto/region-sub-ba-data', (('parent', 'PJM'), ('subba', 'BC')),
                         'eia:electricity/rto/region-sub-ba-data:PJM:BC', (('parent', 'PJM'), ('subba', 'BC')),
                         ('period',)),
}


def request_page(client, url, params, headers, key, sleep):
    for attempt in range(4):
        try:
            response = client.get(url, params=params, headers=headers, follow_redirects=False)
        except httpx.RequestError:
            if attempt == 3:
                raise LoadError('network request failed after 4 attempts') from None
            sleep(2 ** attempt)
            continue
        if response.status_code == 429 or 500 <= response.status_code < 600:
            if attempt == 3:
                raise LoadError(f'upstream HTTP {response.status_code} after 4 attempts')
            delay = 2 ** attempt
            if 'retry-after' in response.headers:
                try:
                    delay = max(delay, int(response.headers['retry-after']))
                except ValueError:
                    raise LoadError('upstream Retry-After requires a later retry') from None
                if delay > 60:
                    raise LoadError('upstream requested a retry more than 60 seconds later')
            sleep(delay)
            continue
        if response.status_code != 200:
            raise LoadError(f'upstream HTTP {response.status_code}; response not logged')
        if key.encode() in response.content:
            raise LoadError('upstream response contains credential material; refusing to persist it')
        return response.content
    raise AssertionError('unreachable')


def validate_scope(rows, spec, start, end):
    """Refuse an upstream response outside requested hours or dataset facets."""
    try:
        for row in rows:
            hour = datetime.strptime(row['period'], '%Y-%m-%dT%H').replace(tzinfo=timezone.utc)
            if not start <= hour < end or hour.minute or hour.second or any(row[key] != value for key, value in spec.scope):
                raise ValueError('out of scope')
    except (KeyError, TypeError, ValueError):
        raise LoadError('upstream rows violate the requested UTC interval or geography; checkpoint unchanged') from None


def fetch(root: Path, source: str, start: datetime, end: datetime, *,
          overlap_hours: int = 48, page_size: int = 5000, client=None,
          sleep=time.sleep, max_days: int = 31) -> dict:
    """Fetch a named EIA-930 dataset in [start,end), resuming its checkpoint."""
    if source not in DATASETS:
        raise ValueError(f'dataset must be one of {", ".join(DATASETS)}')
    for value in (start, end):
        if utc_hour(value.isoformat()) != value:
            raise ValueError('expected UTC hour')
    if not start < end or max_days < 1 or end - start > timedelta(days=max_days):
        raise ValueError(f'request interval must be positive and at most {max_days} days')
    if not 0 <= overlap_hours <= 744 or not 1 <= page_size <= 5000:
        raise ValueError('invalid overlap or page size')
    key = os.environ.get('EIA_API_KEY')
    if not key:
        raise LoadError('missing EIA_API_KEY environment variable')
    spec = DATASETS[source]
    provider, dataset, stream = 'eia', spec.route, spec.stream
    root.mkdir(parents=True, exist_ok=True)
    database = root / 'grid.duckdb'
    with duckdb.connect(str(database)) as conn:
        conn.execute("SET TimeZone='UTC'")
        conn.execute('CREATE SCHEMA IF NOT EXISTS ops')
        conn.execute('''CREATE TABLE IF NOT EXISTS ops.checkpoints (
            stream VARCHAR PRIMARY KEY, initial_start TIMESTAMPTZ,
            completed_until TIMESTAMPTZ, updated_at TIMESTAMPTZ)''')
        checkpoint = conn.execute('SELECT initial_start, completed_until FROM ops.checkpoints WHERE stream=?', [stream]).fetchone()
        effective_start = start
        if checkpoint:
            initial, completed = checkpoint
            if start < initial or start > completed:
                raise LoadError('interval would backfill before the stream or skip a gap; use a separate root')
            if end <= completed:
                return {'status': 'already_complete', 'pages': 0, 'indexed': 0}
            effective_start = max(start, completed - timedelta(hours=overlap_hours))
        owned_client = client is None
        if owned_client:
            client = httpx.Client(timeout=30)
        try:
            pages = download(root, spec, effective_start, end, page_size, client, key, sleep)
        finally:
            if owned_client:
                client.close()
        indexed = sum(ingest(database, root, provider, dataset, path.read_bytes(), committed=False) for path in pages)
        conn.execute('BEGIN TRANSACTION')
        try:
            conn.executemany('''UPDATE raw.batches SET committed=TRUE, observed_at=current_timestamp
                WHERE source=? AND dataset=? AND digest=?''',
                [(provider, dataset, path.stem) for path in pages])
            conn.execute('''INSERT INTO ops.checkpoints VALUES (?, ?, ?, current_timestamp)
                ON CONFLICT(stream) DO UPDATE SET completed_until=excluded.completed_until,
                updated_at=excluded.updated_at''', [stream, start, end])
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise
    return {'status': 'complete', 'pages': len(pages), 'indexed': indexed,
            'start': effective_start.isoformat(), 'end': end.isoformat()}


def download(root, spec, start, end, page_size, client, key, sleep):
    offset, total, pages, seen = 0, None, [], set()
    last_hour = end - timedelta(hours=1)
    for _ in range(10000):
        url = f'https://api.eia.gov/v2/{spec.route}/data/'
        params = {'api_key': key, 'frequency': 'hourly', 'data[0]': 'value',
                  'start': start.strftime('%Y-%m-%dT%H'), 'end': last_hour.strftime('%Y-%m-%dT%H'),
                  'offset': offset, 'length': page_size}
        params.update({f'facets[{name}][]': value for name, value in spec.facets})
        for index, column in enumerate(spec.sort):
            params.update({f'sort[{index}][column]': column, f'sort[{index}][direction]': 'asc'})
        body = request_page(client, url, params, {}, key, sleep)
        path = land(root, 'eia', body)
        try:
            envelope = json.loads(body)['response']
            rows = envelope['data']
            raw_total = envelope['total']
            current_total = int(raw_total)
            if str(current_total) != str(raw_total):
                raise ValueError('noninteger total')
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ValueError('invalid rows')
        except (ValueError, KeyError, TypeError):
            raise LoadError('invalid upstream page shape; raw response retained') from None
        if total is None:
            total = current_total
        if total <= 0:
            raise LoadError('upstream returned no records; checkpoint unchanged')
        if current_total != total or not rows or len(rows) > page_size or offset + len(rows) > total:
            raise LoadError('upstream pagination inconsistent; checkpoint unchanged')
        validate_scope(rows, spec, start, end)
        if path.stem in seen:
            raise LoadError('upstream repeated a page; checkpoint unchanged')
        seen.add(path.stem)
        pages.append(path)
        offset += len(rows)
        if offset == total:
            return pages
    raise LoadError('page limit exceeded; checkpoint unchanged')
