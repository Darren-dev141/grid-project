from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/workstream-a'
EXPECTED = 'b48baaa51dc680cdcc7704f96aee954afbcd6d5433cb85a19d6fda51265679b5'
TZ = ZoneInfo('America/New_York')
UTC = timezone.utc
FEATURES = ['year', 'month', 'dayofweek', 'dayofyear', 'weekend', 'peak_lag_1', 'peak_lag_2', 'peak_lag_7', 'peak_lag_14', 'high_f_lag_7', 'low_f_lag_7']
PARAMS = dict(loss='squared_error', learning_rate=0.1, max_iter=100, max_leaf_nodes=31, l2_regularization=0, random_state=0, early_stopping=False)
LIMITATION = ('Retrospective observed-demand evaluation at the end of the prior local day. No publication-time archive is available; the seven-day weather delay is an assumption, not a historical as-of guarantee. Latest revised source values and quality may differ from information available then. Demand quality is recomputed within each local day to avoid the source flag looking into the next day; boundary spike checks are unavailable. A one-hour MWh value is treated as average MW.')
SOURCES = {'demand': ('data/s1-live/grid.duckdb', 'cleaned.eia_pjm_hourly_demand', 'hour_utc'), 'weather': ('data/s3a-verification/grid.duckdb', 'cleaned.ncei_bwi_daily_temps', 'local_date')}


def dependencies():
    modules = {}
    errors = []
    for name in ('duckdb', 'numpy', 'sklearn'):
        try:
            modules[name] = __import__(name)
        except Exception as exc:
            errors.append(f'{name}: {type(exc).__name__}: {exc}')
    if errors:
        print('Dependency import errors:\n' + '\n'.join(errors), file=sys.stderr)
    if 'duckdb' not in modules:
        raise RuntimeError('duckdb is required for every stage')
    return modules


