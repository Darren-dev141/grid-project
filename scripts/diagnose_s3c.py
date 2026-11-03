"""Read-only eligibility probe over the original 2,833 real complete dates.

Observed calendar-day target weather and first-recorded fitting history are a
retrospective reconstruction. No issue times or availability stamps are invented.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

from grid_pipeline.ledger import read_definition, receipt_paths
from grid_pipeline.model import Alert, Features
from grid_pipeline.stress import DefinitionGap, forecast, parse_definition
from grid_pipeline.stress_inputs import load_first_recorded_history

LOCAL = ZoneInfo('America/New_York')
EXPECTED_YEARS = {2019: 361, 2020: 356, 2021: 363, 2022: 363,
                  2023: 364, 2024: 364, 2025: 365, 2026: 297}
TARGET_STAGES = ('freshness', 'target_temperature', 'calendar_window',
                 'threshold_stratum', 'fit_stratum', 'analog_floor', 'classified')
FAILED_STAGE = {
    'stale_load': 'freshness', 'stale_weather': 'freshness',
    'missing_target_temperature': 'target_temperature',
    'calendar_definition_gap': 'calendar_window',
    'insufficient_threshold_history': 'threshold_stratum',
    'insufficient_fit_history': 'fit_stratum',
    'insufficient_analogs': 'analog_floor',
}


def json_value(value):
    """Preserve infinite condition diagnostics without emitting invalid JSON."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def records(connection, sql):
    result = connection.execute(sql)
    columns = [column[0] for column in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def source_inventory(database):
    with duckdb.connect(str(database), read_only=True) as connection:
        batches = records(connection, '''
            SELECT source, dataset, count(*) AS batches,
                count(*) FILTER (WHERE committed) AS committed_batches,
                min(loaded_at) AS first_loaded_at, max(loaded_at) AS last_loaded_at,
                count(*) FILTER (WHERE loaded_at IS NULL) AS missing_loaded_at,
                min(observed_at) AS first_observed_at, max(observed_at) AS last_observed_at
            FROM raw.batches GROUP BY source, dataset ORDER BY source, dataset''')
        raw_rows = records(connection, '''
            SELECT r.source, r.dataset, count(*) AS raw_rows,
                count(DISTINCT r.digest) AS batches_with_rows
            FROM raw.records r JOIN raw.batches b USING (source, dataset, digest)
            WHERE b.committed GROUP BY r.source, r.dataset ORDER BY r.source, r.dataset''')
        geography = records(connection, '''
            SELECT r.dataset, r.payload ->> 'respondent' AS respondent,
                r.payload ->> 'subba' AS subba, r.payload ->> 'parent' AS parent,
                r.payload ->> 'type' AS row_type, count(*) AS raw_rows,
                count(DISTINCT r.payload ->> 'period') AS distinct_periods,
                min(r.payload ->> 'period') AS first_period,
                max(r.payload ->> 'period') AS last_period
            FROM raw.records r JOIN raw.batches b USING (source, dataset, digest)
            WHERE r.source = 'eia' AND b.committed
                AND r.dataset IN ('electricity/rto/region-data',
                                  'electricity/rto/region-sub-ba-data')
            GROUP BY ALL ORDER BY r.dataset, respondent, subba, parent, row_type''')
    return {'batches': batches, 'raw_rows': raw_rows, 'geography': geography}


def availability_bound(history, cohort):
    """Audit a necessary condition without choosing historical issue times.

    A value first loaded after the ENTIRE target local date cannot have been
    known for any forecast before or during that date. Passing this loose bound
    would not establish availability at an actual issuance.
    """
    counts = Counter()
    details = []
    for row in cohort:
        day = row['local_date']
        end = datetime.combine(day + timedelta(days=1), time.min, LOCAL)
        prior = [item for item in history if item.date < day and item.complete
                 and item.high_f is not None and item.morning_low_f is not None]
        known = sum(item.load_available_at is not None
                    and item.temperature_available_at is not None
                    and item.load_available_at < end
                    and item.temperature_available_at < end for item in prior)
        counts['prior_complete_temperature_pairs'] += len(prior)
        counts['pairs_recorded_before_target_date_ended'] += known
        counts['target_dates_with_any_pair_recorded_before_date_ended'] += known > 0
        details.append({'date': day, 'prior_complete_temperature_pairs': len(prior),
                        'pairs_recorded_before_target_date_ended': known})
    loads = [item.load_available_at for item in history if item.load_available_at]
    temperatures = [item.temperature_available_at for item in history
                    if item.temperature_available_at]
    return dict(counts, label='NECESSARY-CONDITION AUDIT, NOT AN ISSUANCE SIMULATION',
                cutoff='exclusive end of target local date; not a forecast issue time',
                load_first=min(loads, default=None), load_last=max(loads, default=None),
                temperature_first=min(temperatures, default=None),
                temperature_last=max(temperatures, default=None), dates=details)


def probe(mart, load_db, temperature_db, definition_path):
    definition = parse_definition(read_definition(definition_path))
    paths = {'cohort_mart': Path(mart), 'load': Path(load_db),
             'temperature': Path(temperature_db)}
    before_hashes = {name: sha256(path.read_bytes()).hexdigest()
                     for name, path in paths.items()}
    with duckdb.connect(str(mart), read_only=True) as connection:
        rows = records(connection, 'SELECT * FROM marts.mart_day_history ORDER BY local_date')
    cohort = [row for row in rows if 2019 <= row['local_date'].year <= 2026
              and row['complete'] and row['tmax_f'] is not None and row['tmin_f'] is not None]
    years = dict(Counter(row['local_date'].year for row in cohort))
    if years != EXPECTED_YEARS or len({row['local_date'] for row in cohort}) != 2833:
        raise ValueError(f'original 2,833-date cohort mismatch: {years!r}')
    history = load_first_recorded_history(load_db, temperature_db)
    by_date = {day.date: day for day in history}
    availability = availability_bound(history, cohort)
    inventories = {name: source_inventory(path) for name, path in paths.items()
                   if name != 'cohort_mart'}
    repo = Path(__file__).resolve().parents[1]
    receipt_files = [str(path.relative_to(repo)) for path in receipt_paths(repo / 'ledger')]
    outcomes = Counter()
    yearly = defaultdict(Counter)
    history_totals = defaultdict(Counter)
    analog_totals = defaultdict(Counter)
    target_gates = {stage: Counter(entered=0, passed=0, rejected=0) for stage in TARGET_STAGES}
    samples = defaultdict(list)
    fallbacks = Counter()
    details = []
    integration = None
    for row in cohort:
        day = row['local_date']
        features = Features(day, row['tmax_f'], row['tmin_f'], history, True, True,
                            mode='retrospective')
        reason = None
        try:
            value = forecast(features, definition)
            reason = value.no_call_reason
            outcome = value.level if value.status == 'SCORED' else 'UNSCORED:' + reason
            if reason is not None and reason not in FAILED_STAGE:
                raise ValueError(f'unrecognized forecast rejection: {reason}')
            receipt = asdict(value.receipt)
            if value.receipt.history_evaluated:
                for name, counts in value.receipt.history_gates.items():
                    history_totals[name].update(counts)
                    history_totals[name]['target_dates_evaluated'] += 1
                for name, counts in value.receipt.analog_gates.items():
                    analog_totals[name].update(counts)
                for name, count in value.receipt.sample_sizes.items():
                    samples[name].append(count)
            fallbacks.update(value.receipt.fallbacks)
            details.append({'date': day, 'outcome': outcome, 'receipt': receipt})
            if day == date(2025, 7, 1):
                annotated = forecast(replace(features, alerts=(Alert(day, 'annotation check'),)),
                                     definition)
                claims = ('peak_mw', 'peak_hour_ending', 'level', 'thresholds_mw', 'status')
                same = all(getattr(value, key) == getattr(annotated, key) for key in claims)
                integration = {'input': 'REAL original mart target, REAL first-recorded history',
                               'annotation_source': 'SYNTHETIC annotation for invariance check only',
                               'complete': row['complete'], 'target_high_f': row['tmax_f'],
                               'target_low_f': row['tmin_f'], 'forecast': asdict(value),
                               'claims_identical_with_alert': same,
                               'passed': value.status == 'SCORED' and same}
        except DefinitionGap as exc:
            reason = 'calendar_definition_gap'
            outcome = 'DefinitionGap:' + str(exc)
            details.append({'date': day, 'outcome': outcome})
        outcomes[outcome] += 1
        yearly[day.year][outcome] += 1
        failed = FAILED_STAGE.get(reason)
        for stage in TARGET_STAGES:
            target_gates[stage]['entered'] += 1
            if stage == failed:
                target_gates[stage]['rejected'] += 1
                target_gates[stage]['reason:' + reason] += 1
                break
            target_gates[stage]['passed'] += 1
    after_hashes = {name: sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    if before_hashes != after_hashes:
        raise RuntimeError('source database changed during probe; results need a fresh snapshot')
    retrospective = {
        'label': 'OBSERVED-WEATHER RETROSPECTIVE ELIGIBILITY RECONSTRUCTION',
        'publication_availability': 'unverified', 'issued_forecasts': False,
        'outcomes': dict(outcomes), 'years': dict(yearly),
        'target_gates': target_gates, 'history_row_gates': history_totals,
        'analog_row_gates': analog_totals,
        'sample_ranges': {key: {'min': min(values), 'max': max(values)}
                          for key, values in samples.items()},
        'fallbacks': dict(fallbacks), 'integration': integration, 'dates': details,
    }
    return {
        'sources': {name: str(path.resolve()) for name, path in paths.items()},
        'source_sha256_before': before_hashes, 'source_sha256_after': after_hashes,
        'definition_sha256': definition.sha256,
        'cohort': {'dates': len(cohort), 'first': cohort[0]['local_date'],
                   'last': cohort[-1]['local_date'], 'years': years, 'mart_dates': len(rows),
                   'complete_demand': sum(row['complete'] for row in rows),
                   'date_sha256': sha256(''.join(row['local_date'].isoformat() + '\n'
                                               for row in cohort).encode()).hexdigest()},
        'modes': {'retrospective': retrospective,
                  'prospective': {'status': 'NOT RUN', 'outcomes': None,
                                  'reason': 'No real historical issuance ledger or archived '
                                            'target-weather forecast evidence was supplied. '
                                            'No hypothetical issue times were assigned.'}},
        'suspects_in_order': [
            {'suspect': '(a) first-recorded / known-at availability', 'evidence': availability},
            {'suspect': '(b) geography', 'evidence': inventories},
            {'suspect': '(c) alerts / receipts dependency',
             'evidence': {'ledger_receipt_files': receipt_files,
                          'dependency_evidence_basis': 'source inspection of stress.forecast',
                          'numeric_forecast_reads_alert_or_receipt_store': False,
                          'alert_claim_invariance': integration}},
            {'suspect': '(d) analog pool collapse',
             'evidence': {'gates': analog_totals, 'sample_ranges': retrospective['sample_ranges']}},
            {'suspect': '(e) date / completeness / DST', 'evidence': {
                'expected_hours': dict(Counter(row['expected_hours'] for row in rows)),
                'dst_dates': [row for row in rows if row['expected_hours'] != 24],
                'incomplete_dates': [row for row in rows if not row['complete']],
                'complete_missing_temperature_dates': [row['local_date'] for row in rows
                    if row['complete'] and (row['tmax_f'] is None or row['tmin_f'] is None)],
                'first_snapshot_dates': len(history),
                'first_snapshot_complete': sum(day.complete for day in history),
                'first_vs_settled_changes': [row['local_date'] for row in rows
                    if row['local_date'] in by_date and
                    (by_date[row['local_date']].peak_mw, by_date[row['local_date']].high_f,
                     by_date[row['local_date']].morning_low_f) !=
                    (row['peak_mw'], row['tmax_f'], row['tmin_f'])],
            }},
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mart', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    result = probe(args.mart, repo / 'data/s1-live/grid.duckdb',
                   repo / 'data/s3a-verification/grid.duckdb',
                   repo / 'ledger/definitions/stress-index-v1.toml')
    args.output.write_text(json.dumps(json_value(result), indent=2, allow_nan=False) + '\n',
                           encoding='utf-8')
    mode = result['modes']['retrospective']
    print(json.dumps(json_value({key: value for key, value in result.items()
                                 if key not in ('modes', 'suspects_in_order')}), indent=2))
    print(json.dumps(json_value({key: value for key, value in mode.items()
                                 if key != 'dates'}), indent=2))
    if not mode['integration'] or not mode['integration']['passed']:
        raise SystemExit('REAL integration failed: 2025-07-01 did not classify with invariant alerts')


if __name__ == '__main__':
    main()
