"""Trivial-generator anchor: seasonal-naive resampling of training years."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


def _rng_for(date_str: str, seed: int) -> np.random.Generator:
    h = hashlib.sha256(f"{date_str}:{seed}".encode()).hexdigest()
    return np.random.default_rng(int(h[:16], 16))


def _candidates(train_days: list[dict], target: dict) -> list[dict]:
    same_md = [d for d in train_days
               if d["month"] == target["month"] and d["dayofweek"] == target["dayofweek"]]
    if same_md:
        return same_md
    same_m = [d for d in train_days if d["month"] == target["month"]]
    if same_m:
        return same_m
    return train_days


def generate_one(target: dict, train_days: list[dict], seed: int = 0) -> dict:
    cands = _candidates(train_days, target)
    rng = _rng_for(target["date"], seed)
    pick = cands[int(rng.integers(len(cands)))]
    return {
        "date": target["date"],
        "hours": [float(x) for x in pick["hours"]],
        "high_f": target["high_f"],
        "low_f": target["low_f"],
    }


def generate_days(targets: list[dict], train_days: list[dict],
                  seed: int = 0) -> list[dict]:
    return [generate_one(t, train_days, seed) for t in targets]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--train", default="world-model/data/dayblocks/train.json")
    ap.add_argument("--targets", default="world-model/data/dayblocks/dev.json")
    ap.add_argument("--out", default="world-model/generated/anchor_dev.json")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    root = Path(args.repo_root)
    train = json.loads((root / args.train).read_text())
    targets = json.loads((root / args.targets).read_text())
    gen = generate_days(targets, train, args.seed)
    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(gen, indent=2))
    print("wrote", len(gen), "to", out_path)
