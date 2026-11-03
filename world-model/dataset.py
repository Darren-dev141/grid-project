"""Day-block dataset builder for Stage 0.

One sample = one day: 24 hourly PJM load values + conditioning
(BWI high/low, calendar features, prior-7-day context).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

PJM_DB = "data/s1-live/grid.duckdb"
WEATHER_DB = "data/s3a-verification/grid.duckdb"

HOURLY = 24


def _load_pjm_hourly(db_path: str) -> dict[date, list[tuple[datetime, float]]]:
    con = duckdb.connect(db_path, read_only=True)
    rows = con.execute(
        "SELECT hour_utc, demand_mwh, quality FROM cleaned.eia_pjm_hourly_demand "
        "WHERE respondent='PJM' OR respondent IS NULL"
    ).fetchall()
    con.close()
    # group by local date (America/New_York) using hour-ending convention:
    # assign each interval to local date immediately before its ending instant.
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/New_York")
    by_date: dict[date, list[tuple[datetime, float]]] = {}
    for hour_utc, demand, quality in rows:
        if quality != "ok" or demand is None:
            continue
        try:
            v = float(demand)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(v) or v < 0:
            continue
        ending_local = hour_utc.astimezone(tz)
        # hour-ending: interval belongs to date before ending instant
        # if ending at midnight, belongs to previous date
        if ending_local.hour == 0 and ending_local.minute == 0:
            d = (ending_local - timedelta(days=1)).date()
        else:
            d = ending_local.date()
        by_date.setdefault(d, []).append((hour_utc, v))
    return by_date


def _load_weather(db_path: str) -> dict[date, tuple[float, float]]:
    con = duckdb.connect(db_path, read_only=True)
    rows = con.execute(
        "SELECT local_date, high_f, low_f, quality FROM cleaned.ncei_bwi_daily_temps"
    ).fetchall()
    con.close()
    out = {}
    for d, hi, lo, q in rows:
        if q != "ok" or hi is None or lo is None:
            continue
        try:
            hi_f = float(hi); lo_f = float(lo)
        except (TypeError, ValueError):
            continue
        if not (np.isfinite(hi_f) and np.isfinite(lo_f)):
            continue
        out[d] = (hi_f, lo_f)
    return out


def build_dayblocks(repo_root: str = ".", include_sealed: bool = False) -> dict[str, list[dict]]:
    """Build day-block samples split by year. Sealed (2026) only if include_sealed."""
    root = Path(repo_root)
    pjm_db = str(root / PJM_DB)
    wx_db = str(root / WEATHER_DB)

    hourly_by_date = _load_pjm_hourly(pjm_db)
    weather = _load_weather(wx_db)

    # candidate complete days: exactly 24 usable hours
    candidates = []
    for d, vals in hourly_by_date.items():
        if len(vals) != HOURLY:
            continue
        if d not in weather:
            continue
        # sort by utc time
        vals_sorted = sorted(vals, key=lambda x: x[0])
        hours = [v for _, v in vals_sorted]
        if len(hours) != HOURLY:
            continue
        hi, lo = weather[d]
        candidates.append((d, hours, hi, lo))

    candidates.sort(key=lambda x: x[0])

    # Build prior-7 context: previous 7 candidate days (all complete)
    date_set = {c[0] for c in candidates}
    idx = {c[0]: i for i, c in enumerate(candidates)}

    samples = []
    for i, (d, hours, hi, lo) in enumerate(candidates):
        if i < 7:
            continue
        prior = candidates[i - 7:i]
        # require contiguous-ish: previous 7 in candidate list
        prior_peaks = [float(max(c[1])) for c in prior]
        prior_highs = [float(c[2]) for c in prior]
        prior_lows = [float(c[3]) for c in prior]
        samples.append({
            "date": d.isoformat(),
            "year": d.year,
            "hours": [float(x) for x in hours],
            "high_f": hi,
            "low_f": lo,
            "month": d.month,
            "dayofweek": d.weekday(),
            "dayofyear": d.timetuple().tm_yday,
            "weekend": int(d.weekday() >= 5),
            "prior_7_peaks": prior_peaks,
            "prior_7_highs": prior_highs,
            "prior_7_lows": prior_lows,
        })

    train = [s for s in samples if s["year"] <= 2024]
    dev = [s for s in samples if s["year"] == 2025]
    sealed = [s for s in samples if s["year"] == 2026]

    out = {"train": train, "dev": dev}
    if include_sealed:
        out["sealed"] = sealed
    return out


def save_splits(repo_root: str = ".", out_dir: str = "world-model/data/dayblocks",
                include_sealed: bool = False) -> dict[str, int]:
    root = Path(repo_root)
    data = build_dayblocks(repo_root, include_sealed=include_sealed)
    out = root / out_dir
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for split, rows in data.items():
        path = out / f"{split}.json"
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        counts[split] = len(rows)
    return counts


def load_split(repo_root: str = ".", split: str = "train",
               allow_sealed: bool = False,
               out_dir: str = "world-model/data/dayblocks") -> list[dict]:
    """Load a split. Sealed requires allow_sealed=True (explicit flag)."""
    if split == "sealed" and not allow_sealed:
        raise PermissionError("sealed 2026 slice requires allow_sealed=True")
    root = Path(repo_root)
    path = root / out_dir / f"{split}.json"
    if not path.exists():
        raise FileNotFoundError(f"split file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--out-dir", default="world-model/data/dayblocks")
    ap.add_argument("--include-sealed", action="store_true",
                    help="Explicit flag to build sealed 2026 slice")
    args = ap.parse_args()
    counts = save_splits(args.repo_root, args.out_dir, args.include_sealed)
    print(counts)
