"""Seeded synthetic twin generator for the grid pipeline."""
from __future__ import annotations

import csv
import json
import math
import random
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import duckdb

SEED = 20261102
EVAL_START = date(2026, 9, 1)
EVAL_END = date(2026, 10, 30)
HISTORY_START = date(2025, 1, 1)
HISTORY_END = date(2026, 10, 31)
STALE_START = date(2026, 10, 20)
STALE_END = date(2026, 10, 22)

HEATWAVE_1 = {"onset": datetime(2026, 9, 15, 12, 0, tzinfo=ZoneInfo("America/New_York")),
              "duration_hours": 48, "peak_load_uplift_pct": 18.0}
HEATWAVE_2 = {"onset": datetime(2026, 10, 5, 10, 0, tzinfo=ZoneInfo("America/New_York")),
              "duration_hours": 72, "peak_load_uplift_pct": 15.0}
OUTAGE = {"onset": datetime(2026, 9, 28, 6, 0, tzinfo=ZoneInfo("America/New_York")),
          "duration_hours": 12, "capacity_drop_mw": 1800.0}

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
LOAD_DB = DATA / "load.duckdb"
TEMP_DB = DATA / "temperature.duckdb"
MANIFEST = ROOT / "truth_manifest.json"

NY = ZoneInfo("America/New_York")
UTC = timezone.utc
EIA_DATASET = "electricity/rto/region-data"
NCEI_DATASET = "daily-summaries"


def day_start_utc(d):
    return datetime.combine(d, time.min, NY).astimezone(UTC)


