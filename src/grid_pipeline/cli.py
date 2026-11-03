"""Replay saved responses without credentials or external requests."""

import argparse
import sys
from pathlib import Path



def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "ledger":
        from grid_pipeline.ledger import main as ledger_main
        ledger_main(sys.argv[2:])
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=["eia", "pjm", "nws", "ncei"])
    parser.add_argument("dataset", help="Upstream dataset name, e.g. electricity/rto/fuel-type-data")
    parser.add_argument("response", type=Path)
    parser.add_argument("--root", type=Path, default=Path("data"))
    args = parser.parse_args()
    from grid_pipeline.storage import ingest
    count = ingest(args.root / "grid.duckdb", args.root, args.source,
                   args.dataset, args.response.read_bytes())
    print(f"Indexed {count} records; raw response preserved.")


if __name__ == "__main__":
    main()
