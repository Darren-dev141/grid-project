"""Fetch a bounded UTC interval using environment-supplied provider keys."""

import argparse
from pathlib import Path

from grid_pipeline.fetch import LoadError, fetch, utc_hour


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', choices=['eia', 'pjm'])
    parser.add_argument('--start', required=True, type=utc_hour)
    parser.add_argument('--end', required=True, type=utc_hour)
    parser.add_argument('--root', type=Path, default=Path('data'))
    parser.add_argument('--bge-node', type=int)
    parser.add_argument('--overlap-hours', type=int, default=48)
    parser.add_argument('--page-size', type=int, default=5000)
    args = parser.parse_args()
    try:
        result = fetch(args.root, args.source, args.start, args.end,
                       node=args.bge_node, overlap_hours=args.overlap_hours,
                       page_size=args.page_size)
    except (LoadError, ValueError) as exc:
        parser.exit(1, f'Load failed: {exc}\n')
    print(result)


if __name__ == '__main__':
    main()
