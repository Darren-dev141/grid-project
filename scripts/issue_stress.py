"""Issue the S3c stress forecast prospectively and write its receipt.

This is the durable scheduled-job entry point. It never fabricates availability
times: history availability comes from committed raw archives, and prospective
mode fails closed when first-usable provenance cannot be verified.

Same-day issuance (Darren's ruling, Nov 5, 2026): the 07:00 ET job on day D forecasts D's
peak, so `target_date` is the issue day. The latest completed peak is D-2 and load
freshness is judged on completed history through it, never on the target day's own row.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo

from grid_pipeline.ledger import read_definition
from grid_pipeline.model import Alert, Features
from grid_pipeline.stress import forecast, parse_definition
from grid_pipeline.stress_inputs import load_first_recorded_history

ROOT = Path(r"C:\Users\ajbig\Documents\grid-project")
DEFINITION = ROOT / "ledger" / "definitions" / "stress-index-v1.toml"
LOAD_DB = ROOT / "data" / "s1-live" / "grid.duckdb"
TEMP_DB = ROOT / "data" / "s3a-verification" / "grid.duckdb"
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def availability_fields(result) -> dict:
    """Receipt fields for input availability, taken only from the check's own outcome.

    `input_availability_verified` is True only when the forecast's receipt carries a
    passed `verify_input_availability` result. A run that no-called before the check
    (stale input, bad issue time, ...) reports False and says why it was not evaluated.
    """
    check = result.receipt.input_availability if result.receipt is not None else None
    if check is None:
        return {
            "input_availability_verified": False,
            "input_availability_note": "Availability check not reached; forecast no-called first: "
                                       f"{result.no_call_reason}.",
        }
    if check.verified:
        note = ("Every history day used and the target weather have a first-usable time, "
                "derived from committed batch records (later of loaded_at and observed_at), "
                "at or before issued_at. The commit record is local DuckDB state, not "
                "tamper-evident.")
    else:
        note = (f"Availability not verified: {check.reason} ({check.days_unproven} of "
                f"{check.days_checked} used days unproven).")
    return {"input_availability_verified": check.verified, "input_availability_note": note}


def load_is_fresh(history, latest_completed_peak) -> bool:
    """True when the latest completed peak (D-2) is in the first-recorded load history.

    Freshness is judged on completed history through `latest_completed_peak` (target - 2),
    never on the target day's own load row, which cannot exist when the day's 07:00 job
    runs. Requires that day to be complete, first-recorded, and to carry a finite peak.
    """
    return any(day.date == latest_completed_peak and day.complete
               and day.load_first_recorded is True
               and day.peak_mw is not None and isfinite(day.peak_mw)
               for day in history)


def build_features(all_history, issued_at) -> Features:
    """Prospective features for the same-day run: target day == issue day (S3c, Nov 5 ruling)."""
    target_date = issued_at.astimezone(ET).date()
    latest_completed_peak = target_date - timedelta(days=2)
    by_date = {day.date: day for day in all_history}
    target = by_date.get(target_date)
    history = tuple(day for day in all_history if day.date <= latest_completed_peak)
    return Features(
        target_date=target_date,
        high_f=target.high_f if target is not None else None,
        morning_low_f=target.morning_low_f if target is not None else None,
        history=history,
        load_fresh=load_is_fresh(history, latest_completed_peak),
        weather_fresh=target is not None and target.temperature_first_recorded is True,
        alerts=(),
        mode="prospective",
        issued_at=issued_at,
        weather_available_at=target.temperature_available_at if target is not None else None,
        weather_usable_at=target.temperature_usable_at if target is not None else None,
    )


def main() -> None:
    issued_at = datetime.now(ET)
    target_date = issued_at.date()
    scheduled_cutoff = issued_at.replace(hour=7, minute=0, second=0, microsecond=0)
    input_cutoff = min(issued_at, scheduled_cutoff)
    latest_completed_peak = target_date - timedelta(days=2)
    all_history = load_first_recorded_history(LOAD_DB, TEMP_DB, indexed_by=input_cutoff)
    features = build_features(all_history, issued_at)
    result = forecast(features, parse_definition(read_definition(DEFINITION)))
    output = ROOT / "docs" / "s3c" / f"S3C-FIRST-ISSUANCE-{target_date.isoformat()}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    from dataclasses import asdict

    payload = {
        "issued_at": issued_at.isoformat(),
        "target_date": target_date.isoformat(),
        "scheduled_cutoff": scheduled_cutoff.isoformat(),
        "input_index_cutoff": input_cutoff.isoformat(),
        "issued_late": issued_at > scheduled_cutoff,
        "latest_completed_peak_date": latest_completed_peak.isoformat(),
        **availability_fields(result),
        "forecast": asdict(result),
    }
    with output.open('x', encoding='utf-8') as file:
        file.write(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()