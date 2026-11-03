# STAGE 0 FREEZE — Grid world model (harness + freeze, no learned model)

Date: 2026-11-02
Scope: Stage 0 only. No model trained. Harness/score/screen/dataset code frozen after this document.

## 1. Restatement (Stage 0)

Stage 0 builds the measurement apparatus for a future grid world model without
training one: a day-block dataset, a trivial seasonal-naive anchor generator,
a five-component fidelity score, a plausibility screen, and provenance plumbing.
It must prove the anchor scores ~0 against itself, a perfect copy scores ~1,
real dev days pass the screen at ~0 rejection, splits are enforced, and the
sealed 2026 slice is never scored.

## 2. Splits

- Train: days with year <= 2024 (2160 day-blocks).
- Dev: days with year == 2025 (365 day-blocks).
- Sealed: days with year == 2026 (297 day-blocks), behind explicit flag
  `include_sealed=True` / `allow_sealed=True`. Never scored in Stage 0.

Enforced by construction: `build_dayblocks` returns sealed only when
`include_sealed=True`; `load_split("sealed")` raises unless `allow_sealed=True`.
Train/dev queries exclude 2025/2026.

## 3. Day-block sample

One sample = one day: 24 hourly PJM load values (MW) + conditioning
(BWI high/low F, calendar features, prior-7-day context). Source:
`data/s1-live/grid.duckdb` (cleaned.eia_pjm_hourly_demand) and
`data/s3a-verification/grid.duckdb` (cleaned.ncei_bwi_daily_temps).
No re-scraping; existing pipeline outputs only.

## 4. Trivial-generator anchor

Seasonal-naive resampling of training years: for each target day, candidate
training days with same month and weekday; fallback to same month, then all
training days; deterministic pick via SHA-256(date:seed). Score's 0 anchor.

## 5. Fidelity score — five components, EQUAL weights (1/5 each)

Composite = mean of five skill scores, each clipped to [-1, 1]:
skill = 1 - (model_error / anchor_error), with safe division.

1. hourly_trajectory_mae: hourly MAE between generated and real day (matched
   order/weather/calendar).
2. peak_abs_error_bias: mean absolute peak error (signed bias also reported).
3. stress_day_rate: |generated stress rate - real stress rate| over matched hot
   strata, divided by anchor gap. Stress threshold = 90th percentile of training
   daily peaks (ambiguous S3c mapping reported; stress-index-v1 strained
   percentile = 90). Hot stratum = training high-temp upper tertile (high_f >=
   2/3 quantile of training highs).
4. ramp_peakhour_dist: (ramp MAE + total-variation peak-hour histogram distance).
5. load_weather_consistency: |generated slope(peak vs high_f) - real slope|.

Three-seed mean rule: report mean composite over seeds (0,1,2); gen_fn(seed)
produces generated days; anchor_days fixed (seed 0).

Sample-size rule: at least 20 day-blocks per slice (enforced in `score()`).

## 6. Plausibility screen (thresholds from training years only)

Margins (frozen):
- hourly_margin = 0.10 (widens observed hourly range by 10% of range)
- ramp_margin = 0.10 (largest observed ramp * 1.10)
- ratio_margin = 0.05 (energy-to-peak ratio range widened by 5%)
- sigma = 3.0 (load-weather GBM band)

Checks:
- hourly load within [min - 0.10*range, max + 0.10*range]
- max hour-to-hour ramp <= 1.10 * largest observed ramp
- daily energy-to-peak ratio within observed range +/- 0.05*range
- load-weather: generated peak within train-mean-peak +/- 3*max(train_std_peak,
  gbm_residual_std) for its high-temp tertile bin. GBM checker implemented from
  holdout error statistics (docs/workstream-a/predictions.csv residual std
  ~6558 MW) because no callable GBM model artifact exists; reported as such.

Rejection rate is always reported.

## 7. Provenance plumbing

- Generated artifacts stamped: source_type=learned_synthetic, model hash,
  training window, recipe id, fidelity score, timestamp.
- Generated data directory: world-model/generated/ (outside ledger/ and receipts/).
- Guard function `guard_inputs_for_scoring` fails closed on learned_synthetic
  inputs; unit test proves refusal.

## 8. Code hashes (SHA-256)

- world-model/dataset.py: 6a2ec60b006e0d25c869e475ae02662e90ff7c8587b15621bda09d2c380967da
- world-model/anchor.py: 3971a7149a848d4a1063fff15f0ec803085e94b18b2cbe7c5f29907764476c01
- world-model/score.py: 4db48c631603dc45e45e66cbd5d0704ecec9fbc78ac13c28b1881afbb78503c2
- world-model/screen.py: a666610e367de6196dbc0136fbd57db48480f3940ed01e5c05e837519d603905
- world-model/provenance.py: b1b31ff4e41eaadad58980267aae99c5f1d61873c6470b850b09a015b65f60eb
- world-model/__init__.py: fc70cc366c2fa7426c411c63f91d0a300c6785347de2787f1d755bb5d001ae04

## 9. Dataset row counts

- train: 2160
- dev: 365
- sealed: 297 (not scored)

## 10. Self-check (dev slice, sealed untouched)

- anchor scored against itself: composite = 0.0
- perfect machinery (gen == real): composite = 1.0
- screen rejection on real dev days: 10 / 365 = 0.0274 (2.74%)
- three-seed mean (anchor): -0.0668

## 11. Ambiguities reported

- S3c stress thresholds: "stress-day" mapping ambiguous. Used 90th percentile of
  training daily peaks as the stress threshold (stress-index-v1 strained
  percentile = 90). Hot weather strata by training high-temp upper tertile.
- GBM checker: no callable model artifact; implemented from holdout residual
  statistics (overall std ~6558 MW from predictions.csv). Reported as such.
- Screen load-weather 3-sigma band rejects 2.74% of real dev days (10/365);
  reported actual rate.

After this freeze, harness/score/screen/dataset code is frozen; any change
requires a new freeze version.
