"""Catch the NCEI BWI temperature archive up to yesterday, ahead of the daily issuance.

Keyless. This is `grid-temps` with the window derived from the archive: it starts a
few days before the newest recorded NCEI date (overlap re-captures late revisions;
first-recorded history is unaffected because the earliest batch still wins) and ends
today, exclusive. It never touches EIA and needs no key.

    python scripts/refresh_ncei.py --dry-run     # print the window and the equivalent grid-temps command
    python scripts/refresh_ncei.py               # fetch; exit 1 on failure, 0 when done or already current

The scheduled launcher runs this before scripts/issue_stress.py and continues to
issuance if it fails: stale inputs then no-call, which is the honest outcome.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import duckdb

from grid_pipeline import ncei
from grid_pipeline.fetch import LoadError

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO / 'data' / 's3a-verification'
ET = ZoneInfo('America/New_York')


def latest_recorded_date(root: Path) -> date | None:
    """Newest DATE in committed NCEI daily-summaries rows, or None for no usable archive."""
    database = Path(root) / 'grid.duckdb'
    if not database.exists():
        return None
    with duckdb.connect(str(database), read_only=True) as conn:
        try:
            value = conn.execute('''
                SELECT max(try_cast(r.payload ->> 'DATE' AS DATE))
                FROM raw.records r JOIN raw.batches b USING (source, dataset, digest)
                WHERE r.source = 'ncei' AND r.dataset = ? AND b.committed
                    AND (r.payload ->> 'STATION') = ?''',
                                 [ncei.DATASET, ncei.STATION]).fetchone()[0]
        except duckdb.CatalogException:
            return None
    return value


def plan_window(latest: date, today: date, overlap_days: int) -> tuple[date, date] | None:
    """(start, end) with end exclusive at today; None when the archive already reaches yesterday."""
    if latest >= today - timedelta(days=1):
        return None
    start = latest - timedelta(days=overlap_days)
    return start, today


def main(argv=None, *, client=None, today: date | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--overlap-days', type=int, default=3)
    parser.add_argument('--dry-run', action='store_true',
                        help='print the window and the equivalent grid-temps command; no network')
    args = parser.parse_args(argv)
    today = today or datetime.now(ET).date()
    latest = latest_recorded_date(args.root)
    if latest is None:
        print(f'no NCEI archive at {args.root}; run grid-temps with an explicit --start',
              file=sys.stderr)
        return 1
    window = plan_window(latest, today, args.overlap_days)
    if window is None:
        print(json.dumps({'status': 'current', 'latest_recorded': latest.isoformat(),
                          'today': today.isoformat()}, sort_keys=True))
        return 0
    start, end = window
    command = f'grid-temps --root {args.root} --start {start.isoformat()} --end {end.isoformat()}'
    if args.dry_run:
        print(json.dumps({'status': 'dry_run', 'latest_recorded': latest.isoformat(),
                          'start': start.isoformat(), 'end': end.isoformat(),
                          'equivalent_command': command}, sort_keys=True))
        return 0
    try:
        result = ncei.fetch(args.root, start, end, client=client)
    except LoadError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        print('NCEI refresh failed; check local storage and network', file=sys.stderr)
        return 1
    print(json.dumps(dict(result, status='fetched'), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
