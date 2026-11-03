import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dataset


def test_split_enforcement_no_sealed_by_default():
    # load_split sealed without flag raises
    try:
        dataset.load_split(".", "sealed", allow_sealed=False)
    except PermissionError:
        pass
    else:
        raise AssertionError("expected PermissionError")


def test_train_cannot_see_2025_2026():
    train = dataset.load_split(".", "train")
    years = {r["year"] for r in train}
    assert max(years) <= 2024
    assert 2025 not in years
    assert 2026 not in years


def test_dev_is_2025():
    dev = dataset.load_split(".", "dev")
    assert all(r["year"] == 2025 for r in dev)
    assert len(dev) >= 20


def test_sealed_flag():
    sealed = dataset.load_split(".", "sealed", allow_sealed=True)
    assert all(r["year"] == 2026 for r in sealed)
    assert len(sealed) >= 20
    # existence check only; do not inspect values beyond count
