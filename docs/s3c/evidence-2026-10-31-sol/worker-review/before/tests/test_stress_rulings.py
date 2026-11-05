from datetime import date, timedelta
from pathlib import Path

import pytest

from grid_pipeline.model import Features, HistoryDay
from grid_pipeline.stress import forecast, parse_definition

RAW = (Path(__file__).parents[1] / 'ledger/definitions/stress-index-v1.toml').read_bytes()


def test_forecast_returns_type7_thresholds_and_a_real_classification():
    days = []
    for year in (2024, 2025):
        for offset in range(40):
            day = date(year, 6, 12) + timedelta(days=offset)
            days.append(HistoryDay(day, 1000 + 2 * offset, 19, 65 + offset, 50, True,
                                   load_first_recorded=True, temperature_first_recorded=True))
    inputs = Features(date(2026, 7, 1), 95, 50, tuple(days), True, True)

    result = forecast(inputs, parse_definition(RAW))

    assert result.status == 'SCORED'
    assert result.peak_mw == pytest.approx(1060)
    assert result.thresholds_mw == pytest.approx((1058.5, 1070.2, 1076))
    assert (result.level, result.peak_hour_ending, result.no_call_reason) == ('watch', 19, None)
    assert result.receipt.mode == 'retrospective'
    assert result.receipt.publication_availability == 'unverified'
    assert result.receipt.sample_sizes['threshold'] == 80


def test_constant_hinges_fall_back_to_intercept_only():
    from grid_pipeline.stress import _fit

    days = tuple(HistoryDay(date(2025, 7, 1), 100, 19, 66, 49, True) for _ in range(10))
    assert _fit(days) == pytest.approx((100,))


def _pool():
    return tuple(
        HistoryDay(date(year, 6, 12) + timedelta(days=offset), 1000 + 2 * offset, 19,
                   65 + offset, 50, True, load_first_recorded=True,
                   temperature_first_recorded=True)
        for year in (2024, 2025) for offset in range(40)
    )


def _inputs(days=None, **kwargs):
    values = dict(target_date=date(2026, 7, 1), high_f=95, morning_low_f=50,
                  history=_pool() if days is None else tuple(days), load_fresh=True,
                  weather_fresh=True)
    values.update(kwargs)
    return Features(**values)


def _call(inputs):
    return forecast(inputs, parse_definition(RAW))


def test_eligibility_receipt_counts_each_exclusion_and_never_uses_revisions():
    from dataclasses import replace

    days = list(_pool())
    days[0] = replace(days[0], high_f=None)
    days[1] = replace(days[1], morning_low_f=float('nan'))
    days[2] = replace(days[2], load_first_recorded=None)
    days[3] = replace(days[3], complete=False)
    days[4] = replace(days[4], peak_mw=None)
    days.extend((
        replace(days[5], date=date(2026, 7, 1)),
        replace(days[5], date=date(2026, 7, 2)),
        replace(days[5], date=date(2022, 7, 1)),
        replace(days[5], date=date(2025, 1, 1)),
        replace(days[6], peak_mw=999999, load_first_recorded=False),
        replace(days[7], peak_mw=999999),
    ))

    result = _call(_inputs(days))
    assert result.status == 'SCORED'
    assert result.peak_mw == pytest.approx(1060)
    gates = result.receipt.history_gates
    assert {name: gates[name]['rejected'] for name in (
        'prior_date', 'history_year', 'complete', 'load_value', 'first_recorded',
        'temperature', 'availability', 'unique_date', 'season'
    )} == {'prior_date': 2, 'history_year': 1, 'complete': 1, 'load_value': 1,
           'first_recorded': 2, 'temperature': 2, 'availability': 0,
           'unique_date': 2, 'season': 1}
    assert gates['day_type']['passed'] == result.receipt.sample_sizes['fit']
    assert gates['season']['passed'] == result.receipt.sample_sizes['threshold']
    assert result.receipt.publication_availability == 'unverified'


@pytest.mark.parametrize(('high', 'low'), [(None, 50), (90, None), (float('nan'), 50), (90, float('inf'))])
def test_missing_or_nonfinite_target_temperature_has_no_forecast(high, low):
    result = _call(_inputs(high_f=high, morning_low_f=low))
    assert result.status == 'UNSCORED'
    assert result.no_call_reason == 'missing_target_temperature'
    assert result.peak_mw is None
    assert result.receipt.history_evaluated is False


