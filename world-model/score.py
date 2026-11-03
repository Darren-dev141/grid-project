"""Fidelity score harness: five frozen components, equal weights."""
from __future__ import annotations

from typing import Any

import numpy as np


def _peaks(days):
    return np.array([float(max(d["hours"])) for d in days], dtype=float)


def _maxramps(days):
    out = []
    for d in days:
        h = np.asarray(d["hours"], dtype=float)
        out.append(float(np.max(np.abs(np.diff(h)))) if len(h) > 1 else 0.0)
    return np.array(out, dtype=float)


def _peakhours(days):
    return np.array([int(np.argmax(d["hours"])) for d in days], dtype=int)


def _slope_peak_vs_high(days):
    highs = np.array([float(d["high_f"]) for d in days], dtype=float)
    peaks = _peaks(days)
    if len(days) < 2 or np.std(highs) == 0:
        return 0.0
    # simple linear slope
    x = highs - highs.mean()
    y = peaks - peaks.mean()
    denom = float(np.dot(x, x))
    if denom == 0:
        return 0.0
    return float(np.dot(x, y) / denom)


def _tv_peakhour(gen_days, real_days):
    bins = 24
    def hist(days):
        h = _peakhours(days)
        counts = np.zeros(bins)
        for v in h:
            counts[v % bins] += 1
        if counts.sum() == 0:
            return counts
        return counts / counts.sum()
    pg = hist(gen_days)
    pr = hist(real_days)
    return float(0.5 * np.sum(np.abs(pg - pr)))


def stress_threshold(train_days, q=0.9):
    peaks = [float(max(d["hours"])) for d in train_days]
    return float(np.quantile(peaks, q))


def hot_cutoff(train_days, q=0.6666667):
    highs = [float(d["high_f"]) for d in train_days]
    return float(np.quantile(highs, q))


