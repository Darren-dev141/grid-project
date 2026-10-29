"""Check that the current published snapshot is recent enough to serve."""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path


SOURCES = {'price': 'price_last_hour_utc', 'generation': 'renewable_share_last_hour_utc'}


def check(output: Path, now: datetime, *, max_lag_hours: float):
    snapshot_id = json.loads((output / 'current.json').read_text(encoding='utf-8'))['snapshot_id']
    manifest = json.loads((output / 'snapshots' / snapshot_id / 'manifest.json').read_text(encoding='utf-8'))
    sources = {}
    for source, field in SOURCES.items():
        # Older manifests lack the field; treat that like a source with no usable hours.
        if manifest.get(field) is None:
            sources[source] = {'status': 'missing'}
            continue
        end = datetime.fromisoformat(manifest[field]) + timedelta(hours=1)
        lag = (now - end).total_seconds() / 3600
        status = 'future' if lag < 0 else 'fresh' if lag <= max_lag_hours else 'stale'
        sources[source] = {'status': status,
                           'last_hour_utc': manifest[field], 'lag_hours': lag}
    return {'fresh': all(s['status'] == 'fresh' for s in sources.values()), 'sources': sources}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/powerbi'))
    parser.add_argument('--max-lag-hours', type=float, default=36)
    args = parser.parse_args(argv)
    try:
        report = check(args.output, datetime.now(timezone.utc), max_lag_hours=args.max_lag_hours)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, 'Freshness check failed: no readable current publication\n')
    print(json.dumps(report, indent=2))
    if not report['fresh']:
        parser.exit(1, 'Publication is stale or incomplete; do not serve it as current.\n')


if __name__ == '__main__':
    main()