def test_threshold_and_fit_sample_floors_are_distinct():
    from itertools import islice

    days = _pool()
    weekdays = list(islice((day for day in days if day.date.weekday() < 5), 20))
    weekends = list(islice((day for day in days if day.date.weekday() >= 5), 10))
    below_threshold = _call(_inputs(weekdays[:19]))
    assert below_threshold.no_call_reason == 'insufficient_threshold_history'
    assert below_threshold.receipt.sample_sizes['threshold'] == 19

    below_fit = _call(_inputs(weekdays[:19] + weekends))
    assert below_fit.no_call_reason == 'insufficient_fit_history'
    assert below_fit.receipt.sample_sizes['threshold'] == 29
    assert below_fit.receipt.sample_sizes['fit'] == 19

    enough = _call(_inputs(weekdays))
    assert enough.status == 'SCORED'
    assert enough.receipt.sample_sizes['fit'] == 20


@pytest.mark.parametrize(('candidate_count', 'expected_status'), [(4, 'UNSCORED'), (5, 'SCORED'),
                                                                  (9, 'SCORED'), (10, 'SCORED')])
def test_analog_floor_and_fallback(candidate_count, expected_status):
    from dataclasses import replace

    days = list(_pool())
    eligible_indices = [i for i, day in enumerate(days) if day.date.weekday() < 5]
    for index in eligible_indices[candidate_count:]:
        days[index] = replace(days[index], peak_hour_ending=None)
    result = _call(_inputs(days))
    assert result.status == expected_status
    assert result.receipt.sample_sizes['analog_candidates'] == candidate_count
    assert result.receipt.analog_gates['peak_hour']['rejected'] == len(eligible_indices) - candidate_count
    if candidate_count < 5:
        assert result.no_call_reason == 'insufficient_analogs'
        assert result.receipt.sample_sizes['analogs_selected'] == 0
    else:
        assert result.receipt.sample_sizes['analogs_selected'] == candidate_count
        assert ('fewer_than_10_analogs_used_available_pool' in result.receipt.fallbacks) == (candidate_count < 10)


def test_analog_distance_ties_prefer_newest_and_hour_mode_ties_prefer_earlier():
    from dataclasses import replace

    days = list(_pool())
    eligible = sorted((i for i, day in enumerate(days) if day.date.weekday() < 5),
                      key=lambda i: days[i].date, reverse=True)
    for rank, index in enumerate(eligible):
        days[index] = replace(days[index], high_f=90, morning_low_f=60,
                              peak_hour_ending=(8 if rank < 5 else 19) if rank < 11 else None)
    result = _call(_inputs(days, high_f=90, morning_low_f=60))
    assert result.status == 'SCORED'
    assert result.receipt.analog_dates == tuple(days[i].date for i in eligible[:10])
    assert result.peak_hour_ending == 8
    assert 'analog_high_zero_variance' in result.receipt.fallbacks
    assert 'analog_low_zero_variance' in result.receipt.fallbacks


def test_z_scored_analog_distance_does_not_apply_a_temperature_band():
    from dataclasses import replace

    days = list(_pool())
    eligible = [i for i, day in enumerate(days) if day.date.weekday() < 5]
    for index in eligible:
        days[index] = replace(days[index], peak_hour_ending=None)
    coordinates = [(90, 60)] * 8 + [(90, 61), (100, 60), (130, 60)]
    for index, (high, low) in zip(eligible, coordinates):
        days[index] = replace(days[index], high_f=high, morning_low_f=low, peak_hour_ending=19)
    result = _call(_inputs(days, high_f=90, morning_low_f=60))
    assert result.status == 'SCORED'
    assert days[eligible[8]].date not in result.receipt.analog_dates
    assert days[eligible[10]].date in result.receipt.analog_dates


def test_ill_conditioned_near_constant_hinge_is_dropped_before_refit():
    from dataclasses import replace

    days = [replace(day, high_f=66 + i * 1e-12, morning_low_f=50 - i,
                    peak_mw=100 + 2 * i) for i, day in enumerate(_pool())]
    result = _call(_inputs(days, high_f=66, morning_low_f=40))
    assert result.status == 'SCORED'
    assert result.peak_mw == pytest.approx(120)
    assert result.receipt.initial_condition_number > 1e10
    assert result.receipt.final_condition_number <= 1e10
    assert result.receipt.active_hinges == ('cold',)
    assert 'heat_hinge_near_zero_variance' in result.receipt.fallbacks


def test_correlated_hinges_fall_back_to_intercept_and_record_it():
    from dataclasses import replace

    days = [replace(day, high_f=65 + i, morning_low_f=50 - i,
                    peak_mw=100 + 2 * i) for i, day in enumerate(_pool())]
    result = _call(_inputs(days, high_f=75, morning_low_f=40))
    expected = sum(day.peak_mw for day in days if day.date.weekday() < 5) / sum(
        day.date.weekday() < 5 for day in days)
    assert result.peak_mw == pytest.approx(expected)
    assert result.receipt.active_hinges == ()
    assert 'ill_conditioned_intercept_only' in result.receipt.fallbacks
    assert result.receipt.initial_condition_number > 1e10


