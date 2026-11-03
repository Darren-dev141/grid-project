import json
from pathlib import Path

import numpy as np

import score
import anchor
import dataset

ROOT = Path(__file__).resolve().parents[2]
WM = Path(__file__).resolve().parents[1]


def _load(split):
    return json.loads((WM / "data" / "dayblocks" / f"{split}.json").read_text())


def test_sample_size_rule():
    train = _load("train")
    dev = _load("dev")
    assert len(train) >= 20
    assert len(dev) >= 20


def test_score_anchor_vs_itself_zero():
    train = _load("train")
    dev = _load("dev")
    # anchor generated for dev targets
    gen = anchor.generate_days(dev, train, seed=0)
    res = score.score(dev, gen, gen, train)
    # model==anchor => every skill ~0
    for k, v in res["components"].items():
        assert abs(v) < 1e-9, (k, v)
    assert abs(res["composite"]) < 1e-9


def test_score_perfect_model_one():
    train = _load("train")
    dev = _load("dev")
    # model == real => skill ~1
    res = score.score(dev, dev, anchor.generate_days(dev, train, seed=0), train)
    for k, v in res["components"].items():
        assert v > 0.999, (k, v)
    assert res["composite"] > 0.999


def test_score_length_mismatch():
    train = _load("train")
    dev = _load("dev")
    gen = anchor.generate_days(dev, train, seed=0)
    try:
        score.score(dev, gen[:-1], gen, train)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_score_min_slice():
    train = _load("train")
    dev = _load("dev")[:5]
    gen = anchor.generate_days(dev, train, seed=0)
    try:
        score.score(dev, gen, gen, train)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_three_seed_mean_runs():
    train = _load("train")
    dev = _load("dev")
    targets = dev
    def gen_fn(s):
        return anchor.generate_days(targets, train, seed=s)
    anchor_days = anchor.generate_days(targets, train, seed=0)
    mean, vals = score.three_seed_mean(dev, gen_fn, anchor_days, train, seeds=(0, 1, 2))
    assert len(vals) == 3
    assert isinstance(mean, float)


def test_stress_threshold_from_train():
    train = _load("train")
    thr = score.stress_threshold(train, 0.9)
    peaks = [max(d["hours"]) for d in train]
    assert abs(thr - float(np.quantile(peaks, 0.9))) < 1e-9