def hour_list_for_day(d):
    start = day_start_utc(d)
    end = day_start_utc(d + timedelta(days=1))
    n = int((end - start).total_seconds() // 3600)
    return [start + timedelta(hours=i) for i in range(n)]


def temperature_for_day(d, rng_gen):
    doy = d.timetuple().tm_yday
    base_high = 55 + 25 * math.sin(2 * math.pi * (doy - 100) / 365.0)
    base_low = base_high - 18
    uplift = 0.0
    for hw in (HEATWAVE_1, HEATWAVE_2):
        onset = hw["onset"].astimezone(UTC)
        end = onset + timedelta(hours=hw["duration_hours"])
        day_start = day_start_utc(d)
        day_end = day_start + timedelta(days=1)
        if day_start < end and day_end > onset:
            uplift = max(uplift, hw["peak_load_uplift_pct"] / 100.0 * 8.0)
    high = base_high + uplift + float(rng_gen.normal(0, 3))
    low = base_low + uplift * 0.4 + float(rng_gen.normal(0, 2.5))
    high = round(high, 1)
    low = round(low, 1)
    if low > high:
        low = high - 5
    return high, low


def load_profile(hour_local, weekend):
    profile = [0.72, 0.68, 0.66, 0.65, 0.66, 0.70, 0.78, 0.86, 0.92, 0.95,
               0.97, 0.99, 1.00, 0.99, 0.98, 0.97, 0.96, 0.97, 0.99, 1.00,
               0.96, 0.90, 0.82, 0.76]
    base = profile[hour_local] * 95000.0
    if weekend:
        base *= 0.90
    return base


def in_interval(dt, onset, hours):
    end = onset + timedelta(hours=hours)
    return onset <= dt < end


def make_db(path):
    with duckdb.connect(str(path)) as c:
        c.execute("CREATE SCHEMA raw")
        c.execute("""CREATE TABLE raw.batches (
            source VARCHAR, dataset VARCHAR, digest VARCHAR, path VARCHAR,
            loaded_at TIMESTAMPTZ, committed BOOLEAN, observed_at TIMESTAMPTZ,
            PRIMARY KEY (source, dataset, digest))""")
        c.execute("""CREATE TABLE raw.records (
            source VARCHAR, dataset VARCHAR, digest VARCHAR, row_number INTEGER,
            payload JSON, PRIMARY KEY (source, dataset, digest, row_number))""")


def generate():
    random.seed(SEED)
    np.random.seed(SEED)
    rng_gen = np.random.default_rng(SEED)
    DATA.mkdir(parents=True, exist_ok=True)

    for p in (LOAD_DB, TEMP_DB):
        if p.exists():
            p.unlink()
    make_db(LOAD_DB)
    make_db(TEMP_DB)

    all_days = [HISTORY_START + timedelta(days=i)
                for i in range((HISTORY_END - HISTORY_START).days + 1)]

    load_conn = duckdb.connect(str(LOAD_DB))
    temp_conn = duckdb.connect(str(TEMP_DB))
    load_conn.execute("BEGIN")
    temp_conn.execute("BEGIN")

    load_feed_rows_all = []
    temp_feed_rows_all = []

    try:
        for d in all_days:
            stale = STALE_START <= d <= STALE_END
            if stale:
                loaded_at = day_start_utc(d) + timedelta(days=7)
            else:
                loaded_at = day_start_utc(d) - timedelta(days=1)

            high, low = temperature_for_day(d, rng_gen)
            temp_row = {"DATE": d.isoformat(), "STATION": "USW00093721",
                        "TMAX": str(high), "TMIN": str(low),
                        "TMAX_ATTRIBUTES": ",,W", "TMIN_ATTRIBUTES": ",,W"}
            temp_feed_rows_all.append(temp_row)

            is_weekend = d.weekday() >= 5
            day_rows = []
            for hr_utc in hour_list_for_day(d):
                hr_local = hr_utc.astimezone(NY).hour
                base = load_profile(hr_local, is_weekend)
                temp = high if hr_local in range(12, 18) else (high + low) / 2
                weather_effect = 1.0 + 0.004 * max(0, temp - 65) + 0.002 * max(0, 50 - temp)
                val = base * weather_effect
                for hw in (HEATWAVE_1, HEATWAVE_2):
                    onset_utc = hw["onset"].astimezone(UTC)
                    if in_interval(hr_utc, onset_utc, hw["duration_hours"]):
                        val *= (1 + hw["peak_load_uplift_pct"] / 100.0)
                val += float(rng_gen.normal(0, 1200))
                val = max(50000, val)
                row = {"period": hr_utc.strftime("%Y-%m-%dT%H"), "respondent": "PJM",
                       "type": "D", "value": round(val, 1), "value-units": "megawatthours"}
                day_rows.append(row)
                load_feed_rows_all.append(row)

            digest_l = "load-" + d.isoformat()
            load_conn.execute("INSERT INTO raw.batches VALUES (?,?,?,?,?,?,?)",
                              ["eia", EIA_DATASET, digest_l, "", loaded_at, True, loaded_at])
            load_conn.executemany("INSERT INTO raw.records VALUES (?,?,?,?,?)", [
                ("eia", EIA_DATASET, digest_l, i, json.dumps(row)) for i, row in enumerate(day_rows)])

            digest_t = "temp-" + d.isoformat()
            temp_conn.execute("INSERT INTO raw.batches VALUES (?,?,?,?,?,?,?)",
                              ["ncei", NCEI_DATASET, digest_t, "", loaded_at, True, loaded_at])
            temp_conn.executemany("INSERT INTO raw.records VALUES (?,?,?,?,?)", [
                ("ncei", NCEI_DATASET, digest_t, 0, json.dumps(temp_row))])
    finally:
        load_conn.execute("COMMIT")
        temp_conn.execute("COMMIT")
        load_conn.close()
        temp_conn.close()

    load_envelope = {"response": {"data": load_feed_rows_all}}
    temp_envelope = {"response": {"data": temp_feed_rows_all}}
    (ROOT / "feed_load.json").write_text(json.dumps(load_envelope))
    (ROOT / "feed_temperature.json").write_text(json.dumps(temp_envelope))

    with open(ROOT / "interchange_series.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "interchange_mw"])
        for d in all_days:
            for hr_utc in hour_list_for_day(d):
                w.writerow([hr_utc.isoformat(), round(5000 + 3000 * math.sin(hr_utc.hour / 24.0 * 2 * math.pi) + float(rng_gen.normal(0, 500)), 1)])

    manifest = {
        "seed": SEED,
        "generator": "generator.py",
        "history_start": HISTORY_START.isoformat(),
        "history_end": HISTORY_END.isoformat(),
        "evaluation_window": {"start": EVAL_START.isoformat(), "end": EVAL_END.isoformat(),
                             "days": (EVAL_END - EVAL_START).days + 1},
        "stale_gap": {"start": STALE_START.isoformat(), "end": STALE_END.isoformat()},
        "heatwaves": [
            {"onset_local": HEATWAVE_1["onset"].isoformat(), "duration_hours": HEATWAVE_1["duration_hours"],
             "peak_load_uplift_pct": HEATWAVE_1["peak_load_uplift_pct"]},
            {"onset_local": HEATWAVE_2["onset"].isoformat(), "duration_hours": HEATWAVE_2["duration_hours"],
             "peak_load_uplift_pct": HEATWAVE_2["peak_load_uplift_pct"]},
        ],
        "plant_outage": {"onset_local": OUTAGE["onset"].isoformat(), "duration_hours": OUTAGE["duration_hours"],
                         "capacity_drop_mw": OUTAGE["capacity_drop_mw"]},
        "params": {"base_load_mw": 95000, "weather_sensitivity": 0.004, "noise_std_mw": 1200,
                   "temp_noise_std_f": 3.0},
        "files": {"load_db": str(LOAD_DB), "temperature_db": str(TEMP_DB),
                  "feed_load": str(ROOT / "feed_load.json"),
                  "feed_temperature": str(ROOT / "feed_temperature.json"),
                  "interchange": str(ROOT / "interchange_series.csv")},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print("generated", LOAD_DB, TEMP_DB, MANIFEST)


if __name__ == "__main__":
    generate()

