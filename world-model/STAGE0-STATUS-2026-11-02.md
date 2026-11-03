# STAGE 0 STATUS REPORT — Grid world model

Date: 2026-11-02

## Restatement (Stage 0)

Stage 0 builds the measurement apparatus for a future grid world model without
training a model: a day-block dataset, a trivial seasonal-naive anchor
generator, a five-component fidelity score, a plausibility screen with frozen
training-year thresholds, and provenance plumbing. It must prove the anchor
scores ~0 against itself, a perfect copy scores ~1, real dev days pass the
screen at ~0 rejection, splits are enforced, the sealed 2026 slice is never
scored/peeked, and all tests pass.

## Inventory of halted session (partial files)

Found under world-model/ (no STAGE0-HALTED-2026-11-02.md present):
- __init__.py, dataset.py, anchor.py, score.py, screen.py (kept; sound and
  consistent with brief)
- data/dayblocks/train.json (2160), dev.json (365), sealed.json (297)
- data/, generated/, tests/ (empty)

Kept sound files; rebuilt train/dev via builder (byte-identical to existing);
left sealed.json untouched (existence + count only). Added provenance.py,
tests/, STAGE0-FREEZE, STAGE0-STATUS. No duplication.

## What was built (paths)

- world-model/dataset.py (day-block builder, split enforcement)
- world-model/anchor.py (seasonal-naive anchor)
- world-model/score.py (five-component fidelity harness)
- world-model/screen.py (plausibility screen)
- world-model/provenance.py (provenance plumbing + guard)
- world-model/tests/ (test_score, test_dataset, test_screen, test_provenance, conftest)
- world-model/data/dayblocks/{train,dev,sealed}.json
- world-model/data/screen_thresholds.json
- world-model/STAGE0-FREEZE-2026-11-02.md
- world-model/STAGE0-STATUS-2026-11-02.md

## Freeze hash + dataset counts

- Freeze document SHA-256: 58bd702b5b492116491bbf6bb4bae8c30af3769224463ab6f6a33633d987aa37
- train: 2160 (2019-2024)
- dev: 365 (2025)
- sealed: 297 (2026, untouched)

## Self-check numbers (dev slice, sealed untouched)

- anchor scored against itself: composite = 0.0
- perfect machinery (gen == real): composite = 1.0
- screen rejection on real dev days: 10 / 365 = 0.0274 (2.74%)
- three-seed mean (anchor): -0.0668 [0.0, -0.0794, -0.1209]

## Test results

- 31 tests, exit code 0 (all green).

## Screen rejection rate on real dev days

- 10 / 365 = 2.74%, all due to load_weather (cold/hot extremes outside
  3-sigma GBM band).

## Blocked / ambiguous

- S3c stress threshold mapping ambiguous; used 90th percentile of training
  peaks (stress-index-v1 strained percentile). Reported.
- GBM checker: no callable model artifact; implemented from holdout residual
  statistics (overall std ~6558 MW from predictions.csv). Reported.
- No model trained (Stage 1 separate gate).

## Confirmation: 2026 values never scored

The sealed 2026 slice was never loaded for scoring, peeked, or used in any
self-check beyond existence and count (297 rows, year 2026). No aggregate
statistics of sealed values were computed.
