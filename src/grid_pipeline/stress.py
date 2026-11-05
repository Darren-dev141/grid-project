"""Stress-index v1 calculation and its input-provenance receipt."""
from collections import Counter
from dataclasses import replace
from datetime import date, datetime, timedelta
from hashlib import sha256
from math import isfinite
import tomllib
from zoneinfo import ZoneInfo

import numpy as np

from grid_pipeline.model import (Alert, AvailabilityCheck, Definition, Features, Forecast,
                                 ForecastReceipt, HistoryDay)


_V1 = {
    'version': 'stress-index-v1', 'weather_point': 'NWS LWX/107,85',
    'history_station': 'USW00093721', 'history_years': 3, 'window_days': 21,
    'heat_base_f': 65, 'cold_base_f': 50, 'hinge_min_nonzero_days': 10,
    'watch_percentile': 75, 'strained_percentile': 90, 'severe_percentile': 97,
    'analog_count': 10, 'settle_days': 2, 'alerts': {'annotation_only': True},
}


def parse_definition(raw: bytes) -> Definition:
    """Parse exact v1 settings and hash the original bytes, without reading files."""
    try:
        values = tomllib.loads(raw.decode('utf-8-sig'))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError('invalid stress definition') from exc
    if values.keys() != _V1.keys() or any(
        type(values[key]) is not type(value) or values[key] != value
        for key, value in _V1.items()
    ):
        raise ValueError('unsupported stress definition')
    alerts = values.pop('alerts')
    if type(alerts['annotation_only']) is not bool:
        raise ValueError('unsupported stress definition')
    return Definition(sha256=sha256(raw).hexdigest(),
                      alerts_annotation_only=alerts['annotation_only'], **values)


def _active_hinges(days: tuple[HistoryDay, ...]) -> tuple[bool, bool]:
    return (sum(day.high_f > 65 for day in days) >= 10,
            sum(day.morning_low_f < 50 for day in days) >= 10)


def _level(peak: float, watch: float, strained: float, severe: float) -> str:
    if peak >= severe:
        return 'severe'
    if peak >= strained:
        return 'strained'
    if peak >= watch:
        return 'watch'
    return 'calm'


def _mode_hour(hours: list[int]) -> int:
    counts = Counter(hours)
    return min(counts, key=lambda hour: (-counts[hour], hour))


def _fit_model(days: tuple[HistoryDay, ...]):
    """Fit active hinges and return the coefficients, diagnostics, and fallbacks."""
    if not days:
        raise ValueError('empty regression history')
    heat, cold = _active_hinges(days)
    fallbacks = []
    if not heat:
        fallbacks.append('heat_hinge_fewer_than_10_nonzero_days')
    if not cold:
        fallbacks.append('cold_hinge_fewer_than_10_nonzero_days')
    columns = {'heat': np.array([max(0.0, day.high_f - 65) for day in days]),
               'cold': np.array([max(0.0, 50 - day.morning_low_f) for day in days])}
    active = [name for name, enabled in (('heat', heat), ('cold', cold)) if enabled]
    ones = np.ones(len(days))

    def design():
        return np.column_stack([ones] + [columns[name] for name in active])

    def condition(matrix):
        try:
            value = float(np.linalg.cond(matrix))
            return value if isfinite(value) else float('inf')
        except np.linalg.LinAlgError:
            return float('inf')

    matrix = design()
    initial_condition = condition(matrix)
    response = np.array([day.peak_mw for day in days], dtype=float)
    response_scale = float(np.std(response))
    if active and initial_condition > 1e10:
        for name in active[:]:
            column = columns[name]
            column_scale = float(np.std(column))
            near_zero = (column_scale < 1e-10 * response_scale
                         or len(set(float(value) for value in column)) < 2)
            if near_zero:
                active.remove(name)
                fallbacks.append(f'{name}_hinge_near_zero_variance')
        matrix = design()
        if active and condition(matrix) > 1e10:
            active.clear()
            matrix = design()
            fallbacks.append('ill_conditioned_intercept_only')
    if not active and 'ill_conditioned_intercept_only' not in fallbacks:
        fallbacks.append('intercept_only')
    coefficients = np.linalg.lstsq(matrix, np.array([day.peak_mw for day in days]), rcond=None)[0]
    return (tuple(float(value) for value in coefficients), tuple(active), tuple(fallbacks),
            initial_condition, condition(matrix))


def _fit(days: tuple[HistoryDay, ...]) -> tuple[float, ...]:
    return _fit_model(days)[0]


class DefinitionGap(ValueError):
    """The published specification does not determine a forecast."""


def _finite(value) -> bool:
    try:
        return value is not None and isfinite(value)
    except (TypeError, ValueError):
        return False


def _aware(value) -> bool:
    return isinstance(value, datetime) and value.utcoffset() is not None


def _available_at_issue(value, issued_at) -> bool:
    return _aware(value) and _aware(issued_at) and value <= issued_at


