"""Report blocked observed-weather hindcast coverage from a verified mart.

Usage: python scripts/backtest_stress.py path/to/verified.duckdb
This opens the database read-only. It does not produce forecast performance metrics.
"""
import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('verified_mart', help='path to an independently verified DuckDB mart')
    args = parser.parse_args()
    import duckdb

    connection = duckdb.connect(args.verified_mart, read_only=True)
    try:
        rows = connection.execute('''
            select year(local_date) as target_year, count(*) as complete_days
            from marts.mart_day_history
            where local_date >= date '2019-01-01' and local_date < date '2027-01-01'
              and complete and tmax_f is not null and tmin_f is not null
            group by 1 order by 1
        ''').fetchall()
    finally:
        connection.close()
    counts = dict(rows)
    print('Observed-weather hindcast coverage only; not forecast validation.')
    print('Forecast metrics blocked: v1 calculation methods and issue-time availability are unresolved.')
    print('Year | Complete days with observed temperatures | Result')
    for year in range(2019, 2027):
        print(f'{year} | {counts.get(year, 0)} | not run')


if __name__ == '__main__':
    main()
