"""Prospective input-availability verification (W3).

`input_availability_verified` has to be earned from commit-record-derived first-usable
times. These tests cover the stress-level check with synthetic days, the loader's
derivation from batch commit records (positive and negative), and one end-to-end run
loader -> Features -> forecast -> receipt fields. They verify timestamp logic against
local synthetic archives; they do not show that any real input was published when
its commit record says.
"""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from grid_pipeline.ledger import read_definition
from grid_pipeline.model import AvailabilityCheck, Features, HistoryDay
from grid_pipeline.stress import forecast, parse_definition, verify_input_availability
from grid_pipeline.stress_inputs import load_first_recorded_history
from scripts.issue_stress import availability_fields
from test_stress_inputs import (EIA_DATASET, NCEI_DATASET, add_batch, hourly_rows,
                                make_database, temperature_row)

RAW = read_definition(Path(__file__).parents[1] / 'ledger/definitions/stress-index-v1.toml')
UTC = timezone.utc
ISSUE = datetime(2026, 6, 30, 12, tzinfo=UTC)
TARGET = date(2026, 7, 1)
BEFORE = ISSUE - timedelta(hours=1)
AFTER = ISSUE + timedelta(seconds=1)


def _day(day, offset, usable=BEFORE):
    return HistoryDay(day, 1000 + 2 * offset, 19, 65 + offset, 50, True,
                      load_first_recorded=True, temperature_first_recorded=True,
                      load_available_at=BEFORE, temperature_available_at=BEFORE,
                      load_usable_at=usable, temperature_usable_at=usable)


def _pool(usable=BEFORE):
    return tuple(_day(date(year, 6, 12) + timedelta(days=offset), offset, usable)
                 for year in (2024, 2025) for offset in range(40))


def _inputs(days=None, **kwargs):
    values = dict(target_date=TARGET, high_f=95, morning_low_f=50,
                  history=_pool() if days is None else tuple(days), load_fresh=True,
                  weather_fresh=True, mode='prospective', issued_at=ISSUE,
                  weather_available_at=BEFORE, weather_usable_at=BEFORE)
    values.update(kwargs)
    return Features(**values)


def _call(inputs):
    return forecast(inputs, parse_definition(RAW))


# --- stress-level check -------------------------------------------------------------

def test_commit_derived_usable_times_verify_and_the_forecast_is_scored():
    result = _call(_inputs())
    assert result.status == 'SCORED'
    assert result.no_call_reason is None
    assert result.receipt.publication_availability == 'verified'
    check = result.receipt.input_availability
    assert check == AvailabilityCheck(True, None, 80, 0, BEFORE)
    assert availability_fields(result)['input_availability_verified'] is True


def test_usable_exactly_at_issuance_verifies_and_one_second_later_does_not():
    assert _call(_inputs(_pool(usable=ISSUE), weather_usable_at=ISSUE)).status == 'SCORED'
    late = _call(_inputs(_pool(usable=AFTER)))
    assert late.status == 'UNSCORED'
    assert late.no_call_reason == 'unverified_issue_time_availability'


@pytest.mark.parametrize('change', [
    {'load_usable_at': AFTER},
    {'temperature_usable_at': AFTER},
    {'load_usable_at': None},
    {'temperature_usable_at': None},
    {'load_usable_at': BEFORE.replace(tzinfo=None)},
])
def test_one_unproven_used_day_leaves_the_whole_run_unverified(change):
    days = list(_pool())
    days[10] = replace(days[10], **change)
    result = _call(_inputs(days))
    assert result.status == 'UNSCORED'
    assert result.no_call_reason == 'unverified_issue_time_availability'
    assert result.peak_mw is None and result.level is None
    assert result.receipt.publication_availability == 'unverified'
    assert result.receipt.history_evaluated is False
    check = result.receipt.input_availability
    assert (check.verified, check.reason, check.days_checked, check.days_unproven) == (
        False, 'history_first_usable_not_proven_by_issuance', 80, 1)
    assert availability_fields(result)['input_availability_verified'] is False


def test_indexing_times_alone_never_verify():
    days = [replace(day, load_usable_at=None, temperature_usable_at=None) for day in _pool()]
    result = _call(_inputs(days))
    assert result.no_call_reason == 'unverified_issue_time_availability'
    assert result.receipt.input_availability.days_unproven == 80
    assert availability_fields(result)['input_availability_verified'] is False