def verify_input_availability(features: Features,
                              used_days: tuple[HistoryDay, ...]) -> AvailabilityCheck:
    """Check that every input a prospective forecast would use was first usable by issuance.

    Evidence is the loader's commit-record-derived `*_usable_at` (the later of a
    batch's loaded_at and observed_at, committed batches only), never the legacy
    `*_available_at` indexing times and never a caller flag. Fails closed: a
    missing, naive, or post-issuance usable time on any used history day or on the
    target weather leaves the result unverified. `verified` is only ever True here.
    """
    if not _aware(features.issued_at):
        return AvailabilityCheck(False, 'missing_or_invalid_issue_time')
    if not used_days:
        return AvailabilityCheck(False, 'no_history_to_verify')
    unproven = [day for day in used_days
                if not (_available_at_issue(day.load_usable_at, features.issued_at)
                        and _available_at_issue(day.temperature_usable_at, features.issued_at))]
    stamps = [stamp for day in used_days
              for stamp in (day.load_usable_at, day.temperature_usable_at)
              if stamp is not None and _aware(stamp)]
    latest = max(stamps, default=None)
    if unproven:
        return AvailabilityCheck(False, 'history_first_usable_not_proven_by_issuance',
                                 len(used_days), len(unproven), latest)
    weather = features.weather_usable_at
    if weather is None or not _available_at_issue(weather, features.issued_at):
        return AvailabilityCheck(False, 'target_weather_first_usable_not_proven_by_issuance',
                                 len(used_days), 0, latest)
    return AvailabilityCheck(True, None, len(used_days), 0, max([*stamps, weather]))


def _season_window(target_date: date, definition: Definition) -> set[str]:
    leap_year = date(2024, 1, 1).year
    def slot(day: date) -> int:
        return (day - date(leap_year, 1, 1)).days
    target_slot = slot(target_date.replace(year=leap_year))
    slots = {(target_slot + offset) % 366 for offset in range(-definition.window_days,
                                                              definition.window_days + 1)}
    return {(date(leap_year, 1, 1) + timedelta(days=slot_number)).strftime('%m-%d')
            for slot_number in slots}

def _history_with_gates(features: Features, definition: Definition):
    window = _season_window(features.target_date, definition)
    gates = {}

    def keep(name, rows, predicate):
        kept = tuple(day for day in rows if predicate(day))
        gates[name] = {'entered': len(rows), 'passed': len(kept),
                       'rejected': len(rows) - len(kept)}
        return kept

    rows = features.history
    rows = keep('prior_date', rows, lambda day: day.date < features.target_date)
    rows = keep('history_year', rows, lambda day:
                day.date.year >= features.target_date.year - definition.history_years)
    rows = keep('complete', rows, lambda day: day.complete)
    rows = keep('load_value', rows, lambda day: _finite(day.peak_mw))
    rows = keep('first_recorded', rows, lambda day:
                day.load_first_recorded is True and day.temperature_first_recorded is True)
    rows = keep('temperature', rows, lambda day:
                _finite(day.high_f) and _finite(day.morning_low_f))
    rows = keep('availability', rows, lambda day: features.mode == 'retrospective' or (
        _available_at_issue(day.load_available_at, features.issued_at)
        and _available_at_issue(day.temperature_available_at, features.issued_at)))
    rows = keep('latest_completed_peak', rows, lambda day: features.mode == 'retrospective' or (
        _aware(features.issued_at) and day.date <=
        features.issued_at.astimezone(ZoneInfo('America/New_York')).date() - timedelta(days=2)))
    by_date = {}
    for day in rows:
        by_date.setdefault(day.date, []).append(day)
    unique_rows = tuple(group[0] for group in by_date.values()
                        if all(day == group[0] for day in group))
    gates['unique_date'] = {'entered': len(rows), 'passed': len(unique_rows),
                            'rejected': len(rows) - len(unique_rows)}
    rows = unique_rows
    rows = keep('season', rows, lambda day: day.date.strftime('%m-%d') in window)
    weekend = features.target_date.weekday() >= 5
    fit_days = keep('day_type', rows, lambda day: (day.date.weekday() >= 5) == weekend)
    return rows, fit_days, gates


def _history(features: Features, definition: Definition) -> tuple[HistoryDay, ...]:
    return _history_with_gates(features, definition)[0]


def _day_type_history(features: Features, definition: Definition) -> tuple[HistoryDay, ...]:
    return _history_with_gates(features, definition)[1]


def annotate_alerts(target_date, alerts: tuple[Alert, ...]) -> tuple[str, ...]:
    """Select caller-supplied date annotations; interval mapping is upstream."""
    return tuple(alert.text for alert in alerts if alert.date == target_date)


