from dataclasses import FrozenInstanceError
from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest

from grid_pipeline.ledger import read_definition
from grid_pipeline.model import Alert, Features, HistoryDay
from grid_pipeline.stress import DefinitionGap, annotate_alerts, _active_hinges, _day_type_history, _history, _level, _mode_hour, forecast, parse_definition


RAW = read_definition(Path(__file__).parents[1] / 'ledger/definitions/stress-index-v1.toml')


def history(day, high=65, low=50, hour=19):
    return HistoryDay(date.fromisoformat(day), 100, hour, high, low, True,
                      load_first_recorded=True, temperature_first_recorded=True)


def features(**overrides):
    values = dict(target_date=date(2026, 7, 1), high_f=90, morning_low_f=70,
                  history=(), load_fresh=True, weather_fresh=True, alerts=())
    values.update(overrides)
    return Features(**values)


def test_definition_hash_exact_bytes_and_immutable():
    definition = parse_definition(RAW)
    assert definition.sha256 == sha256(RAW).hexdigest()
    assert parse_definition(RAW + b'\n').sha256 != definition.sha256
    with pytest.raises(FrozenInstanceError):
        definition.sha256 = 'changed'


def test_drop_hinges_with_fewer_than_ten_nonzero_days():
    days = tuple(history('2025-07-01', high=66, low=49) for _ in range(9))
    assert _active_hinges(days) == (False, False)
    assert _active_hinges(days + (history('2025-07-02', high=66, low=50),)) == (True, False)


def test_levels_include_threshold_and_prefer_highest():
    assert _level(74, 75, 90, 97) == 'calm'
    assert _level(75, 75, 90, 97) == 'watch'
    assert _level(90, 75, 90, 97) == 'strained'
    assert _level(97, 75, 90, 97) == 'severe'


def test_peak_hour_mode_tie_goes_to_earlier_hour():
    assert _mode_hour([19, 8, 19, 8]) == 8


@pytest.mark.parametrize(('load', 'weather', 'reason'), [(False, True, 'stale_load'), (True, False, 'stale_weather')])
def test_stale_input_has_no_claims(load, weather, reason):
    result = forecast(features(load_fresh=load, weather_fresh=weather), parse_definition(RAW))
    assert (result.peak_mw, result.peak_hour_ending, result.level, result.thresholds_mw) == (None, None, None, None)
    assert result.no_call_reason == reason


def test_empty_history_is_explicitly_unscored():
    result = forecast(features(), parse_definition(RAW))
    assert result.status == 'UNSCORED'
    assert result.no_call_reason == 'insufficient_threshold_history'


def test_stale_alerts_only_include_target_day():
    alerts = (Alert(date(2026, 7, 1), 'Heat Warning'),
              Alert(date(2026, 7, 2), 'Next day'))
    result = forecast(features(load_fresh=False, alerts=alerts), parse_definition(RAW))
    assert result.alerts == ('Heat Warning',)
    assert result.level is None


def test_history_excludes_future_incomplete_and_wrong_season():
    days = (history('2025-07-01'), history('2026-07-01'),
            history('2026-07-02'), history('2025-01-01'),
            HistoryDay(date(2025, 7, 2), 100, 19, 80, 60, False),
            history('2022-07-01'))
    assert _history(features(history=days), parse_definition(RAW)) == (days[0],)


def test_day_type_fit_excludes_weekends():
    days = (history('2025-07-01'), history('2025-07-05'))
    assert _day_type_history(features(history=days), parse_definition(RAW)) == (days[0],)


def test_definition_rejects_unrecognized_or_changed_settings():
    with pytest.raises(ValueError):
        parse_definition(RAW.replace(b'heat_base_f = 65', b'heat_base_f = 66'))


def test_least_squares_fits_pinned_heat_hinge():
    from grid_pipeline.stress import _fit

    days = tuple(HistoryDay(date(2025, 7, i + 1), 100 + 2 * i, 19,
                            65 + i, 50, True) for i in range(1, 12))
    assert _fit(days) == pytest.approx((100, 2))


def test_circular_calendar_window_no_boundary_refusal():
    assert _history(features(target_date=date(2026, 1, 1)), parse_definition(RAW)) is not None


@pytest.mark.parametrize('year', [2024, 2025, 2026, 2028])
def test_window_ending_february_28_does_not_contain_a_leap_day(year):
    target = date(year, 2, 7)
    days = (history(f'{year - 1}-01-16'), history(f'{year - 1}-01-17'),
            history(f'{year - 1}-02-28'), history(f'{year - 1}-03-01'),
            history(f'{year}-02-06'), history(f'{year}-02-07'))
    assert _history(features(target_date=target, history=days), parse_definition(RAW)) == (
        days[1], days[2], days[4])


def test_definition_requires_annotation_only_alerts():
    with pytest.raises(ValueError):
        parse_definition(RAW.replace(b'annotation_only = true', b'annotation_only = false'))


def test_annotations_select_target_date_without_changing_level():
    alerts = (Alert(date(2026, 7, 1), 'Heat Warning'), Alert(date(2026, 7, 2), 'Tomorrow'))
    assert annotate_alerts(date(2026, 7, 1), alerts) == ('Heat Warning',)
    assert _level(90, 75, 90, 97) == 'strained'


def test_definition_rejects_integer_as_alert_boolean():
    with pytest.raises(ValueError):
        parse_definition(RAW.replace(b'annotation_only = true', b'annotation_only = 1'))
