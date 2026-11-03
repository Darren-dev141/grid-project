"""Run unmodified grid pipeline against synthetic twin."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

ROOT = Path(__file__).resolve().parent
GRID = Path(r"C:\Users\ajbig\Documents\grid-project")
import sys
sys.path.insert(0, str(GRID / "src"))

from grid_pipeline.model import Features
from grid_pipeline.stress import forecast, parse_definition
from grid_pipeline.stress_inputs import load_first_recorded_history
from grid_pipeline.ledger import read_definition

DEFINITION = GRID / "ledger" / "definitions" / "stress-index-v1.toml"
LOAD_DB = ROOT / "data" / "load.duckdb"
TEMP_DB = ROOT / "data" / "temperature.duckdb"
MANIFEST = json.loads((ROOT / "truth_manifest.json").read_text())

NY = ZoneInfo("America/New_York")
UTC = timezone.utc

definition = parse_definition(read_definition(DEFINITION))

# heatwave date sets
hw_dates = set()
for hw in MANIFEST["heatwaves"]:
    onset = datetime.fromisoformat(hw["onset_local"])
    end = onset + timedelta(hours=hw["duration_hours"])
    d = onset.astimezone(UTC).astimezone(NY).date()
    while d <= end.astimezone(UTC).astimezone(NY).date():
        hw_dates.add(d)
        d += timedelta(days=1)

history = load_first_recorded_history(LOAD_DB, TEMP_DB)
by_date = {h.date: h for h in history}

eval_start = date.fromisoformat(MANIFEST["evaluation_window"]["start"])
eval_end = date.fromisoformat(MANIFEST["evaluation_window"]["end"])

rows = []
for i in range((eval_end - eval_start).days + 1):
    d = eval_start + timedelta(days=i)
    h = by_date.get(d)
    if h is None:
        rows.append({"date": d.isoformat(), "level": None, "reason": "no_history", "peak_mw": None,
                     "actual_peak_mw": None, "in_hw": d in hw_dates})
        continue
    features = Features(
        target_date=d,
        high_f=h.high_f,
        morning_low_f=h.morning_low_f,
        history=history,
        load_fresh=h.load_first_recorded is True,
        weather_fresh=h.temperature_first_recorded is True,
        mode="retrospective",
    )
    res = forecast(features, definition)
    rows.append({
        "date": d.isoformat(),
        "level": res.level,
        "reason": res.no_call_reason,
        "peak_mw": res.peak_mw,
        "actual_peak_mw": h.peak_mw,
        "in_hw": d in hw_dates,
    })

# counts
elevated = lambda r: r["level"] in ("watch", "strained", "severe")
hits = sum(1 for r in rows if r["in_hw"] and elevated(r))
misses = sum(1 for r in rows if r["in_hw"] and not elevated(r))
false_alarms = sum(1 for r in rows if (not r["in_hw"]) and elevated(r))
tn = sum(1 for r in rows if (not r["in_hw"]) and not elevated(r))

# distributions
def dist(subset):
    from collections import Counter
    levels = Counter(r["level"] if r["level"] is not None else ("UNSCORED:" + (r["reason"] or "")) for r in subset)
    peaks = [r["peak_mw"] for r in subset if r["peak_mw"] is not None]
    actuals = [r["actual_peak_mw"] for r in subset if r["actual_peak_mw"] is not None]
    return {
        "n": len(subset),
        "levels": dict(levels),
        "peak_mw_mean": (sum(peaks) / len(peaks)) if peaks else None,
        "actual_peak_mw_mean": (sum(actuals) / len(actuals)) if actuals else None,
    }

in_window = [r for r in rows if r["in_hw"]]
out_window = [r for r in rows if not r["in_hw"]]

# issuance tests
def issuance(target_date, issued_at):
    cutoff = issued_at
    all_hist = load_first_recorded_history(LOAD_DB, TEMP_DB, indexed_by=cutoff)
    bd = {h.date: h for h in all_hist}
    target = bd.get(target_date)
    latest_completed = target_date - timedelta(days=2)
    hist = tuple(h for h in all_hist if h.date <= latest_completed)
    features = Features(
        target_date=target_date,
        high_f=target.high_f if target is not None else None,
        morning_low_f=target.morning_low_f if target is not None else None,
        history=hist,
        load_fresh=target is not None and target.load_first_recorded is True,
        weather_fresh=target is not None and target.temperature_first_recorded is True,
        alerts=(),
        mode="prospective",
        issued_at=issued_at,
        weather_available_at=target.temperature_available_at if target is not None else None,
    )
    res = forecast(features, definition)
    return res.no_call_reason, target

stale_mid = date.fromisoformat(MANIFEST["stale_gap"]["start"]) + timedelta(days=1)
clean_day = date(2026, 10, 25)
issued_stale = datetime(stale_mid.year, stale_mid.month, stale_mid.day, 7, 0, tzinfo=NY) - timedelta(days=1)
issued_clean = datetime(clean_day.year, clean_day.month, clean_day.day, 7, 0, tzinfo=NY) - timedelta(days=1)
reason_stale, t_stale = issuance(stale_mid, issued_stale)
reason_clean, t_clean = issuance(clean_day, issued_clean)

results = {
    "eval_days": len(rows),
    "hits": hits,
    "misses": misses,
    "false_alarms": false_alarms,
    "true_negatives": tn,
    "in_window_dist": dist(in_window),
    "out_window_dist": dist(out_window),
    "issuance_stale_day": {"date": stale_mid.isoformat(), "reason": reason_stale,
                           "stale_data_reason": reason_stale in ("stale_load", "stale_weather")},
    "issuance_clean_day": {"date": clean_day.isoformat(), "reason": reason_clean,
                           "normal_path": reason_clean not in ("stale_load", "stale_weather")},
    "rows": rows,
}
(ROOT / "run_results.json").write_text(json.dumps(results, indent=2, default=str))
print(json.dumps({k: results[k] for k in results if k != "rows"}, indent=2))