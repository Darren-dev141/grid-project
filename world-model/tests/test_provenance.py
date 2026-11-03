import json
from pathlib import Path

import provenance

ROOT = Path(__file__).resolve().parents[2]
WM = Path(__file__).resolve().parents[1]


def test_is_learned_synthetic_detects():
    obj = {"provenance": {"source_type": "learned_synthetic"}}
    assert provenance.is_learned_synthetic(obj) is True


def test_is_real_not_synthetic():
    obj = {"provenance": {"source_type": "real"}}
    assert provenance.is_learned_synthetic(obj) is False


def test_refuse_synthetic_default():
    obj = {"provenance": {"source_type": "learned_synthetic"}}
    try:
        provenance.refuse_if_synthetic(obj, allow_synthetic=False)
        assert False, "expected ProvenanceError"
    except provenance.ProvenanceError:
        pass


def test_allow_synthetic_override():
    obj = {"provenance": {"source_type": "learned_synthetic"}}
    provenance.refuse_if_synthetic(obj, allow_synthetic=True)  # no raise


def test_guard_inputs_refuses():
    objs = [{"provenance": {"source_type": "real"}}, {"provenance": {"source_type": "learned_synthetic"}}]
    try:
        provenance.guard_inputs_for_scoring(objs)
        assert False, "expected ProvenanceError"
    except provenance.ProvenanceError:
        pass


def test_guard_allows_real():
    objs = [{"provenance": {"source_type": "real"}}]
    provenance.guard_inputs_for_scoring(objs)  # no raise


def test_assert_not_in_ledger_blocks():
    try:
        provenance.assert_not_in_ledger("ledger/foo.json", str(ROOT))
        assert False, "expected ProvenanceError"
    except provenance.ProvenanceError:
        pass


def test_assert_not_in_ledger_allows_generated():
    provenance.assert_not_in_ledger("world-model/generated/x.json", str(ROOT))  # no raise


def test_write_generated_artifact_stamps():
    p = WM / "generated" / "_test_artifact.json"
    if p.exists():
        p.unlink()
    prov = provenance.write_generated_artifact(
        str(p),
        {"value": 42},
        model_hash="hash123",
        training_window="2019-2024",
        recipe_id="stage0-test",
        fidelity_score=0.5,
        repo_root=str(ROOT),
    )
    assert prov["source_type"] == "learned_synthetic"
    data = json.loads(p.read_text())
    assert data["provenance"]["model_hash"] == "hash123"
    assert data["provenance"]["training_window"] == "2019-2024"
    assert data["provenance"]["recipe_id"] == "stage0-test"
    # cleanup
    p.unlink(missing_ok=True)


def test_write_generated_refuses_ledger_path():
    try:
        provenance.write_generated_artifact(
            "ledger/x.json",
            {"v": 1},
            model_hash="h",
            training_window="w",
            recipe_id="r",
            repo_root=str(ROOT),
        )
        assert False, "expected ProvenanceError"
    except provenance.ProvenanceError:
        pass
