"""Read-only S3c eligibility diagnosis over the original historical probe cohort.

Retrospective reconstruction uses retained first snapshots, with publication
availability unverified. Prospective operation enforces their recorded timestamps.
This is an eligibility probe, not validation of historical issued forecasts.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, time, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

from grid_pipeline.model import Features
from grid_pipeline.stress import DefinitionGap, forecast, parse_definition, _history_with_gates
from grid_pipeline.stress_inputs import load_first_recorded_history

LOCAL = ZoneInfo('America/New_York')


def encode(value):
    if isinstance(value, (datetime,)) or hasattr(value, 'isoformat'):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def probe(mart, load_db, temperature_db, definition_path):
    definition = parse_definition(definition_path.read_bytes())
    history = load_first_recorded_history(load_db, temperature_db)
    by_date = {day.date: day for day in history}
    with duckdb.connect(str(mart), read_only=True) as conn:
        result = conn.execute('select * from marts.mart_day_history order by local_date')
        columns = [col[0] for col in result.description]
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    cohort = [r for r in rows if 2019 <= r['local_date'].year <= 2026
              and r['complete'] and r['tmax_f'] is not None and r['tmin_f'] is not None]
    report = {'sources': {'cohort_mart': str(mart), 'load': str(load_db),
                          'temperature': str(temperature_db)},
              'definition_sha256': definition.sha256,
              'cohort': {'dates': len(cohort), 'first': cohort[0]['local_date'],
                         'last': cohort[-1]['local_date'],
                         'years': dict(Counter(r['local_date'].year for r in cohort)),
                         'mart_dates': len(rows),
                         'complete_demand': sum(r['complete'] for r in rows),
                         'complete_temperatures': len(cohort)},
              'modes': {}, 'mechanics': {}, 'availability': {}}
    # Preserve the original target weather values and date cohort. Historical
    # fitting values come exclusively from retained first-recorded raw evidence.
    for mode in ('retrospective', 'prospective'):
        outcomes = Counter()
        years = defaultdict(Counter)
        history_totals = defaultdict(Counter)
        analog_totals = defaultdict(Counter)
        target_gates = defaultdict(Counter)
        sample_ranges = defaultdict(list)
        fallbacks = Counter()
        detail_rows = []
        integration = None
        for row in cohort:
            day = row['local_date']
            first = by_date.get(day)
            # The schedule in the accepted architecture is 21:17 UTC the prior
            # date. This is a requested-issuance audit, never an availability stamp.
            issue = datetime.combine(day - timedelta(days=1), time(21,17), timezone.utc)
            features = Features(day, row['tmax_f'], row['tmin_f'], history, True, True,
                                mode=mode, issued_at=issue if mode == 'prospective' else None,
                                weather_available_at=(first.temperature_available_at if first else None))
            stages = ['freshness', 'target_temperature']
            if mode == 'prospective':
                stages += ['issue_time', 'target_weather_availability']
            stages += ['calendar_window', 'threshold_sample', 'fit_sample', 'analog_floor', 'classified']
            reason = None
            try:
                value = forecast(features, definition)
                reason = value.no_call_reason
                label = value.level if value.status == 'SCORED' else 'UNSCORED:' + reason
                receipt = asdict(value.receipt)
                if value.receipt.history_evaluated:
                    for name, counts in value.receipt.history_gates.items():
                        history_totals[name].update(counts)
                        history_totals[name]['target_dates_evaluated'] += 1
                        history_totals[name]['target_dates_with_any_row_rejected'] += counts['rejected'] > 0
                    for name, counts in value.receipt.analog_gates.items():
                        analog_totals[name].update(counts)
                    for name, size in value.receipt.sample_sizes.items():
                        sample_ranges[name].append(size)
                fallbacks.update(value.receipt.fallbacks)
                if mode == 'retrospective' and day.isoformat() == '2025-07-01':
                    integration = asdict(value)
                detail_rows.append({'date': day, 'outcome': label, 'receipt': receipt})
            except DefinitionGap as exc:
                label = 'DefinitionGap:' + str(exc)
                reason = 'calendar_definition_gap'
                detail_rows.append({'date': day, 'outcome': label})
            outcomes[label] += 1
            years[day.year][label] += 1
            failed_stage = {
                'stale_load': 'freshness', 'stale_weather': 'freshness',
                'missing_target_temperature': 'target_temperature',
                'missing_or_invalid_issue_time': 'issue_time',
                'target_weather_unavailable_at_issuance': 'target_weather_availability',
                'calendar_definition_gap': 'calendar_window',
                'insufficient_threshold_history': 'threshold_sample',
                'insufficient_fit_history': 'fit_sample',
                'insufficient_analogs': 'analog_floor',
            }.get(reason)
            for stage in stages:
                target_gates[stage]['entered'] += 1
                if stage == failed_stage:
                    target_gates[stage]['rejected'] += 1
                    target_gates[stage]['reason:' + reason] += 1
                    break
                target_gates[stage]['passed'] += 1
        report['modes'][mode] = {
            'label': 'RETROSPECTIVE RECONSTRUCTION' if mode == 'retrospective' else 'PROSPECTIVE OPERATION',
            'outcomes': dict(outcomes), 'years': {y: dict(v) for y,v in years.items()},
            'target_gates': {k: dict(v) for k,v in target_gates.items()},
            'history_row_gates': {k: dict(v) for k,v in history_totals.items()},
            'analog_row_gates': {k: dict(v) for k,v in analog_totals.items()},
            'sample_ranges': {k: {'min': min(v), 'max': max(v)} for k,v in sample_ranges.items()},
            'fallbacks': dict(fallbacks), 'integration': integration, 'dates': detail_rows}
    # Independent availability audit, including rows whose target weather gate
    # prevents the actual forecast from reaching history selection.
    hist_counts = Counter()
    history_only_gates = defaultdict(Counter)
    for row in cohort:
        d = row['local_date']
        issue = datetime.combine(d-timedelta(days=1), time(21,17), timezone.utc)
        prior = [h for h in history if h.date < d and h.complete and h.high_f is not None and h.morning_low_f is not None]
        hist_counts['prior_complete_temperature_pairs'] += len(prior)
        hist_counts['pairs_available_at_issuance'] += sum(
            h.load_available_at is not None and h.temperature_available_at is not None
            and h.load_available_at <= issue and h.temperature_available_at <= issue for h in prior)
        try:
            _,_,gates = _history_with_gates(Features(d,row['tmax_f'],row['tmin_f'],history,True,True,
                                           mode='prospective',issued_at=issue),definition)
            for k,v in gates.items():
                history_only_gates[k].update(v)
        except DefinitionGap:
            hist_counts['calendar_gap_targets'] += 1
    timestamps = [h.load_available_at for h in history if h.load_available_at]
    temps = [h.temperature_available_at for h in history if h.temperature_available_at]
    report['availability'] = dict(hist_counts, load_first=min(timestamps), load_last=max(timestamps),
                                 temperature_first=min(temps),temperature_last=max(temps),
                                 independent_history_gates={k:dict(v) for k,v in history_only_gates.items()})
    report['mechanics'] = {
        'expected_hours': dict(Counter(r['expected_hours'] for r in rows)),
        'complete_dst_dates': [r['local_date'] for r in rows if r['complete'] and r['expected_hours'] != 24],
        'incomplete_dates': [r['local_date'] for r in rows if not r['complete']],
        'complete_missing_temperature_dates': [r['local_date'] for r in rows if r['complete'] and (r['tmax_f'] is None or r['tmin_f'] is None)],
        'first_snapshot_dates': len(history),
        'first_snapshot_complete': sum(h.complete for h in history),
        'first_vs_settled_changes': [r['local_date'] for r in rows if r['local_date'] in by_date and
            (by_date[r['local_date']].peak_mw,by_date[r['local_date']].high_f,by_date[r['local_date']].morning_low_f) !=
            (r['peak_mw'],r['tmax_f'],r['tmin_f'])],
    }
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mart', type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    result=probe(args.mart,repo/'data/s1-live/grid.duckdb',repo/'data/s3a-verification/grid.duckdb',
                 repo/'ledger/definitions/stress-index-v1.toml')
    args.output.write_text(json.dumps(result,default=encode,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('modes','mechanics')},default=encode,indent=2))
    for mode, values in result['modes'].items():
        print(mode,json.dumps({k:v for k,v in values.items() if k not in ('dates','years','integration')},default=encode,indent=2))


if __name__ == '__main__':
    main()
