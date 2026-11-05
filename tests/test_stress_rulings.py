from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from grid_pipeline.ledger import read_definition
from grid_pipeline.model import Features, HistoryDay
from grid_pipeline.stress import forecast, parse_definition
from scripts.issue_stress import build_features, load_is_fresh

RAW = read_definition(Path(__file__).parents[1] / 'ledger/definitions/stress-index-v1.toml')


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


def test_prospective_timestamps_alone_do_not_prove_issue_time_availability():
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
    assert result.status == 'UNSCORED'
    assert result.no_call_reason == 'unverified_issue_time_availability'
    assert (result.peak_mw, result.peak_hour_ending, result.level, result.thresholds_mw) == (
        None, None, None, None)
    assert result.receipt.mode == 'prospective'
    assert result.receipt.publication_availability == 'unverified'
    assert result.receipt.history_evaluated is False
    # This synthetic selector check verifies timestamp comparisons, not provenance.
    from grid_pipeline.stress import _history_with_gates
    _, _, gates = _history_with_gates(inputs, parse_definition(RAW))
    assert gates['availability'] == {'entered': 80, 'passed': 76, 'rejected': 4}
    assert _call(replace(inputs, issued_at=None)).no_call_reason == 'missing_or_invalid_issue_time'
    assert _call(replace(inputs, issued_at=issue.replace(tzinfo=None))).no_call_reason == 'missing_or_invalid_issue_time'
    assert _call(replace(inputs, weather_available_at=after)).no_call_reason == 'target_weather_unavailable_at_issuance'
    assert _call(replace(inputs, weather_available_at=None)).no_call_reason == 'target_weather_unavailable_at_issuance'
    at_issue = _call(replace(inputs, weather_available_at=issue))
    assert at_issue.no_call_reason == 'unverified_issue_time_availability'


# Same-day issuance (W2, Darren's ruling of Nov 5, 2026): the 07:00 job on day D forecasts D's
# peak. These two tests replace
# test_prospective_issue_at_or_after_target_local_midnight_has_no_claim, whose
# before-the-target-date rule no longer holds; its four instants are all kept below.
@pytest.mark.parametrize(('target', 'issued'), [
    (date(2026, 7, 1), '2026-07-03T12:00:00+00:00'),     # two days after the target day
    (date(2026, 7, 1), '2026-07-01T11:00:01+00:00'),     # one second after 07:00 EDT
    (date(2026, 3, 8), '2026-03-08T11:00:01+00:00'),     # one second after 07:00 EDT (spring forward)
    (date(2026, 11, 1), '2026-11-01T12:00:01+00:00'),    # one second after 07:00 EST (fall back)
])
def test_prospective_issue_after_the_target_day_cutoff_has_no_claim(target, issued):
    issue = datetime.fromisoformat(issued)
    result = _call(_inputs(target_date=target, mode='prospective', issued_at=issue,
                           weather_available_at=issue - timedelta(hours=1)))
    assert result.no_call_reason == 'issue_time_after_target_day_cutoff'
    assert result.status == 'UNSCORED'
    assert result.receipt.publication_availability == 'unverified'
    assert result.peak_mw is None


@pytest.mark.parametrize(('target', 'issued'), [
    (date(2026, 7, 1), '2026-07-01T04:00:00+00:00'),     # target local midnight: old gate rejected
    (date(2026, 3, 8), '2026-03-08T05:00:00+00:00'),     # target local midnight (spring forward)
    (date(2026, 11, 1), '2026-11-01T04:00:00+00:00'),    # target local midnight (fall back)
    (date(2026, 7, 1), '2026-07-01T11:00:00+00:00'),     # exactly 07:00 EDT
    (date(2026, 3, 8), '2026-03-08T11:00:00+00:00'),     # exactly 07:00 EDT (spring forward)
    (date(2026, 11, 1), '2026-11-01T12:00:00+00:00'),    # exactly 07:00 EST (fall back)
    (date(2026, 11, 1), '2026-11-01T11:59:59+00:00'),    # 06:59:59 EST
])
def test_prospective_issue_at_or_before_the_target_day_cutoff_passes_the_timing_gate(target, issued):
    issue = datetime.fromisoformat(issued)
    result = _call(_inputs(target_date=target, mode='prospective', issued_at=issue,
                           weather_available_at=issue - timedelta(hours=1)))
    # The next gate in line: these inputs carry no commit-derived usable times.
    assert result.no_call_reason == 'unverified_issue_time_availability'