@pytest.mark.parametrize('weather_usable_at', [None, AFTER, BEFORE.replace(tzinfo=None)])
def test_target_weather_needs_its_own_first_usable_proof(weather_usable_at):
    result = _call(_inputs(weather_usable_at=weather_usable_at))
    assert result.no_call_reason == 'unverified_issue_time_availability'
    assert result.receipt.input_availability.reason == (
        'target_weather_first_usable_not_proven_by_issuance')
    assert result.receipt.publication_availability == 'unverified'


def test_only_days_the_forecast_uses_must_be_proven():
    out_of_season = replace(_day(date(2025, 12, 25), 0), load_usable_at=None,
                            temperature_usable_at=None)
    result = _call(_inputs(_pool() + (out_of_season,)))
    assert result.status == 'SCORED'
    assert result.receipt.input_availability.days_checked == 80


def test_check_cannot_pass_without_history():
    check = verify_input_availability(_inputs(()), ())
    assert (check.verified, check.reason) == (False, 'no_history_to_verify')
    assert verify_input_availability(_inputs(issued_at=None), _pool()).verified is False


def test_flag_is_false_when_the_run_no_called_before_the_check():
    result = _call(_inputs(load_fresh=False))
    assert result.no_call_reason == 'stale_load'
    fields = availability_fields(result)
    assert fields['input_availability_verified'] is False
    assert 'not reached' in fields['input_availability_note']


# --- loader derivation from batch commit records ------------------------------------

@pytest.fixture
def databases(tmp_path):
    load_database = tmp_path / 'load.duckdb'
    temperature_database = tmp_path / 'temperature.duckdb'
    make_database(load_database)
    make_database(temperature_database)
    return load_database, temperature_database


DAY = date(2026, 6, 15)
CUTOFF = datetime(2026, 6, 30, 11, tzinfo=UTC)


def _history(databases, **kwargs):
    return {item.date: item for item in load_first_recorded_history(*databases, **kwargs)}


def test_committed_batch_usable_time_is_the_later_of_indexing_and_commit(databases):
    load_database, temperature_database = databases
    indexed, committed = datetime(2026, 6, 20, 9, tzinfo=UTC), datetime(2026, 6, 20, 9, 5, tzinfo=UTC)
    add_batch(load_database, 'eia', EIA_DATASET, 'a', indexed, hourly_rows(DAY), observed_at=committed)
    add_batch(temperature_database, 'ncei', NCEI_DATASET, 'a', committed, [temperature_row(DAY)],
              observed_at=indexed)
    day = _history(databases, indexed_by=CUTOFF)[DAY]
    assert day.load_usable_at == committed
    assert day.load_available_at == indexed
    # A commit record earlier than the indexing time cannot make rows usable before indexing.
    assert day.temperature_usable_at == committed
    assert day.temperature_available_at == committed


def test_backdated_indexing_time_does_not_move_usable_time_earlier(databases):
    load_database, temperature_database = databases
    backdated = datetime(2026, 6, 16, 6, tzinfo=UTC)
    committed = CUTOFF + timedelta(hours=1)
    add_batch(load_database, 'eia', EIA_DATASET, 'a', backdated, hourly_rows(DAY), observed_at=committed)
    add_batch(temperature_database, 'ncei', NCEI_DATASET, 'a', backdated, [temperature_row(DAY)],
              observed_at=committed)
    day = _history(databases, indexed_by=CUTOFF)[DAY]
    assert day.load_available_at == backdated and day.temperature_available_at == backdated
    assert day.load_usable_at == committed and day.temperature_usable_at == committed
    check = verify_input_availability(_inputs(issued_at=CUTOFF, weather_usable_at=backdated), (day,))
    assert check.verified is False
    assert check.reason == 'history_first_usable_not_proven_by_issuance'


def test_committed_batch_without_a_commit_record_has_no_usable_time(databases):
    load_database, temperature_database = databases
    indexed = datetime(2026, 6, 16, 6, tzinfo=UTC)
    add_batch(load_database, 'eia', EIA_DATASET, 'a', indexed, hourly_rows(DAY))
    add_batch(temperature_database, 'ncei', NCEI_DATASET, 'a', indexed, [temperature_row(DAY)])
    day = _history(databases, indexed_by=CUTOFF)[DAY]
    assert day.load_available_at == indexed and day.temperature_available_at == indexed
    assert day.load_usable_at is None and day.temperature_usable_at is None
    assert verify_input_availability(_inputs(issued_at=CUTOFF), (day,)).verified is False


