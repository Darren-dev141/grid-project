from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from scripts.issue_stress import build_features

ET = ZoneInfo('America/New_York')
UTC = timezone.utc


def _weather(update_time, high=65, low=40):
    return {'high_f': high, 'morning_low_f': low,
            'weather_available_at': update_time, 'weather_usable_at': update_time,
            'update_time': update_time, 'issuance_id': 'iss1'}


def test_weather_fresh_true_with_valid_pinned_issuance():
    issued = datetime(2026, 11, 5, 6, 30, tzinfo=ET)
    update = issued - timedelta(hours=2)
    wf = build_features([], issued, _weather(update))
    assert wf.weather_fresh is True


def test_weather_fresh_false_when_stale():
    issued = datetime(2026, 11, 5, 6, 30, tzinfo=ET)
    update = issued - timedelta(hours=13)
    wf = build_features([], issued, _weather(update))
    assert wf.weather_fresh is False


def test_weather_fresh_false_when_incomplete():
    issued = datetime(2026, 11, 5, 6, 30, tzinfo=ET)
    update = issued - timedelta(hours=2)
    wf = build_features([], issued, _weather(update, low=None))
    assert wf.weather_fresh is False


def test_weather_fresh_false_when_absent():
    issued = datetime(2026, 11, 5, 6, 30, tzinfo=ET)
    wf = build_features([], issued, None)
    assert wf.weather_fresh is False