def test_unattested_first_recorded_history_never_becomes_a_forecast():
    from dataclasses import replace

    days = [replace(day, load_first_recorded=None, temperature_first_recorded=None) for day in _pool()]
    result = _call(_inputs(days))
    assert result.no_call_reason == 'insufficient_threshold_history'
    assert result.receipt.history_gates['first_recorded'] == {'entered': 80, 'passed': 0, 'rejected': 80}


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


# --- same-day issuance: scored, late, post-peak, stale (W2) ---------------------------

NEW_YORK = ZoneInfo('America/New_York')
TARGET = date(2026, 7, 1)
PEAK_HOUR = 19


def _stamped_pool(usable, peak_hour=PEAK_HOUR):
    return tuple(replace(day, peak_hour_ending=peak_hour, load_available_at=usable,
                         temperature_available_at=usable, load_usable_at=usable,
                         temperature_usable_at=usable) for day in _pool())


def _same_day(issued_at, peak_hour=PEAK_HOUR, **kwargs):
    """Prospective inputs for TARGET with history and weather verified usable an hour earlier."""
    usable = issued_at - timedelta(hours=1)
    return _inputs(_stamped_pool(usable, peak_hour), mode='prospective', issued_at=issued_at,
                   weather_available_at=usable, weather_usable_at=usable, **kwargs)


def test_same_day_issue_at_0700_with_fresh_verified_history_is_scored():
    issued = datetime(2026, 7, 1, 7, 0, tzinfo=NEW_YORK)
    assert issued.date() == TARGET                       # target_date stays the issue day
    result = _call(_same_day(issued))
    assert result.status == 'SCORED', result.no_call_reason
    assert result.target_date == TARGET
    assert result.peak_hour_ending == PEAK_HOUR
    assert result.receipt.publication_availability == 'verified'
    assert result.receipt.input_availability.verified is True


@pytest.mark.parametrize('issued', [
    datetime(2026, 7, 1, 0, 0, tzinfo=NEW_YORK),         # target local midnight
    datetime(2026, 7, 1, 6, 59, 59, tzinfo=NEW_YORK),
    datetime(2026, 6, 30, 17, 17, tzinfo=NEW_YORK),      # the day before still precedes the cutoff
    datetime(2026, 7, 1, 11, 0, tzinfo=timezone.utc),    # 07:00 EDT given in UTC
])
def test_same_day_issue_at_or_before_the_cutoff_is_scored(issued):
    assert _call(_same_day(issued)).status == 'SCORED'


@pytest.mark.parametrize('issued', [
    datetime(2026, 7, 1, 7, 0, 0, 1, tzinfo=NEW_YORK),   # one microsecond late
    datetime(2026, 7, 1, 7, 0, 8, tzinfo=NEW_YORK),      # when the Nov 4 scheduled run fired
    datetime(2026, 7, 1, 11, 0, 1, tzinfo=timezone.utc), # one second after 07:00 EDT, in UTC
])
def test_same_day_issue_after_the_cutoff_has_no_claim(issued):
    result = _call(_same_day(issued))
    assert result.status == 'UNSCORED'
    assert result.no_call_reason == 'issue_time_after_target_day_cutoff'
    assert (result.peak_mw, result.peak_hour_ending, result.level) == (None, None, None)
    assert result.receipt.publication_availability == 'unverified'


@pytest.mark.parametrize('issued', [
    datetime(2026, 7, 1, 18, 0, tzinfo=NEW_YORK),        # the start of the peak hour (HE 19)
    datetime(2026, 7, 1, 19, 0, tzinfo=NEW_YORK),        # the end of the peak hour
    datetime(2026, 7, 1, 23, 59, tzinfo=NEW_YORK),
])
def test_same_day_issue_after_the_days_peak_has_no_claim(issued):
    result = _call(_same_day(issued))
    assert result.status == 'UNSCORED'
    assert result.no_call_reason == 'issue_time_after_target_day_cutoff'
    assert result.peak_mw is None