def score(real_days, gen_days, anchor_days, train_days, seed_info=None):
    """Return dict with per-component skills, composite, and details."""
    if len(real_days) < 20:
        raise ValueError("need at least 20 day-blocks per slice")
    if not (len(real_days) == len(gen_days) == len(anchor_days)):
        raise ValueError("length mismatch between real/gen/anchor")

    thr = stress_threshold(train_days, 0.9)
    hot_cut = hot_cutoff(train_days, 2.0/3.0)

    # hot strata indices based on REAL day weather (matched)
    hot_idx = [i for i, d in enumerate(real_days) if float(d["high_f"]) >= hot_cut]

    def stress_rate(days, idx):
        if not idx:
            return 0.0
        peaks = [float(max(days[i]["hours"])) for i in idx]
        return float(np.mean([1.0 if p >= thr else 0.0 for p in peaks]))

    rate_real = stress_rate(real_days, hot_idx)
    rate_gen = stress_rate(gen_days, hot_idx)
    rate_anchor = stress_rate(anchor_days, hot_idx)

    # Component 1 hourly MAE
    def hourly_mae(a_days, b_days):
        errs = []
        for a, b in zip(a_days, b_days):
            ha = np.asarray(a["hours"], float)
            hb = np.asarray(b["hours"], float)
            errs.append(float(np.mean(np.abs(ha - hb))))
        return float(np.mean(errs)) if errs else 0.0

    mae_gen = hourly_mae(gen_days, real_days)
    mae_anchor = hourly_mae(anchor_days, real_days)
    skill1 = 1.0 - (mae_gen / mae_anchor) if mae_anchor > 0 else 0.0
    skill1 = float(np.clip(skill1, -1.0, 1.0))

    # Component 2 peak
    peak_gen_err = float(np.mean(np.abs(_peaks(gen_days) - _peaks(real_days))))
    peak_anchor_err = float(np.mean(np.abs(_peaks(anchor_days) - _peaks(real_days))))
    skill2 = 1.0 - (peak_gen_err / peak_anchor_err) if peak_anchor_err > 0 else 0.0
    skill2 = float(np.clip(skill2, -1.0, 1.0))
    peak_bias_gen = float(np.mean(_peaks(gen_days) - _peaks(real_days)))
    peak_bias_anchor = float(np.mean(_peaks(anchor_days) - _peaks(real_days)))

    # Component 3 stress rate
    err_gen3 = abs(rate_gen - rate_real)
    err_anchor3 = abs(rate_anchor - rate_real)
    if err_anchor3 > 0:
        skill3 = 1.0 - (err_gen3 / err_anchor3)
    else:
        skill3 = 1.0 if err_gen3 == 0 else 0.0
    skill3 = float(np.clip(skill3, -1.0, 1.0))

    # Component 4 ramp + peak hour
    ramp_gen_err = float(np.mean(np.abs(_maxramps(gen_days) - _maxramps(real_days))))
    ramp_anchor_err = float(np.mean(np.abs(_maxramps(anchor_days) - _maxramps(real_days))))
    tv_gen = _tv_peakhour(gen_days, real_days)
    tv_anchor = _tv_peakhour(anchor_days, real_days)
    err4_gen = ramp_gen_err + tv_gen
    err4_anchor = ramp_anchor_err + tv_anchor
    if err4_anchor > 0:
        skill4 = 1.0 - (err4_gen / err4_anchor)
    else:
        skill4 = 1.0 if err4_gen == 0 else 0.0
    skill4 = float(np.clip(skill4, -1.0, 1.0))

    # Component 5 load-weather consistency (slope)
    slope_real = _slope_peak_vs_high(real_days)
    slope_gen = _slope_peak_vs_high(gen_days)
    slope_anchor = _slope_peak_vs_high(anchor_days)
    err5_gen = abs(slope_gen - slope_real)
    err5_anchor = abs(slope_anchor - slope_real)
    if err5_anchor > 0:
        skill5 = 1.0 - (err5_gen / err5_anchor)
    else:
        skill5 = 1.0 if err5_gen == 0 else 0.0
    skill5 = float(np.clip(skill5, -1.0, 1.0))

    composite = float(np.mean([skill1, skill2, skill3, skill4, skill5]))

    details = {
        "hourly_mae_gen": mae_gen,
        "hourly_mae_anchor": mae_anchor,
        "peak_mae_gen": peak_gen_err,
        "peak_mae_anchor": peak_anchor_err,
        "peak_bias_gen": peak_bias_gen,
        "peak_bias_anchor": peak_bias_anchor,
        "stress_threshold": thr,
        "hot_cutoff": hot_cut,
        "n_hot_days": len(hot_idx),
        "stress_rate_real": rate_real,
        "stress_rate_gen": rate_gen,
        "stress_rate_anchor": rate_anchor,
        "ramp_mae_gen": ramp_gen_err,
        "ramp_mae_anchor": ramp_anchor_err,
        "tv_peakhour_gen": tv_gen,
        "tv_peakhour_anchor": tv_anchor,
        "slope_real": slope_real,
        "slope_gen": slope_gen,
        "slope_anchor": slope_anchor,
        "n_days": len(real_days),
    }
    components = {
        "hourly_trajectory_mae": skill1,
        "peak_abs_error_bias": skill2,
        "stress_day_rate": skill3,
        "ramp_peakhour_dist": skill4,
        "load_weather_consistency": skill5,
    }
    return {
        "components": components,
        "composite": composite,
        "details": details,
    }


def three_seed_mean(real_days, gen_fn, anchor_days, train_days, seeds=(0, 1, 2)):
    """gen_fn: callable(seed) -> list of gen days. Returns mean composite over seeds."""
    comps = []
    for s in seeds:
        gen = gen_fn(s)
        r = score(real_days, gen, anchor_days, train_days)
        comps.append(r["composite"])
    return float(np.mean(comps)), [float(c) for c in comps]
