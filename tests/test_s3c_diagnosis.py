"""Synthetic checks for honest diagnostics; these are not historical forecasts."""
from datetime import date, datetime, timezone
import json

from grid_pipeline.model import HistoryDay
from scripts.diagnose_s3c import availability_bound, json_value


def test_availability_audit_uses_local_date_bound_without_assigning_issue_time():
    # March 8 is a 23-hour New York date, ending at 04:00 UTC on March 9.
    prior = date(2026, 3, 7)
    before = datetime(2026, 3, 9, 3, 59, 59, tzinfo=timezone.utc)
    end = datetime(2026, 3, 9, 4, tzinfo=timezone.utc)
    history = (
        HistoryDay(prior, 100, 19, 70, 40, True,
                   load_available_at=before, temperature_available_at=before),
        HistoryDay(prior, 100, 19, 70, 40, True,
                   load_available_at=end, temperature_available_at=before),
        HistoryDay(prior, 100, 19, 70, 40, True),
        HistoryDay(date(2026, 3, 8), 100, 19, 70, 40, True,
                   load_available_at=before, temperature_available_at=before),
    )
    result = availability_bound(history, [{'local_date': date(2026, 3, 8)}])
    assert result['prior_complete_temperature_pairs'] == 3
    assert result['pairs_recorded_before_target_date_ended'] == 1
    assert result['target_dates_with_any_pair_recorded_before_date_ended'] == 1
    assert 'issued_at' not in result['dates'][0]


def test_infinite_condition_number_and_dates_are_preserved_in_strict_json():
    values = {'initial_condition_number': float('inf'),
              'date': date(2026, 7, 1), 'coefficients': (1.0, 2.0)}
    encoded = json.dumps(json_value(values), allow_nan=False)
    assert json.loads(encoded) == {
        'initial_condition_number': 'inf', 'date': '2026-07-01',
        'coefficients': [1.0, 2.0],
    }
