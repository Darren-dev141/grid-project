"""Catch the BWI NWS forecast up, ahead of the daily issuance.

Keyless. Runs nws.fetch_bwi against the s3a-verification archive root so the
forecast lands in the same database issue_stress.py reads (TEMP_DB). Two-phase
provenance: uncommitted rows are invisible to the loader.

    python scripts/refresh_nws_bwi.py            # fetch; exit 1 on failure
    python scripts/refresh_nws_bwi.py --dry-run  # print what would run
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from grid_pipeline import nws
from grid_pipeline.fetch import LoadError

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO / 'data' / 's3a-verification'


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({'status': 'dry_run', 'root': str(args.root)}, sort_keys=True))
        return 0
    try:
        result = nws.fetch_bwi(args.root)
    except LoadError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        print('NWS BWI refresh failed; check local storage and network', file=sys.stderr)
        return 1
    print(json.dumps(dict(result, status='fetched'), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
