import json
from pathlib import Path

import screen

ROOT = Path(__file__).resolve().parents[2]
WM = Path(__file__).resolve().parents[1]


def test_screen_thresholds_from_train():
    train = json.loads((WM / "data" / "dayblocks" / "train.json").read_text())
    thr = screen.compute_thresholds(train, str(ROOT))
    assert thr["hourly_lo"] < thr["hourly_hi"]
    assert thr["ramp_limit"] > 0


def test_screen_dev_rejection_rate_reported():
    train = json.loads((WM / "data" / "dayblocks" / "train.json").read_text())
    dev = json.loads((WM / "data" / "dayblocks" / "dev.json").read_text())
    thr = screen.compute_thresholds(train, str(ROOT))
    res = screen.screen_days(dev, thr)
    # ~0: report actual; assert not catastrophic
    assert res["rejection_rate"] < 0.10