def _analogs(features: Features, candidates: tuple[HistoryDay, ...], count: int):
    values = np.array([(day.high_f, day.morning_low_f) for day in candidates], dtype=float)
    target = np.array((features.high_f, features.morning_low_f), dtype=float)
    scales = values.std(axis=0)
    fallbacks = []
    for axis, name in enumerate(('high', 'low')):
        if scales[axis] == 0:
            fallbacks.append(f'analog_{name}_zero_variance')
    # A constant axis contributes the same distance to every candidate.
    standardized = np.zeros_like(values)
    np.divide(values - target, scales, out=standardized, where=scales != 0)
    distances = np.hypot(standardized[:, 0], standardized[:, 1])
    ranked = sorted(zip(candidates, distances), key=lambda pair: (pair[1], -pair[0].date.toordinal()))
    return tuple(day for day, _ in ranked[:count]), tuple(fallbacks)


def forecast(features: Features, definition: Definition) -> Forecast:
    """Forecast from eligible first-recorded inputs, or return an explicit no-call."""
    if features.mode not in ('retrospective', 'prospective'):
        raise ValueError('mode must be retrospective or prospective')
    alerts = annotate_alerts(features.target_date, features.alerts)
    receipt = ForecastReceipt(features.mode, 'unverified', features.issued_at)

    def no_call(reason, details):
        return Forecast(features.target_date, definition.version, definition.sha256,
                        None, None, None, None, reason, alerts, 'UNSCORED', details)

    if not features.load_fresh or not features.weather_fresh:
        return no_call('stale_load' if not features.load_fresh else 'stale_weather', receipt)
    if not _finite(features.high_f) or not _finite(features.morning_low_f):
        return no_call('missing_target_temperature', receipt)
    gated = None
    if features.mode == 'prospective':
        if not _aware(features.issued_at):
            return no_call('missing_or_invalid_issue_time', receipt)
        if features.issued_at.astimezone(ZoneInfo('America/New_York')).date() >= features.target_date:
            return no_call('issue_time_not_before_target_date', receipt)
        if not _available_at_issue(features.weather_available_at, features.issued_at):
            return no_call('target_weather_unavailable_at_issuance', receipt)
        # Indexing timestamps and caller flags cannot establish first usable commits.
        # Only the commit-record-derived usable times on the rows actually used can.
        gated = _history_with_gates(features, definition)
        availability = verify_input_availability(features, gated[0])
        receipt = replace(receipt, input_availability=availability)
        if not availability.verified:
            return no_call('unverified_issue_time_availability', receipt)
        receipt = replace(receipt, publication_availability='verified')

    threshold_days, fit_days, history_gates = (
        gated if gated is not None else _history_with_gates(features, definition))
    candidates = tuple(day for day in fit_days
                       if type(day.peak_hour_ending) is int and 1 <= day.peak_hour_ending <= 24)
    analog_gates = {
        'season': history_gates['season'],
        'day_type': history_gates['day_type'],
        'peak_hour': {'entered': len(fit_days), 'passed': len(candidates),
                      'rejected': len(fit_days) - len(candidates)},
    }
    samples = {'threshold': len(threshold_days), 'fit': len(fit_days),
               'analog_candidates': len(candidates), 'analogs_selected': 0}
    receipt = replace(receipt, history_evaluated=True, history_gates=history_gates,
                      analog_gates=analog_gates, sample_sizes=samples)
    if len(threshold_days) < 20:
        return no_call('insufficient_threshold_history', receipt)
    if len(fit_days) < 20:
        return no_call('insufficient_fit_history', receipt)
    if len(candidates) < 5:
        return no_call('insufficient_analogs', receipt)

    selected, analog_fallbacks = _analogs(features, candidates, definition.analog_count)
    coefficients, active, fit_fallbacks, initial_condition, final_condition = _fit_model(fit_days)
    terms = {'heat': max(0.0, features.high_f - definition.heat_base_f),
             'cold': max(0.0, definition.cold_base_f - features.morning_low_f)}
    peak = coefficients[0] + sum(coef * terms[name] for coef, name in zip(coefficients[1:], active))
    thresholds = tuple(float(value) for value in np.quantile(
        [day.peak_mw for day in threshold_days],
        [definition.watch_percentile / 100, definition.strained_percentile / 100,
         definition.severe_percentile / 100], method='linear'))
    fallbacks = fit_fallbacks + analog_fallbacks
    if len(selected) < definition.analog_count:
        fallbacks += ('fewer_than_10_analogs_used_available_pool',)
    samples = dict(samples, analogs_selected=len(selected))
    analog_gates = dict(analog_gates, selected={'entered': len(candidates), 'passed': len(selected),
                                                'rejected': len(candidates) - len(selected)})
    receipt = replace(receipt, sample_sizes=samples, analog_gates=analog_gates,
                      fallbacks=fallbacks, analog_dates=tuple(day.date for day in selected),
                      regression_coefficients=coefficients, active_hinges=active,
                      initial_condition_number=initial_condition, final_condition_number=final_condition)
    return Forecast(features.target_date, definition.version, definition.sha256, float(peak),
                    _mode_hour([day.peak_hour_ending for day in selected]),
                    _level(peak, *thresholds), thresholds, None, alerts, 'SCORED', receipt)
