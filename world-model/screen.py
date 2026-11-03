"""Plausibility screen with thresholds from training years only."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np


def _maxramp(hours):
    h = np.asarray(hours, float)
    if len(h) < 2:
        return 0.0
    return float(np.max(np.abs(np.diff(h))))


def load_gbm_band(repo_root: str = ".") -> dict:
    """Compute per-weather-bin GBM residual std from Workstream A artifacts if usable."""
    root = Path(repo_root)
    pred_path = root / "docs" / "workstream-a" / "predictions.csv"
    # weather by date from s3a db not loaded here; use training fallback caller supplies.
    # We only return residual std overall + maybe by month.
    band = {"overall_std": None, "by_month": {}}
    if not pred_path.exists():
        return band
    try:
        rows = list(csv.DictReader(pred_path.read_text().splitlines()))
    except Exception:
        return band
    resids = []
    for r in rows:
        try:
            actual = float(r["actual_mw"])
            boost = float(r["boosting"])
        except (KeyError, ValueError, TypeError):
            continue
        resids.append(actual - boost)
    if resids:
        band["overall_std"] = float(np.std(resids, ddof=1))
    # by month residual std
    by_month = {}
    for r in rows:
        try:
            d = r["date"]
            m = int(d[5:7])
            actual = float(r["actual_mw"]); boost = float(r["boosting"])
        except (KeyError, ValueError, TypeError):
            continue
        by_month.setdefault(m, []).append(actual - boost)
    for m, vals in by_month.items():
        if len(vals) > 1:
            band["by_month"][m] = float(np.std(vals, ddof=1))
    return band


def compute_thresholds(train_days: list[dict], repo_root: str = ".",
                      hourly_margin: float = 0.10, ramp_margin: float = 0.10,
                      ratio_margin: float = 0.05, sigma: float = 3.0) -> dict:
    hours_all = [h for d in train_days for h in d["hours"]]
    hmin, hmax = float(min(hours_all)), float(max(hours_all))
    hr = hmax - hmin
    hourly_lo = hmin - hourly_margin * hr
    hourly_hi = hmax + hourly_margin * hr

    ramps = [_maxramp(d["hours"]) for d in train_days]
    maxramp = float(max(ramps)) if ramps else 0.0
    ramp_limit = maxramp * (1.0 + ramp_margin)

    ratios = [float(sum(d["hours"]) / max(d["hours"])) for d in train_days]
    ratio_lo = float(min(ratios)); ratio_hi = float(max(ratios))
    rr = ratio_hi - ratio_lo
    ratio_lo -= ratio_margin * rr
    ratio_hi += ratio_margin * rr

    highs = np.array([float(d["high_f"]) for d in train_days])
    cutoffs = np.quantile(highs, [1/3, 2/3])
    # clean tertile bins: low / mid / high
    def _bin_index(hf):
        if hf <= float(cutoffs[0]):
            return 0
        if hf <= float(cutoffs[1]):
            return 1
        return 2
    bins = []
    for bi in range(3):
        members = [d for d in train_days if _bin_index(float(d["high_f"])) == bi]
        peaks = [float(max(d["hours"])) for d in members]
        train_std = float(np.std(peaks, ddof=1)) if len(peaks) > 1 else 0.0
        train_mean = float(np.mean(peaks)) if peaks else 0.0
        if bi == 0:
            hi = float(cutoffs[0]); lo = None
        elif bi == 1:
            lo = float(cutoffs[0]); hi = float(cutoffs[1])
        else:
            lo = float(cutoffs[1]); hi = None
        bins.append({
            "high_lo": lo,
            "high_hi": hi,
            "train_mean_peak": train_mean,
            "train_std_peak": train_std,
            "n": len(members),
        })

    gbm = load_gbm_band(repo_root)
    overall_gbm_std = gbm.get("overall_std")

    # GBM incumbent demonstrated error band (holdout residual std) used as checker.
    for b in bins:
        gbm_std = overall_gbm_std if overall_gbm_std is not None else b["train_std_peak"]
        half = sigma * max(b["train_std_peak"], gbm_std if gbm_std is not None else 0.0)
        if half == 0:
            half = sigma * (b["train_mean_peak"] * 0.1 if b["train_mean_peak"] else 1.0)
        b["gbm_std"] = gbm_std
        b["half_width"] = float(half)

    thresholds = {
        "hourly_margin": hourly_margin,
        "ramp_margin": ramp_margin,
        "ratio_margin": ratio_margin,
        "sigma": sigma,
        "hourly_lo": hourly_lo,
        "hourly_hi": hourly_hi,
        "ramp_limit": ramp_limit,
        "ratio_lo": ratio_lo,
        "ratio_hi": ratio_hi,
        "hot_cutoffs": [float(x) for x in cutoffs],
        "bins": bins,
        "gbm_band": gbm,
        "screen_version": "stage0-2026-11-02",
    }
    return thresholds


def _bin_for(day, thresholds):
    hf = float(day["high_f"])
    cutoffs = thresholds["hot_cutoffs"]
    if hf <= cutoffs[0]:
        return 0
    if hf <= cutoffs[1]:
        return 1
    return 2


def screen_one(day: dict, thresholds: dict) -> tuple[bool, list[str]]:
    reasons = []
    hours = [float(x) for x in day["hours"]]
    # hourly range
    if any(h < thresholds["hourly_lo"] or h > thresholds["hourly_hi"] for h in hours):
        reasons.append("hourly_range")
    # ramp
    if _maxramp(hours) > thresholds["ramp_limit"]:
        reasons.append("ramp")
    # energy-to-peak ratio
    ratio = float(sum(hours) / max(hours)) if max(hours) > 0 else 0.0
    if ratio < thresholds["ratio_lo"] or ratio > thresholds["ratio_hi"]:
        reasons.append("energy_peak_ratio")
    # load-weather consistency
    b = thresholds["bins"][_bin_for(day, thresholds)]
    peak = float(max(hours))
    lo = b["train_mean_peak"] - b["half_width"]
    hi = b["train_mean_peak"] + b["half_width"]
    if peak < lo or peak > hi:
        reasons.append("load_weather")
    return (len(reasons) == 0, reasons)


def screen_days(days: list[dict], thresholds: dict) -> dict:
    total = len(days)
    rejected = 0
    reasons_count = {}
    for d in days:
        ok, rs = screen_one(d, thresholds)
        if not ok:
            rejected += 1
        for r in rs:
            reasons_count[r] = reasons_count.get(r, 0) + 1
    rate = (rejected / total) if total else 0.0
    return {
        "total": total,
        "rejected": rejected,
        "rejection_rate": rate,
        "reasons": reasons_count,
    }


def save_thresholds(thresholds: dict, path: str):
    # convert numpy types
    def clean(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.ndarray,)):
            return [clean(x) for x in o.tolist()]
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(x) for x in o]
        return o
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(clean(thresholds), indent=2))


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--train", default="world-model/data/dayblocks/train.json")
    ap.add_argument("--out", default="world-model/data/screen_thresholds.json")
    args = ap.parse_args()
    root = Path(args.repo_root)
    train = json.loads((root / args.train).read_text())
    thr = compute_thresholds(train, str(root))
    save_thresholds(thr, str(root / args.out))
    print("thresholds saved")
    # quick screen on dev
    dev = json.loads((root / "world-model/data/dayblocks/dev.json").read_text())
    print(screen_days(dev, thr))