def iso(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def read_source(duckdb, key, start, end):
    db, table, col = SOURCES[key]
    con = duckdb.connect(str(ROOT / db), read_only=True)
    try:
        result = con.execute(f'SELECT * FROM {table} WHERE {col} >= ? AND {col} < ? ORDER BY {col}', [start, end])
        columns = [item[0] for item in result.description]
        rows = [[iso(v) for v in row] for row in result.fetchall()]
        return dict(columns=columns, database=db, rows=rows, table=table)
    finally:
        con.close()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')


def frozen_and_current(duckdb):
    freeze = json.loads((OUT / 'FREEZE.json').read_text(encoding='utf-8'))
    raw = (OUT / 'holdout-source.json').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED or freeze.get('sha256') != EXPECTED or freeze.get('artifact') != 'holdout-source.json':
        raise ValueError('Frozen artifact or manifest hash mismatch')
    frozen = json.loads(raw)
    current = {key: read_source(duckdb, key, '2025-01-01', '2027-01-01') for key in SOURCES}
    if hashlib.sha256(canonical(current)).hexdigest() != EXPECTED:
        raise ValueError('Current holdout source differs from frozen all-column artifact')
    return frozen


def records(source):
    return (dict(zip(source['columns'], row)) for row in source['rows'])


def expected_hours(day):
    start = datetime.combine(day, time.min, TZ).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, TZ).astimezone(UTC)
    return [start + timedelta(hours=i) for i in range(int((end - start).total_seconds() // 3600))]


def daily(demand, weather):
    hours = defaultdict(list)
    for row in records(demand):
        stamp = datetime.fromisoformat(row['hour_utc'])
        stamp = stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)
        hours[stamp.astimezone(TZ).date()].append((stamp, row['demand_mwh']))
    peaks, counts = {}, Counter()
    for day, items in hours.items():
        stamps = [x[0] for x in items]
        if len(stamps) != len(set(stamps)) or set(stamps) != set(expected_hours(day)):
            counts['incomplete_or_duplicate_demand_days'] += 1
            continue
        values = [v for _, v in sorted(items)]
        if any(v is None or not math.isfinite(v) or v < 0 or v > 200000 for v in values):
            counts['invalid_demand_days'] += 1
            continue
        # Recompute the source's neighbor spike rule only when both neighbors
        # are in this local day, so a prior-day feature never reads target hours.
        if any(values[i] > 1.10 * max(values[i-1], values[i+1]) or values[i] < 0.85 * min(values[i-1], values[i+1]) for i in range(1, len(values)-1)):
            counts['spike_demand_days'] += 1
            continue
        peaks[day] = max(values)
    temps = {}
    seen = set()
    for row in records(weather):
        day = date.fromisoformat(row['local_date'])
        if day in seen:
            raise ValueError(f'Duplicate weather date {day}')
        seen.add(day)
        hi, lo = row['high_f'], row['low_f']
        if row['quality'] == 'ok' and hi is not None and lo is not None and math.isfinite(hi) and math.isfinite(lo):
            temps[day] = (hi, lo)
        else:
            counts['invalid_weather_days'] += 1
    counts['valid_demand_days'] = len(peaks)
    counts['valid_weather_days'] = len(temps)
    return peaks, temps, dict(counts)


def cohort(peaks, temps, start, end):
    rows, excluded = [], defaultdict(list)
    day = start
    while day <= end:
        reasons = []
        if day not in peaks:
            reasons.append('target_demand')
        lags = [day - timedelta(days=n) for n in (1, 2, 7, 14)]
        assert all(d < day for d in lags)
        if any(d not in peaks for d in lags):
            reasons.append('demand_lag')
        if day - timedelta(days=7) not in temps:
            reasons.append('weather_lag_7')
        if reasons:
            for reason in reasons:
                excluded[reason].append(day.isoformat())
        else:
            x = [day.year, day.month, day.weekday(), day.timetuple().tm_yday, int(day.weekday() >= 5)] + [peaks[d] for d in lags] + list(temps[day - timedelta(days=7)])
            rows.append((day, x, peaks[day]))
        day += timedelta(days=1)
    return rows, {'requested_start': start.isoformat(), 'requested_end': end.isoformat(), 'included_count': len(rows), 'included_start': rows[0][0].isoformat() if rows else None, 'included_end': rows[-1][0].isoformat() if rows else None, 'excluded_count': (end-start).days + 1 - len(rows), 'excluded_by_reason_dates': dict(excluded)}


def metrics(rows, pred):
    if not rows or len(rows) != len(pred) or not all(math.isfinite(float(p)) for p in pred):
        raise ValueError('Empty cohort, mismatched cohort, or non-finite predictions')
    errors = [float(p) - r[2] for r, p in zip(rows, pred)]
    return {'n': len(rows), 'mae_mw': sum(abs(x) for x in errors)/len(errors), 'rmse_mw': math.sqrt(sum(x*x for x in errors)/len(errors)), 'bias_mw': sum(errors)/len(errors)}


def baseline_predictions(rows):
    return {'persistence': [r[1][5] for r in rows], 'seasonal': [r[1][7] for r in rows]}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(path, rows):
    if not rows:
        raise ValueError(f'No rows for {path}')
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summary_md(title, summary, metadata):
    return '# ' + title + '\n\n' + LIMITATION + '\n\n```json\n' + json.dumps({'metrics': summary, 'metadata': metadata}, indent=2, allow_nan=False) + '\n```\n'


def training_sources(duckdb):
    return {key: read_source(duckdb, key, '1900-01-01', '2025-01-01') for key in SOURCES}


def prepare(duckdb, frozen):
    source = training_sources(duckdb)
    train_peaks, train_temps, quality = daily(source['demand'], source['weather'])
    # Holdout is constructed only from the frozen bytes, never the live query.
    merged = {}
    for key in SOURCES:
        if source[key]['columns'] != frozen[key]['columns']:
            raise ValueError(f'{key} columns differ from freeze')
        merged[key] = dict(source[key], rows=source[key]['rows'] + frozen[key]['rows'])
    all_peaks, all_temps, all_quality = daily(merged['demand'], merged['weather'])
    return train_peaks, train_temps, quality, all_peaks, all_temps, all_quality


def train_start(peaks):
    if not peaks:
        raise ValueError('No valid training demand days')
    return min(peaks)


def fit_predict(modules, train, evaluation):
    if 'numpy' not in modules or 'sklearn' not in modules:
        raise RuntimeError('numpy and sklearn are required for boosting; see import errors above')
    from sklearn.ensemble import HistGradientBoostingRegressor
    if not train or not evaluation:
        raise ValueError('Empty training or evaluation cohort')
    model = HistGradientBoostingRegressor(**PARAMS)
    model.fit([r[1] for r in train], [r[2] for r in train])
    return list(model.predict([r[1] for r in evaluation]))


def stage_baselines(modules, frozen):
    tp, tt, q, ap, at, aq = prepare(modules['duckdb'], frozen)
    train, train_meta = cohort(tp, tt, train_start(tp), date(2024, 12, 31))
    evaluation, eval_meta = cohort(ap, at, date(2025, 1, 1), date(2026, 12, 31))
    pred = baseline_predictions(evaluation)
    result = {'freeze_sha256': EXPECTED, 'features': FEATURES, 'training_cohort': train_meta, 'evaluation_cohort': eval_meta, 'training_quality': q, 'combined_quality': aq, 'metrics': {k: metrics(evaluation, v) for k, v in pred.items()}, 'limitation': LIMITATION}
    write_json(OUT / 'baselines.json', result)


def stage_boosting(modules, frozen):
    baseline_path = OUT / 'baselines.json'
    if not baseline_path.exists():
        raise ValueError('Run baselines first')
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    tp, tt, q, ap, at, aq = prepare(modules['duckdb'], frozen)
    train, tm = cohort(tp, tt, train_start(tp), date(2024, 12, 31))
    evaluation, em = cohort(ap, at, date(2025, 1, 1), date(2026, 12, 31))
    pred = baseline_predictions(evaluation)
    baseline_metrics = {k: metrics(evaluation, v) for k, v in pred.items()}
    if baseline.get('freeze_sha256') != EXPECTED or baseline.get('features') != FEATURES or baseline.get('evaluation_cohort') != em or baseline.get('training_cohort') != tm or baseline.get('metrics') != baseline_metrics:
        raise ValueError('Baseline results are stale; rerun baselines')
    assert all(r[0] <= date(2024, 12, 31) for r in train)
    frozen_and_current(modules['duckdb'])
    pred['boosting'] = fit_predict(modules, train, evaluation)
    summary = {k: metrics(evaluation, v) for k, v in pred.items()}
    meta = {'freeze_sha256': EXPECTED, 'features': FEATURES, 'parameters': PARAMS, 'training_cohort': tm, 'evaluation_cohort': em, 'training_quality': q, 'combined_quality': aq, 'versions': {k: v.__version__ for k, v in modules.items()}, 'python': sys.version, 'limitation': LIMITATION}
    write_csv(OUT / 'predictions.csv', [dict(date=r[0].isoformat(), actual_mw=r[2], **{k: float(v[i]) for k, v in pred.items()}) for i, r in enumerate(evaluation)])
    write_csv(OUT / 'results.csv', [dict(model=k, **v) for k, v in summary.items()])
    write_json(OUT / 'metadata.json', meta)
    (OUT / 'results.md').write_text(summary_md('Holdout results', summary, meta), encoding='utf-8')


def stage_rolling(modules):
    if not (OUT / 'results.md').exists() or not (OUT / 'metadata.json').exists():
        raise ValueError('Run boosting first')
    source = training_sources(modules['duckdb'])
    peaks, temps, quality = daily(source['demand'], source['weather'])
    results, details = [], {}
    for year in (2023, 2024):
        train, tm = cohort(peaks, temps, train_start(peaks), date(year-1, 12, 31))
        evaluation, em = cohort(peaks, temps, date(year, 1, 1), date(year, 12, 31))
        assert all(r[0].year < year for r in train)
        frozen_and_current(modules['duckdb'])
        pred = baseline_predictions(evaluation)
        pred['boosting'] = fit_predict(modules, train, evaluation)
        details[str(year)] = {'training_cohort': tm, 'evaluation_cohort': em}
        results += [dict(year=year, model=k, **metrics(evaluation, v)) for k, v in pred.items()]
    write_csv(OUT / 'rolling.csv', results)
    (OUT / 'rolling.md').write_text(summary_md('Rolling origin results', results, {'windows': details, 'quality': quality, 'features': FEATURES, 'parameters': PARAMS, 'versions': {k: v.__version__ for k, v in modules.items()}}), encoding='utf-8')


def verify(modules, frozen):
    for day, count in [(date(2024, 3, 10), 23), (date(2024, 11, 3), 25), (date(2024, 2, 1), 24)]:
        hours = expected_hours(day)
        assert len(hours) == count and len(set(hours)) == count
        source = {'columns': ['hour_utc', 'demand_mwh'], 'rows': [[x.isoformat(), 100.0] for x in hours]}
        weather = {'columns': ['local_date', 'quality', 'high_f', 'low_f'], 'rows': []}
        p, _, _ = daily(source, weather)
        assert p[day] == 100.0
        source['rows'].pop()
        assert day not in daily(source, weather)[0]
    d = date(2024, 3, 1)
    p = {d - timedelta(days=n): float(n) for n in (0, 1, 2, 7, 14)}
    t = {d - timedelta(days=7): (70.0, 50.0)}
    rows, _ = cohort(p, t, d, d)
    assert rows[0][1] == [2024, 3, 4, 61, 0, 1.0, 2.0, 7.0, 14.0, 70.0, 50.0]
    tp, tt, _, ap, at, _ = prepare(modules['duckdb'], frozen)
    train, tm = cohort(tp, tt, train_start(tp), date(2024, 12, 31))
    combined_train, _ = cohort(ap, at, train_start(tp), date(2024, 12, 31))
    combined_by_day = {r[0]: r for r in combined_train}
    assert all(combined_by_day[r[0]] == r for r in train)
    assert set(combined_by_day) - {r[0] for r in train} <= {date(2024, 12, 31)}
    assert all(r[0] < date(2025, 1, 1) for r in train)
    altered = {key: dict(value, rows=[]) for key, value in frozen.items()}
    tp2, tt2, _, _, _, _ = prepare(modules['duckdb'], altered)
    assert cohort(tp2, tt2, train_start(tp2), date(2024, 12, 31))[0] == train
    path = OUT / 'predictions.csv'
    if path.exists():
        evaluation, em = cohort(ap, at, date(2025, 1, 1), date(2026, 12, 31))
        with path.open(newline='', encoding='utf-8') as f:
            predictions = list(csv.DictReader(f))
        assert [r['date'] for r in predictions] == [r[0].isoformat() for r in evaluation]
        assert all(math.isfinite(float(r[k])) for r in predictions for k in ('actual_mw', 'persistence', 'seasonal', 'boosting'))
        metadata = json.loads((OUT / 'metadata.json').read_text(encoding='utf-8'))
        assert metadata['training_cohort'] == tm and metadata['evaluation_cohort'] == em
    print('Verification passed; prediction checks run only when predictions.csv exists.')


def main():
    parser = argparse.ArgumentParser(description='Staged retrospective PJM daily peak evaluation')
    parser.add_argument('stage', choices=('baselines', 'boosting', 'rolling', 'verify'))
    args = parser.parse_args()
    modules = dependencies()
    frozen = frozen_and_current(modules['duckdb'])
    if args.stage == 'baselines':
        stage_baselines(modules, frozen)
    elif args.stage == 'boosting':
        stage_boosting(modules, frozen)
    elif args.stage == 'rolling':
        stage_rolling(modules)
    else:
        verify(modules, frozen)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)

