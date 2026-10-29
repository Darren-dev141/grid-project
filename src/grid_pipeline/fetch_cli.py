"""Fetch or backfill bounded UTC intervals from EIA-930."""

import argparse
from datetime import timedelta
from pathlib import Path

import httpx

from grid_pipeline.fetch import DATASETS, LoadError, fetch, utc_hour


def backfill(root: Path, dataset: str, start, end, *, window_days: int = 180,
             client=None, sleep=None, page_size: int = 5000):
    if dataset not in DATASETS:
        raise ValueError(f'dataset must be one of {", ".join(DATASETS)}')
    if not 1 <= window_days <= 366:
        raise ValueError('window-days must be between 1 and 366')
    if not start < end:
        raise ValueError('backfill interval must be positive')
    owned_client = client is None
    if owned_client:
        client = httpx.Client(timeout=30)
    results = []
    cursor = start
    try:
        while cursor < end:
            window_end = min(cursor + timedelta(days=window_days), end)
            options = {'overlap_hours': 0, 'page_size': page_size, 'client': client,
                       'max_days': window_days}
            if sleep is not None:
                options['sleep'] = sleep
            results.append(fetch(root, dataset, cursor, window_end, **options))
            cursor = window_end
    finally:
        if owned_client:
            client.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', choices=tuple(DATASETS))
    parser.add_argument('--start', required=True, type=utc_hour)
    parser.add_argument('--end', required=True, type=utc_hour)
    parser.add_argument('--root', type=Path, default=Path('data'))
    parser.add_argument('--overlap-hours', type=int, default=48)
    parser.add_argument('--page-size', type=int, default=5000)
    args = parser.parse_args()
    try:
        result = fetch(args.root, args.dataset, args.start, args.end,
                       overlap_hours=args.overlap_hours, page_size=args.page_size)
    except (LoadError, ValueError) as exc:
        parser.exit(1, f'Load failed: {exc}\n')
    print(result)


def backfill_main():
    parser = argparse.ArgumentParser(description='Resumable history backfill from EIA-930.')
    parser.add_argument('dataset', choices=tuple(DATASETS))
    parser.add_argument('--start', required=True, type=utc_hour)
    parser.add_argument('--end', required=True, type=utc_hour)
    parser.add_argument('--window-days', type=int, default=180)
    parser.add_argument('--root', type=Path, default=Path('data'))
    args = parser.parse_args()
    try:
        result = backfill(args.root, args.dataset, args.start, args.end,
                          window_days=args.window_days)
    except (LoadError, ValueError) as exc:
        parser.exit(1, f'Load failed: {exc}\n')
    print(result)


if __name__ == '__main__':
    main()
