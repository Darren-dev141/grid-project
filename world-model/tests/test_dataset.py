import json
from pathlib import Path

import dataset

ROOT = Path(__file__).resolve().parents[2]
WM = Path(__file__).resolve().parents[1]


def test_build_without_sealed_has_no_sealed_key():
    data = dataset.build_dayblocks(str(ROOT), include_sealed=False)
    assert "sealed" not in data
    assert set(data.keys()) == {"train", "dev"}


def test_train_years_le_2024():
    data = dataset.build_dayblocks(str(ROOT), include_sealed=False)
    for s in data["train"]:
        assert s["year"] <= 2024


def test_dev_year_2025():
    data = dataset.build_dayblocks(str(ROOT), include_sealed=False)
    for s in data["dev"]:
        assert s["year"] == 2025


def test_load_split_train_no_sealed_years():
    rows = dataset.load_split(str(ROOT), "train", allow_sealed=False)
    assert all(r["year"] <= 2024 for r in rows)


def test_load_split_sealed_requires_flag():
    try:
        dataset.load_split(str(ROOT), "sealed", allow_sealed=False)
        assert False, "expected PermissionError"
    except PermissionError:
        pass


def test_load_split_sealed_with_flag_count():
    rows = dataset.load_split(str(ROOT), "sealed", allow_sealed=True)
    assert len(rows) >= 20
    assert all(r["year"] == 2026 for r in rows)


def test_split_enforcement_train_cannot_see_2025_2026():
    # a "train" consumer cannot access 2025/2026 via train split
    rows = dataset.load_split(str(ROOT), "train", allow_sealed=False)
    assert not any(r["year"] >= 2025 for r in rows)


def test_hourly_length():
    data = dataset.build_dayblocks(str(ROOT), include_sealed=False)
    for split in ("train", "dev"):
        for s in data[split]:
            assert len(s["hours"]) == 24
