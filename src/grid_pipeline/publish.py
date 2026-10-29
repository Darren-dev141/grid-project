"""Validate an isolated database snapshot and publish a Power BI CSV atomically."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from zoneinfo import ZoneInfo

import duckdb


class PublishError(RuntimeError):
    pass


def report_rows(conn):
    result = conn.execute('SELECT * FROM serving.grid_hourly ORDER BY hour_utc')
    columns = [column[0] for column in result.description]
    rows = [dict(zip(columns, values)) for values in result.fetchall()]
    if not rows or not any(row['price_usd_per_mwh'] is not None for row in rows):
        raise PublishError('no price observations available for this node')
    if not any(row['reported_generation_mwh'] is not None for row in rows):
        raise PublishError('no regional generation observations available')
    local_zone = ZoneInfo('America/New_York')
    for row in rows:
        hour = row['hour_utc'].replace(tzinfo=timezone.utc)
        local = hour.astimezone(local_zone)
        row['hour_utc'] = hour.isoformat()
        row['hour_local'] = local.isoformat()
        row['local_date'] = local.date().isoformat()
        row['local_hour'] = local.hour
        row['local_weekday'] = local.strftime('%A')
        row['utc_offset_minutes'] = int(local.utcoffset().total_seconds() / 60)
        for key in ('price_loaded_at', 'generation_loaded_at'):
            if row[key] is not None:
                row[key] = row[key].astimezone(timezone.utc).isoformat()
    return rows


def last_hour_with(rows, column):
    """Latest hour where column has a value, for freshness checks; rows sorted by hour."""
    return next((row['hour_utc'] for row in reversed(rows) if row[column] is not None), None)


def publish(database: Path, output: Path, project: Path, node: int, *, data_kind: str):
    if not database.is_file():
        raise PublishError('database does not exist')
    if node <= 0 or data_kind not in {'synthetic', 'public_unverified'}:
        raise PublishError('positive node and explicit data kind required')
    if not (project / 'dbt_project.yml').is_file():
        raise PublishError('dbt project not found; pass --project')
    output.mkdir(parents=True, exist_ok=True)
    snapshot_id = uuid.uuid4().hex
    snapshot = output / 'snapshots' / snapshot_id
    snapshot.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='grid-publish-') as temporary:
        copy = Path(temporary) / 'warehouse.duckdb'
        # DuckDB's logical copy respects its Windows file locks and includes WAL data.
        # Callers must serialize jobs within this process, as with ingestion.
        with duckdb.connect(str(database)) as conn:
            catalog = conn.execute('SELECT current_database()').fetchone()[0]
            quoted_catalog = '"' + catalog.replace('"', '""') + '"'
            quoted_path = "'" + str(copy).replace("'", "''") + "'"
            conn.execute(f'ATTACH {quoted_path} AS export_snapshot')
            conn.execute(f'COPY FROM DATABASE {quoted_catalog} TO export_snapshot')
            conn.execute('DETACH export_snapshot')
        env = os.environ.copy()
        env['GRID_DATABASE'] = str(copy)
        env['DBT_SEND_ANONYMOUS_USAGE_STATS'] = 'false'
        executable = Path(sys.executable).parent / ('dbt.exe' if os.name == 'nt' else 'dbt')
        try:
            result = subprocess.run([
                str(executable), 'build', '--project-dir', str(project.resolve()),
                '--profiles-dir', str(project.resolve()),
                '--target-path', str((snapshot / 'dbt').resolve()),
                '--log-path', str((snapshot / 'logs').resolve()),
                '--vars', json.dumps({'bge_pnode_id': node}),
            ], env=env, capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            raise PublishError('dbt could not finish; previous publication preserved') from None
        (snapshot / 'validation.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise PublishError(f'dbt validation failed; see {snapshot / "validation.txt"}')
        with duckdb.connect(str(copy), read_only=True) as conn:
            conn.execute("SET TimeZone='UTC'")
            rows = report_rows(conn)
    csv_path = snapshot / 'grid_hourly.csv'
    with csv_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        'schema_version': 1, 'snapshot_id': snapshot_id,
        'data_kind': data_kind, 'purpose': 'historical analysis; not a charging recommendation',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'bge_node_id': node, 'rows': len(rows),
        'first_hour_utc': rows[0]['hour_utc'], 'last_hour_utc': rows[-1]['hour_utc'],
        'price_hours': sum(row['price_usd_per_mwh'] is not None for row in rows),
        'renewable_share_hours': sum(row['renewable_share'] is not None for row in rows),
        'price_last_hour_utc': last_hour_with(rows, 'price_usd_per_mwh'),
        'renewable_share_last_hour_utc': last_hour_with(rows, 'renewable_share'),
        'generation_geography': 'PJM balancing authority',
        'csv_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    }
    (snapshot / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    pointer = output / f'.current-{snapshot_id}.json'
    pointer.write_text(json.dumps({'snapshot_id': snapshot_id}), encoding='utf-8')
    os.replace(pointer, output / 'current.json')
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=Path('data/grid.duckdb'))
    parser.add_argument('--output', type=Path, default=Path('data/powerbi'))
    parser.add_argument('--project', type=Path, default=Path('dbt'))
    parser.add_argument('--bge-node', type=int, required=True)
    parser.add_argument('--data-kind', choices=['synthetic', 'public_unverified'], required=True)
    args = parser.parse_args()
    try:
        snapshot = publish(args.database, args.output, args.project, args.bge_node,
                           data_kind=args.data_kind)
    except PublishError as exc:
        parser.exit(1, f'Publication failed: {exc}\n')
    print(f'Published validated historical export: {snapshot}')


if __name__ == '__main__':
    main()
