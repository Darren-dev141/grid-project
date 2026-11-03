"""Build S3b in fresh scratch space from existing stores and report every gap.

No network requests. Source warehouses are opened read-only and never rebuilt.
Run with the project's Python and one NEW output-directory argument.
"""
import json
from pathlib import Path
import sys

import duckdb

from grid_pipeline.storage import ingest
from grid_pipeline.warehouse import build


def main():
    repo = Path(__file__).resolve().parents[1]
    root = Path(sys.argv[1]).resolve()
    if not root.is_relative_to(repo / 'data' / 'scratch'):
        raise ValueError('output must be a new directory under data/scratch')
    root.mkdir(parents=True, exist_ok=False)
    database = root / 'grid.duckdb'
    ingest(database, root, 'eia', 'bootstrap', b'{"response":{"data":[]}}')
    sources = [repo / 'data/s1-live/grid.duckdb', repo / 'data/s3a-verification/grid.duckdb']
    with duckdb.connect(str(database)) as dest:
        for source in sources:
            with duckdb.connect(str(source), read_only=True) as origin:
                for table in ['batches', 'records']:
                    result = origin.execute(f'select * from raw.{table}')
                    columns = [col[0] for col in result.description]
                    rows = result.fetchall()
                    if rows:
                        dest.executemany(
                            f'insert or ignore into raw.{table} ({", ".join(columns)}) '
                            f'values ({", ".join("?" for _ in columns)})', rows)
    build(database, select=['+mart_day_history'], artifact_root=root)
    with duckdb.connect(str(database), read_only=True) as conn:
        def records(sql):
            result = conn.execute(sql)
            return [dict(zip([c[0] for c in result.description], row)) for row in result.fetchall()]
        report = {
            'database': str(database),
            'sources': [str(p) for p in sources],
            'coverage': records('''select count(*) as rows, count(distinct local_date) as unique_dates,
                min(local_date) as first_date, max(local_date) as last_date,
                count(*) filter (where complete) as demand_complete_days,
                count(*) filter (where tmax_f is not null and tmin_f is not null) as temperature_days,
                count(*) filter (where complete and tmax_f is not null and tmin_f is not null)
                    as complete_joined_days from marts.mart_day_history'''),
            'gaps': records('''select * from marts.mart_day_history where not complete
                or tmax_f is null or tmin_f is null order by local_date'''),
            'midnight_peaks': records('''select * from marts.mart_day_history
                where peak_hour_ending=24 order by local_date'''),
            'dst_days': records('''select * from marts.mart_day_history
                where expected_hours != 24 order by local_date'''),
        }
    output = json.dumps(report, default=str, indent=2) + '\n'
    (root / 'coverage.json').write_text(output, encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
