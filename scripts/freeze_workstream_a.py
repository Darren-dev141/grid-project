"""Lead-owned canonical source freeze. Never fits a model."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import duckdb

ROOT = Path(r'C:\Users\ajbig\Documents\grid-project')
OUT = ROOT / 'docs' / 'workstream-a'
SOURCES = [
    ('demand', 'data/s1-live/grid.duckdb', 'cleaned.eia_pjm_hourly_demand', 'hour_utc'),
    ('weather', 'data/s3a-verification/grid.duckdb', 'cleaned.ncei_bwi_daily_temps', 'local_date'),
]

def canonical_slice():
    result = {}
    for name, path, table, date in SOURCES:
        with duckdb.connect(str(ROOT / path), read_only=True) as con:
            cursor = con.execute(f"SELECT * FROM {table} WHERE {date} >= DATE '2025-01-01' AND {date} < DATE '2027-01-01' ORDER BY {date}")
            columns = [d[0] for d in cursor.description]
            rows = [[v.isoformat() if isinstance(v, (dt.datetime, dt.date)) else v for v in row] for row in cursor.fetchall()]
        result[name] = dict(database=path, table=table, columns=columns, rows=rows)
    return (json.dumps(result, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')

if __name__ == '__main__':
    payload = canonical_slice()
    digest = hashlib.sha256(payload).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'holdout-source.json'
    record = OUT / 'FREEZE.json'
    if record.exists():
        assert json.loads(record.read_text())['sha256'] == digest, 'Frozen source changed'
        assert target.read_bytes() == payload, 'Frozen artifact changed'
    else:
        target.write_bytes(payload)
        record.write_text(json.dumps(dict(sha256=digest, created_utc=dt.datetime.now(dt.timezone.utc).isoformat(), artifact='holdout-source.json', procedure='Read-only SELECT * from each listed source, dates >=2025-01-01 and <2027-01-01, ordered by source date. All columns including quality and provenance retained; ISO-8601 date/timestamps; JSON sorted keys, compact separators, ensure_ascii=True, allow_nan=False; UTF-8 with one final LF. SHA-256 of exact bytes.', policy='No fitting, tuning, feature selection or validation on holdout. Fixed features and hyperparameters chosen before scoring. Lagged observations from prior holdout days may be used only in sequential next-day final scoring. Training targets <=2024-12-31. Rolling-origin windows inside training years only.'), indent=2) + '\n', encoding='utf-8')
    print(digest)
    print({k: len(v['rows']) for k,v in json.loads(payload).items()})
