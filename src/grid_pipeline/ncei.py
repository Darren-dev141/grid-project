"""Bounded, keyless BWI daily temperature loads from NOAA NCEI.

Intervals include start and exclude end. Explicit overlapping reloads capture
revisions; no checkpoint skips recently missing or revised observations.
"""

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import time

import duckdb
import httpx

from grid_pipeline.fetch import LoadError
from grid_pipeline.storage import ingest, land

BASE = 'https://www.ncei.noaa.gov/access/services/data/v1'
STATION = 'USW00093721'
DATASET = 'daily-summaries'


def records_from_payload(dataset, payload):
    """Reject foreign scope and bad dates before indexing; dbt flags bad values."""
    if dataset != DATASET:
        raise ValueError('unsupported NCEI dataset')
    if not isinstance(payload, list):
        raise ValueError('expected NCEI daily record list')
    seen = set()
    for row in payload:
        if not isinstance(row, dict) or row.get('STATION') != STATION:
            raise ValueError('invalid NCEI BWI station')
        day = date.fromisoformat(row['DATE'])
        if day.isoformat() != row['DATE'] or day in seen:
            raise ValueError('invalid NCEI date or duplicate day')
        seen.add(day)
    return payload


def fetch(root: Path, start: date, end: date, *, client=None, sleep=time.sleep):
    """Land every HTTP body, validate scope, then make a single batch visible."""
    if not 0 < (end - start).days <= 366:
        raise LoadError('NCEI interval must contain 1 to 366 days (end exclusive)')
    if client is None:
        with httpx.Client() as owned:
            return fetch(root, start, end, client=owned, sleep=sleep)
    root = Path(root)
    params = {'dataset': DATASET, 'stations': STATION,
              'startDate': start.isoformat(), 'endDate': (end - timedelta(days=1)).isoformat(),
              'dataTypes': 'TMAX,TMIN', 'units': 'standard',
              'includeAttributes': 'true', 'format': 'json'}
    for attempt in range(3):
        try:
            response = client.get(BASE, params=params, timeout=30, follow_redirects=False)
        except httpx.RequestError:
            if attempt == 2:
                raise LoadError('NCEI network request failed after 3 attempts') from None
        else:
            path = land(root, 'ncei', response.content)
            if response.status_code == 200:
                break
            if response.status_code != 429 and not 500 <= response.status_code < 600:
                raise LoadError(f'NCEI HTTP {response.status_code}')
            if 'retry-after' in response.headers:
                raise LoadError('NCEI requested a later retry (Retry-After)')
            if attempt == 2:
                raise LoadError(f'NCEI HTTP {response.status_code} after 3 attempts')
        sleep(2 ** attempt)
    body = response.content
    try:
        rows = records_from_payload(DATASET, json.loads(body))
        if any(not start <= date.fromisoformat(row['DATE']) < end for row in rows):
            raise ValueError('out-of-interval NCEI date')
    except (ValueError, KeyError, TypeError):
        raise LoadError('invalid NCEI daily response; raw body retained') from None
    database = root / 'grid.duckdb'
    indexed = ingest(database, root, 'ncei', DATASET, body, committed=False)
    # A -> B -> A revisions must select the most recently observed payload even
    # when A's bytes already exist. loaded_at remains the first indexing time.
    with duckdb.connect(str(database)) as conn:
        conn.execute("""UPDATE raw.batches SET committed=TRUE, observed_at=current_timestamp
                        WHERE source='ncei' AND dataset=? AND digest=?""", [DATASET, path.stem])
    return {'indexed': indexed, 'days': len(rows), 'station': STATION,
            'start': start.isoformat(), 'end': end.isoformat(), 'digest': path.stem}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data'))
    parser.add_argument('--start', type=date.fromisoformat, required=True)
    parser.add_argument('--end', type=date.fromisoformat, required=True)
    args = parser.parse_args(argv)
    try:
        result = fetch(args.root, args.start, args.end)
    except LoadError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        print('NCEI load failed; check local storage and configuration', file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