def test_uncommitted_batch_rows_never_verify_or_pull_usable_time_earlier(databases):
    load_database, temperature_database = databases
    early = datetime(2026, 6, 16, 6, tzinfo=UTC)
    committed = CUTOFF + timedelta(hours=1)
    other = DAY + timedelta(days=1)
    # DAY's early batch is uncommitted; the committed copy of the same rows lands after the cutoff.
    add_batch(load_database, 'eia', EIA_DATASET, 'pending', early, hourly_rows(DAY),
              observed_at=early, committed=False)
    add_batch(load_database, 'eia', EIA_DATASET, 'real', early + timedelta(hours=1),
              hourly_rows(DAY), observed_at=committed)
    # `other` exists only in an uncommitted batch.
    add_batch(load_database, 'eia', EIA_DATASET, 'only-pending', early, hourly_rows(other),
              observed_at=early, committed=False)
    add_batch(temperature_database, 'ncei', NCEI_DATASET, 'a', early,
              [temperature_row(DAY), temperature_row(other)], observed_at=early)
    history = _history(databases, indexed_by=CUTOFF)
    assert history[DAY].load_usable_at == committed
    assert history[other].load_first_recorded is None
    assert history[other].load_usable_at is None
    assert verify_input_availability(_inputs(issued_at=CUTOFF), (history[other],)).verified is False


def test_adjacent_hour_without_a_commit_record_blocks_the_day(databases):
    load_database, temperature_database = databases
    indexed = datetime(2026, 6, 16, 6, tzinfo=UTC)
    add_batch(load_database, 'eia', EIA_DATASET, 'a', indexed, hourly_rows(DAY), observed_at=indexed)
    add_batch(load_database, 'eia', EIA_DATASET, 'neighbor', indexed,
              hourly_rows(DAY + timedelta(days=1))[:1])
    add_batch(temperature_database, 'ncei', NCEI_DATASET, 'a', indexed, [temperature_row(DAY)],
              observed_at=indexed)
    assert _history(databases, indexed_by=CUTOFF)[DAY].load_usable_at is None


# --- end to end ----------------------------------------------------------------------

def _archive(databases, *, backdated_day=None):
    """A summer archive: 2025 and 2026 days in the season window, committed before ISSUE."""
    load_database, temperature_database = databases
    days = ([date(2025, 6, 11) + timedelta(days=n) for n in range(43)]
            + [date(2026, 6, 11) + timedelta(days=n) for n in range(18)])
    stamp = datetime(2026, 6, 29, 20, tzinfo=UTC)
    for number, day in enumerate(days):
        load_rows = hourly_rows(day)
        for row in load_rows:                          # flat day, distinct level per day
            row['value'] = 100 + number
        indexed, committed = stamp, stamp + timedelta(minutes=1)
        if day == backdated_day:
            indexed, committed = stamp, ISSUE + timedelta(hours=1)
        add_batch(load_database, 'eia', EIA_DATASET, f'd{number}', indexed, load_rows,
                  observed_at=committed)
        add_batch(temperature_database, 'ncei', NCEI_DATASET, f't{number}', indexed,
                  [temperature_row(day, high=str(60 + number % 30), low=str(45 + number % 12))],
                  observed_at=committed)
    return days


def _end_to_end(databases):
    history = tuple(day for day in load_first_recorded_history(*databases, indexed_by=ISSUE)
                    if day.date <= date(2026, 6, 28))
    return _call(Features(
        target_date=TARGET, high_f=88.0, morning_low_f=60.0, history=history, load_fresh=True,
        weather_fresh=True, mode='prospective', issued_at=ISSUE,
        weather_available_at=BEFORE, weather_usable_at=BEFORE))


def test_end_to_end_committed_archive_earns_the_flag(databases):
    _archive(databases)
    result = _end_to_end(databases)
    assert result.status == 'SCORED', result.no_call_reason
    assert result.receipt.publication_availability == 'verified'
    fields = availability_fields(result)
    assert fields['input_availability_verified'] is True
    assert result.receipt.input_availability.days_checked == result.receipt.sample_sizes['threshold']


def test_end_to_end_backdated_indexing_time_does_not_earn_the_flag(databases):
    days = _archive(databases, backdated_day=date(2025, 6, 20))
    assert date(2025, 6, 20) in days
    result = _end_to_end(databases)
    assert result.status == 'UNSCORED'
    assert result.no_call_reason == 'unverified_issue_time_availability'
    assert result.receipt.input_availability.days_unproven >= 1
    assert availability_fields(result)['input_availability_verified'] is False
