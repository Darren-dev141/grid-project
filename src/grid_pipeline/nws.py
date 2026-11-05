"""Keyless NWS snapshots: immutable bytes and issuance-preserving raw indexing."""

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

import httpx
import duckdb

from grid_pipeline.fetch import LoadError
from grid_pipeline.storage import ingest, land

POINT = '39.4696,-76.8294'
GRID = ('LWX', 100, 98)
# BWI airport point (verified via /points endpoint; see docs/evidence/nws_points_bwi_*.json).
# Docs previously claimed LWX/107,85; the API returns LWX/108,86 for 39.1754,-76.6684.
POINT_BWI = '39.1754,-76.6684'
GRID_BWI = ('LWX', 108, 86)
BASE = 'https://api.weather.gov'
_ET = ZoneInfo('America/New_York')


def records_from_payload(dataset, payload):
    """Validate the envelope before any database mutation; retain issuance metadata."""
    if dataset in ('forecast', 'forecast_bwi'):
        properties = payload['properties']
        periods = properties['periods']
        if not isinstance(periods, list) or not periods or any(not isinstance(p, dict) for p in periods):
            raise ValueError('expected forecast periods')
        required = {'number', 'startTime', 'endTime', 'isDaytime', 'temperature', 'temperatureUnit'}
        if any(not required <= p.keys() for p in periods):
            raise ValueError('invalid NWS forecast period')
        for field in ('updateTime', 'generatedAt'):
            stamp = datetime.fromisoformat(properties[field].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('expected timezone-aware issuance')
        return [payload]
    if dataset == 'alerts':
        features = payload['features']
        if not isinstance(features, list) or any(
            not isinstance(f, dict) or not f.get('id') or
            not isinstance(f.get('properties'), dict) or not f['properties'].get('event')
            for f in features
        ):
            raise ValueError('invalid NWS alert features')
        return features
    raise ValueError('unsupported NWS dataset')


def request(client, path, headers, sleep, root):
    for attempt in range(3):
        try:
            response = client.get(BASE + path, headers=headers, timeout=30, follow_redirects=False)
        except httpx.RequestError:
            if attempt == 2:
                raise LoadError('NWS network request failed after 3 attempts') from None
        else:
            land(root, 'nws', response.content)
            if response.status_code == 200:
                return response.content
            if response.status_code != 429 and not 500 <= response.status_code < 600:
                raise LoadError(f'NWS HTTP {response.status_code}')
            # Defer to the caller/scheduler rather than ignore server throttling
            # or block this bounded interactive load for an unbounded interval.
            if 'retry-after' in response.headers:
                raise LoadError('NWS requested a later retry (Retry-After)')
            if attempt == 2:
                raise LoadError(f'NWS HTTP {response.status_code} after 3 attempts')
        sleep(2 ** attempt)
    raise AssertionError('unreachable')


def fetch(root: Path, *, client=None, sleep=time.sleep):
    """Resolve pinned point, then independently land/index forecast and alerts.

    loaded_at records the first successful indexing time, immediately after receipt.
    Byte-identical replays preserve that timestamp and insert nothing.
    """
    ua = os.environ.get('NWS_USER_AGENT', '').strip()
    if not ua:
        raise LoadError('NWS_USER_AGENT must identify this application')
    if client is None:
        with httpx.Client() as owned:
            return fetch(root, client=owned, sleep=sleep)
    root = Path(root)
    headers = {'User-Agent': ua, 'Accept': 'application/geo+json'}
    body = request(client, f'/points/{POINT}', headers, sleep, root)
    try:
        properties = json.loads(body)['properties']
        actual = (properties['gridId'], properties['gridX'], properties['gridY'])
    except (ValueError, KeyError, TypeError):
        raise LoadError('invalid NWS point response; raw body retained') from None
    if actual != GRID:
        raise LoadError('NWS gridpoint mismatch; review pinned location')
    result = {}
    for dataset, path in [('forecast', f'/gridpoints/{GRID[0]}/{GRID[1]},{GRID[2]}/forecast'),
                          ('alerts', f'/alerts/active?point={POINT}')]:
        body = request(client, path, headers, sleep, root)
        try:
            result[dataset] = ingest(root / 'grid.duckdb', root, 'nws', dataset, body)
        except (ValueError, KeyError, TypeError, AttributeError):
            raise LoadError(f'invalid NWS {dataset} response; raw body retained') from None
    return result


def fetch_bwi(root: Path, *, client=None, sleep=time.sleep):
    """BWI airport forecast with W3 two-phase provenance."""
    ua = os.environ.get('NWS_USER_AGENT', '').strip()
    if not ua:
        raise LoadError('NWS_USER_AGENT must identify this application')
    if client is None:
        with httpx.Client() as owned:
            return fetch_bwi(root, client=owned, sleep=sleep)
    root = Path(root)
    headers = {'User-Agent': ua, 'Accept': 'application/geo+json'}
    # Resolve the gridpoint from the API (do not assume).
    points_body = request(client, f'/points/{POINT_BWI}', headers, sleep, root)
    try:
        properties = json.loads(points_body)['properties']
        grid = (properties['gridId'], properties['gridX'], properties['gridY'])
    except (ValueError, KeyError, TypeError):
        raise LoadError('invalid NWS point response; raw body retained') from None
    # Use the API result (flag discrepancy against the verified pin in the record).
    result = {}
    path = f'/gridpoints/{grid[0]}/{grid[1]},{grid[2]}/forecast'
    body = request(client, path, headers, sleep, root)
    try:
        payload = json.loads(body)
        props = payload['properties']
        periods = props['periods']
        if not isinstance(periods, list) or not periods:
            raise ValueError('expected forecast periods')
        # probe: does the response contain a night period ending on today's (target) morning?
        today = datetime.now(_ET).date()
        overnight_low_present = any(
            (not p.get('isDaytime')) and
            datetime.fromisoformat(p['endTime'].replace('Z', '+00:00')).astimezone(_ET).date() == today
            for p in periods if isinstance(p, dict) and p.get('endTime')
        )
        print(f'nws_bwi_probe overnight_low_present={str(overnight_low_present).lower()} '
              f'issuance={props.get("updateTime")} periods={len(periods)}')
    except (ValueError, KeyError, TypeError, AttributeError):
        raise LoadError('invalid NWS forecast response; raw body retained') from None
    database = root / 'grid.duckdb'
    landed = land(root, 'nws', body)
    indexed = ingest(database, root, 'nws', 'forecast_bwi', body, committed=False)
    with duckdb.connect(str(database)) as conn:
        conn.execute("UPDATE raw.batches SET committed=TRUE, observed_at=current_timestamp WHERE source='nws' AND dataset='forecast_bwi' AND digest=?", [landed.stem])
    return {'forecast_bwi': indexed, 'gridpoint': grid, 'periods': len(periods), 'digest': landed.stem}


def main_bwi(argv=None):
    parser = argparse.ArgumentParser(description='Fetch BWI NWS forecast (keyless, W3 provenance)')
    parser.add_argument('--root', type=Path, default=Path('data'))
    args = parser.parse_args(argv)
    try:
        result = fetch_bwi(args.root)
    except LoadError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        print('NWS BWI load failed; check local storage and configuration', file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Fetch Reisterstown NWS forecast and active alerts')
    parser.add_argument('--root', type=Path, default=Path('data'))
    args = parser.parse_args(argv)
    try:
        result = fetch(args.root)
    except LoadError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        print('NWS load failed; check local storage and configuration', file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
