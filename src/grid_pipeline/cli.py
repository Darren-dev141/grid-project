"""Replay saved responses without credentials or external requests."""

import argparse
from pathlib import Path

from grid_pipeline.storage import ingest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=["eia", "pjm"])
    parser.add_argument("dataset", help="Upstream dataset name, e.g. electricity/rto/fuel-type-data")
    parser.add_argument("response", type=Path)
    parser.add_argument("--root", type=Path, default=Path("data"))
    args = parser.parse_args()
    count = ingest(args.root / "grid.duckdb", args.root, args.source,
                   args.dataset, args.response.read_bytes())
    print(f"Indexed {count} records; raw response preserved.")


if __name__ == "__main__":
    main()
