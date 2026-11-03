"""Provenance plumbing for Stage 0 generated artifacts.

Every generated (learned_synthetic) artifact writer stamps provenance.
Generated data lives OUTSIDE ledger/ and all receipt paths.
Guard functions fail-closed: refuse learned_synthetic inputs by default.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOURCE_TYPE_LEARNED = "learned_synthetic"
SOURCE_TYPE_REAL = "real"

LEDGER_DIRNAME = "ledger"
RECEIPT_DIRNAME = "receipts"


class ProvenanceError(ValueError):
    """Raised when a provenance policy is violated."""


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_learned_synthetic(obj: Any) -> bool:
    """Detect a learned_synthetic artifact by its provenance stamp."""
    if not isinstance(obj, dict):
        return False
    prov = obj.get("provenance")
    if isinstance(prov, dict):
        if prov.get("source_type") == SOURCE_TYPE_LEARNED:
            return True
    if obj.get("source_type") == SOURCE_TYPE_LEARNED:
        return True
    # nested: list of records
    if isinstance(obj.get("records"), list):
        return any(is_learned_synthetic(r) for r in obj["records"])
    return False


def refuse_if_synthetic(obj: Any, *, allow_synthetic: bool = False) -> None:
    """Fail-closed guard: refuse learned_synthetic inputs unless explicitly allowed."""
    if is_learned_synthetic(obj) and not allow_synthetic:
        raise ProvenanceError(
            "learned_synthetic input refused by default (fail-closed); "
            "pass allow_synthetic=True to override"
        )


def guard_inputs_for_scoring(inputs: Any) -> None:
    """Scoring/brief code paths call this to refuse learned_synthetic inputs."""
    if isinstance(inputs, (list, tuple)):
        for x in inputs:
            refuse_if_synthetic(x, allow_synthetic=False)
    else:
        refuse_if_synthetic(inputs, allow_synthetic=False)


def assert_not_in_ledger(path: str | Path, repo_root: str | Path = ".") -> None:
    """Ensure a generated-data path does not live under ledger/ or receipts/."""
    root = Path(repo_root).resolve()
    p = Path(path)
    if not p.is_absolute():
        p = (root / p).resolve()
    try:
        rel = p.relative_to(root)
    except ValueError:
        rel = p
    parts = rel.parts
    if LEDGER_DIRNAME in parts or RECEIPT_DIRNAME in parts:
        raise ProvenanceError(f"generated data must not live under ledger/receipts: {path}")
    # also block any path containing 'ledger' segment
    if "ledger" in parts:
        raise ProvenanceError(f"generated data must not live under ledger: {path}")


def stamp_provenance(
    *,
    model_hash: str,
    training_window: str,
    recipe_id: str,
    fidelity_score: float | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prov = {
        "source_type": SOURCE_TYPE_LEARNED,
        "model_hash": model_hash,
        "training_window": training_window,
        "recipe_id": recipe_id,
        "fidelity_score": fidelity_score,
        "stamped_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        prov.update(extra)
    return prov


def write_generated_artifact(
    path: str | Path,
    data: Any,
    *,
    model_hash: str,
    training_window: str,
    recipe_id: str,
    fidelity_score: float | None = None,
    repo_root: str | Path = ".",
    extra_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a generated artifact with provenance stamp. Returns provenance dict."""
    assert_not_in_ledger(path, repo_root)
    out_path = Path(path)
    if not out_path.is_absolute():
        out_path = Path(repo_root) / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    prov = stamp_provenance(
        model_hash=model_hash,
        training_window=training_window,
        recipe_id=recipe_id,
        fidelity_score=fidelity_score,
        extra=extra_provenance,
    )

    if isinstance(data, dict):
        payload = dict(data)
        payload["provenance"] = prov
    else:
        payload = {"data": data, "provenance": prov}

    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return prov


if __name__ == "__main__":
    # smoke
    p = write_generated_artifact(
        "world-model/generated/_smoke.json",
        {"hello": "world"},
        model_hash="abc123",
        training_window="2019-2024",
        recipe_id="stage0-smoke",
        fidelity_score=0.0,
        repo_root=".",
    )
    print(p)