@pytest.mark.parametrize(('peak_hour', 'issued', 'expected'), [
    (7, datetime(2026, 7, 1, 5, 59, 59, tzinfo=NEW_YORK), None),   # before HE 7 (06:00-07:00)
    (7, datetime(2026, 7, 1, 6, 0, tzinfo=NEW_YORK), None),        # exactly at its start
    (7, datetime(2026, 7, 1, 6, 0, 1, tzinfo=NEW_YORK), 'issue_time_after_peak'),
    (7, datetime(2026, 7, 1, 7, 0, tzinfo=NEW_YORK), 'issue_time_after_peak'),
    (8, datetime(2026, 7, 1, 7, 0, tzinfo=NEW_YORK), None),        # HE 8 starts at 07:00
])
def test_issue_after_the_start_of_the_forecast_peak_hour_has_no_claim(peak_hour, issued, expected):
    result = _call(_same_day(issued, peak_hour))
    assert result.no_call_reason == expected
    assert result.status == ('SCORED' if expected is None else 'UNSCORED')
    if expected:
        assert (result.peak_mw, result.peak_hour_ending, result.level) == (None, None, None)
        assert result.receipt.history_evaluated is True


def _fresh_day(day, usable):
    return HistoryDay(day, 1040, PEAK_HOUR, 80, 60, True, load_first_recorded=True,
                      temperature_first_recorded=True, load_available_at=usable,
                      temperature_available_at=usable, load_usable_at=usable,
                      temperature_usable_at=usable)


def _history_through(last_day, usable):
    return _stamped_pool(usable) + (_fresh_day(last_day, usable),)


def _target_row(issued, *, load_first_recorded=None):
    """The target day's weather row; it has no load, as at 07:00 on the day itself."""
    usable = issued - timedelta(hours=1)
    return HistoryDay(TARGET, None, None, 95, 50, False, load_first_recorded=load_first_recorded,
                      temperature_first_recorded=True, temperature_available_at=usable,
                      temperature_usable_at=usable)


def test_same_day_features_with_history_through_d_minus_2_are_scored_without_a_target_load_row():
    issued = datetime(2026, 7, 1, 7, 0, tzinfo=NEW_YORK)
    usable = issued - timedelta(hours=1)
    history = _history_through(TARGET - timedelta(days=2), usable) + (_target_row(issued),)
    features = build_features(history, issued)
    assert features.target_date == TARGET and features.load_fresh is True
    result = _call(features)
    assert result.status == 'SCORED', result.no_call_reason
    assert result.receipt.publication_availability == 'verified'


@pytest.mark.parametrize('last_day', [TARGET - timedelta(days=5), TARGET - timedelta(days=3)])
def test_same_day_stale_history_still_no_calls_stale_load(last_day):
    issued = datetime(2026, 7, 1, 7, 0, tzinfo=NEW_YORK)
    usable = issued - timedelta(hours=1)
    # Even a target-day row claiming first-recorded load must not rescue stale history.
    history = (_history_through(last_day, usable)
               + (_target_row(issued, load_first_recorded=True),))
    features = build_features(history, issued)
    assert features.load_fresh is False
    result = _call(features)
    assert result.status == 'UNSCORED'
    assert result.no_call_reason == 'stale_load'


def test_load_freshness_is_judged_on_the_completed_peak_two_days_before_the_target():
    usable = datetime(2026, 7, 1, 6, tzinfo=NEW_YORK)
    d2 = TARGET - timedelta(days=2)
    fresh = _fresh_day(d2, usable)
    assert load_is_fresh((fresh,), d2) is True
    assert load_is_fresh((), d2) is False
    assert load_is_fresh((_fresh_day(TARGET - timedelta(days=3), usable),), d2) is False
    assert load_is_fresh((replace(fresh, complete=False),), d2) is False
    assert load_is_fresh((replace(fresh, load_first_recorded=None),), d2) is False
    assert load_is_fresh((replace(fresh, peak_mw=None),), d2) is False
    assert load_is_fresh((replace(fresh, peak_mw=float('nan')),), d2) is False
    # D-1 is not a completed peak at a 07:00 issuance and is dropped before the check.
    issued = datetime(2026, 7, 1, 7, 0, tzinfo=NEW_YORK)
    only_d1 = (_fresh_day(TARGET - timedelta(days=1), usable),)
    assert build_features(only_d1, issued).load_fresh is False