def test_prospective_checks_target_and_each_historical_source_at_issuance():
    from dataclasses import replace
    from datetime import datetime, timezone

    issue = datetime(2026, 6, 30, 12, tzinfo=timezone.utc)
    before = issue - timedelta(hours=1)
    after = issue + timedelta(seconds=1)
    days = [replace(day, load_available_at=before, temperature_available_at=before)
            for day in _pool()]
    days[0] = replace(days[0], load_available_at=after)
    days[1] = replace(days[1], temperature_available_at=after)
    days[2] = replace(days[2], load_available_at=None)
    days[3] = replace(days[3], temperature_available_at=before.replace(tzinfo=None))
    inputs = _inputs(days, mode='prospective', issued_at=issue, weather_available_at=before)
    result = _call(inputs)
    assert result.status == 'SCORED'
    assert result.receipt.mode == 'prospective'
    assert result.receipt.publication_availability == 'verified_at_issuance'
    assert result.receipt.history_gates['availability'] == {'entered': 80, 'passed': 76, 'rejected': 4}
    assert _call(replace(inputs, issued_at=None)).no_call_reason == 'missing_or_invalid_issue_time'
    assert _call(replace(inputs, issued_at=issue.replace(tzinfo=None))).no_call_reason == 'missing_or_invalid_issue_time'
    assert _call(replace(inputs, weather_available_at=after)).no_call_reason == 'target_weather_unavailable_at_issuance'
    assert _call(replace(inputs, weather_available_at=None)).no_call_reason == 'target_weather_unavailable_at_issuance'
    at_issue = _call(replace(inputs, weather_available_at=issue))
    assert at_issue.status == 'SCORED'


def test_unattested_first_recorded_history_never_becomes_a_forecast():
    from dataclasses import replace

    days = [replace(day, load_first_recorded=None, temperature_first_recorded=None) for day in _pool()]
    result = _call(_inputs(days))
    assert result.no_call_reason == 'insufficient_threshold_history'
    assert result.receipt.history_gates['first_recorded'] == {'entered': 80, 'passed': 0, 'rejected': 80}


def test_leap_day_at_window_start_remains_a_definition_gap():
    from grid_pipeline.stress import DefinitionGap

    with pytest.raises(DefinitionGap, match='calendar boundary'):
        _call(_inputs(target_date=date(2028, 3, 21)))


def test_alerts_are_annotations_only_for_fresh_forecasts():
    from dataclasses import replace
    from grid_pipeline.model import Alert

    inputs = _inputs()
    without = _call(inputs)
    with_alert = _call(replace(inputs, alerts=(Alert(inputs.target_date, 'warning'),)))
    assert with_alert.alerts == ('warning',)
    assert (with_alert.peak_mw, with_alert.level, with_alert.peak_hour_ending) == (
        without.peak_mw, without.level, without.peak_hour_ending)


def test_legacy_forecast_construction_derives_a_consistent_status():
    from grid_pipeline.model import Forecast

    scored = Forecast(date(2026, 7, 1), 'v1', 'hash', 100, 19, 'calm', (120, 130, 140), None, ())
    unscored = Forecast(date(2026, 7, 1), 'v1', 'hash', None, None, None, None, 'stale_load', ())
    assert scored.status == 'SCORED'
    assert unscored.status == 'UNSCORED'


def test_weekend_forecast_uses_weekends_for_fit_and_all_days_for_thresholds():
    from itertools import islice

    days = tuple(day for day in _pool() if (day.date.month, day.date.day) >= (6, 13))
    weekends = list(islice((day for day in days if day.date.weekday() >= 5), 20))
    weekdays = list(islice((day for day in days if day.date.weekday() < 5), 10))
    result = _call(_inputs(weekends + weekdays, target_date=date(2026, 7, 4)))
    assert result.status == 'SCORED'
    assert result.receipt.sample_sizes['fit'] == 20
    assert result.receipt.sample_sizes['threshold'] == 30
    assert all(day.weekday() >= 5 for day in result.receipt.analog_dates)


def test_identical_repeated_history_record_counts_as_one_day():
    days = list(_pool())
    days.append(days[0])
    result = _call(_inputs(days))
    assert result.status == 'SCORED'
    assert result.receipt.sample_sizes['threshold'] == 80
    assert result.receipt.history_gates['unique_date'] == {'entered': 81, 'passed': 80, 'rejected': 1}
