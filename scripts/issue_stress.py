"""Issue the S3c stress forecast prospectively and write its receipt.

This is the durable scheduled-job entry point. It never fabricates availability
times: history availability comes from committed raw archives, and prospective
mode fails closed when first-usable provenance cannot be verified.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
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


def main() -> None:
    issued_at = datetime.now(ET)
    target_date = issued_at.date()
    scheduled_cutoff = issued_at.replace(hour=7, minute=0, second=0, microsecond=0)
    input_cutoff = min(issued_at, scheduled_cutoff)
    latest_completed_peak = target_date - timedelta(days=2)
    all_history = load_first_recorded_history(LOAD_DB, TEMP_DB, indexed_by=input_cutoff)
    by_date = {day.date: day for day in all_history}
    target = by_date.get(target_date)
    history = tuple(day for day in all_history if day.date <= latest_completed_peak)
    features = Features(
        target_date=target_date,
        high_f=target.high_f if target is not None else None,
        morning_low_f=target.morning_low_f if target is not None else None,
        history=history,
        load_fresh=target is not None and target.load_first_recorded is True,
        weather_fresh=target is not None and target.temperature_first_recorded is True,
        alerts=(),
        mode="prospective",
        issued_at=issued_at,
        weather_available_at=target.temperature_available_at if target is not None else None,
        weather_usable_at=target.temperature_usable_at if target is not None else None,
    )
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