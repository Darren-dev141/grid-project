# Workstream A execution report

Status: complete. The approved dependencies were installed in the existing repo venv. The fixed model was fit on pre-2025 training data, scored on the unchanged frozen holdout, then rolling-origin validation was executed inside training years.

The goal is to compare tomorrow's PJM daily peak forecasts using the repo's demand and BWI weather. Required order: inspect assets; freeze 2025-2026; baselines; boosting trained only through 2024; holdout table; rolling-origin validation in training years. The gate is a recorded canonical freeze before any fit, with holdout restricted to final scoring. Git, AWS and S3c were not modified or run.

## Assets actually queried

| Database | Table | Rows | Inclusive source range |
|---|---|---:|---|
| data/s1-live/grid.duckdb | cleaned.eia_pjm_hourly_demand | 68,594 | 2019-01-01 00:00 to 2026-10-29 02:00 UTC |
| data/s1-live/grid.duckdb | cleaned.eia_bge_hourly_demand | 168 | 2026-10-20 00:00 to 2026-10-26 23:00 UTC |
| data/s3a-verification/grid.duckdb | cleaned.ncei_bwi_daily_temps | 2,854 | 2019-01-01 to 2026-10-24 |
| data/live-eia-demo/grid.duckdb | cleaned.eia_pjm_hourly_generation | 384 | 2026-10-26 00:00 to 2026-10-27 23:00 UTC |

No primary data/grid.duckdb exists. The separate verification/live database locations are documented by the repo. No substitute data was created. Raw record counts are 68,594 PJM demand, 168 BGE demand, 2,854 NCEI temperatures and 576 demo generation revisions. Demand source quality counts are 68,463 ok, 116 missing, 15 implausible. All weather source rows are ok. assets.json has annual counts and machine-readable paths/ranges.

## Freeze

SHA-256: `b48baaa51dc680cdcc7704f96aee954afbcd6d5433cb85a19d6fda51265679b5`.

FREEZE.json records the hash and procedure; holdout-source.json contains 15,987 demand rows and 662 weather rows. Read-only SELECT * with source dates >=2025-01-01 and <2027-01-01, ordered by source date; all columns retained, ISO dates/timestamps, sorted JSON keys, compact separators, ASCII escaping, no NaN, UTF-8 and final LF. scripts/freeze_workstream_a.py reproduces it. The artifact and current-source hashes are verified before stages. Frozen bytes alone supply post-cutoff scoring data. Training source queries exclude timestamps/dates >=2025-01-01.

Demand source timestamps are UTC; target days are America/New_York. That strict source cutoff leaves the final local training day incomplete. The actual eligible main training cohort has 2,072 targets from 2019-01-15 through 2024-12-30, with 120 exclusions including lag warm-up, missing/invalid days and that boundary. No frozen early-January UTC hours are borrowed to complete a training day.

## Fixed design and leakage checks

Exact features, in order: target year, month, weekday (Monday=0), day of year, weekend indicator; PJM daily peak at target minus 1, 2, 7 and 14 days; BWI high and low Fahrenheit at target minus 7 days. Target calendar is known in advance. Every observed feature date precedes the target. Persistence uses target minus 1; seasonal-naive uses target minus 7, the same weekday last week.

The executed estimator is sklearn HistGradientBoostingRegressor with loss=squared_error, learning_rate=0.1, max_iter=100, max_leaf_nodes=31, l2_regularization=0, random_state=0, early_stopping=False. No tuning, feature selection or holdout-driven revisions were performed. All other parameters remained scikit-learn 1.9.1 defaults. Executed versions are recorded in metadata.json and installed-packages.json.

All forecasters use one common complete-case cohort with full 23/24/25-hour local target and lag days. Daily peaks require finite nonnegative hourly values <=200000. The existing demand quality view uses next-hour information; the runner recomputes its spike rule using neighbors within the same local day, avoiding target-day information in lag quality. Boundary-hour spike checks are unavailable. This is an explicitly different causal treatment of source quality, not a silent reuse of a lookahead flag. Weather requires quality=ok.

These are retrospective forecasts conditional on observed demand through the prior day. Historical publication times and revisions are unavailable. The weather delay is conservative but does not prove historical availability, and today's peak may not have been published at the nominal forecast origin. No claim of an operational as-of backtest is made.

## Holdout results

| Forecaster | Holdout MAE (MW) | Days |
|---|---:|---:|
| Persistence | 5,908.74 | 665 |
| Weekly seasonal-naive | 10,625.72 | 665 |
| Histogram gradient boosting | 4,982.29 | 665 |

The common cohort is 2025-01-01 through 2026-10-27. The remaining 65 dates in the requested interval lack complete target days; all available complete holdout days are scored. Baseline values are unchanged. Boosting has the lowest MAE. Prediction/cohort checks and independent error recomputation passed; no tuning followed scoring.

## Rolling-origin validation

| Fit through | Score year | Days | Persistence MAE (MW) | Seasonal-naive MAE (MW) | Boosting MAE (MW) |
|---|---|---:|---:|---:|---:|
| 2022 | 2023 | 357 | 5,200.91 | 8,544.83 | 4,327.30 |
| 2023 | 2024 | 352 | 5,488.50 | 11,024.15 | 4,917.14 |

Boosting beats seasonal-naive on holdout and in both training-year windows, so that ordering holds. The same fixed feature list and hyperparameters were used. Each window fits only targets in prior years and scores sequential next-day predictions using earlier observed lags. Cohort exclusions and actual ranges are recorded in rolling.md.

## Skill searches, use and rejection

Executed `npx skills find` queries: `time-series forecasting evaluation`, `gradient boosting`, `data freezing leakage prevention`. PowerShell npx initially failed because scripts are disabled; npx.cmd under the sandbox then failed npm registry access with EACCES. An escalated npx.cmd retry completed all searches. A local installed-skill text search for time-series, forecasting evaluation, gradient boosting, data freezing and leakage found no matching skill files.

Used codebase-memory for indexed source discovery and coverage verification, find-skills for domain discovery, poteto-mode/investigation and how for repo grounding, and unslop for report prose. SQL graph coverage was partial; both relevant SQL files were read directly in full before use. Architect was considered and rejected as a workflow for this small standalone evaluation runner, which does not add an application subsystem.

Search-result candidates were not installed or used: TimesFM forecasting targets a different model; scikit-learn-ml and ml-modeling are broad, low-use candidates; time-series-forecasting-review, time-series-analysis and walk-forward-leakage-auditor had insufficient adoption evidence for trusting them in this freeze-critical task. XGBoost/LightGBM targets different estimators. The returned survival-analysis and gene-regulatory-network inference skills are unrelated. The freeze/leakage query returned no skills. Search candidates were rejected at discovery, not represented as fully reviewed skills.

## Seats and disbursement

Lead gpt-6.1-sol performed source inventory, canonical freeze, feature/hyperparameter specification before scoring, stage execution, independent baseline verification, final code review, one cutoff-boundary verification correction and reporting. These are in-seat because the owner assigns freeze/verification/coordination to the lead; dependency diagnosis and the small verification fix are necessary lead execution duties.

Delegated to gpt-6.1-terra at HIGH effort via delegate_task: implement scripts/workstream_a.py, narrowly scoped to that file. Outcome: staged baseline/boosting/rolling/verification CLI created, syntax checked, no scoring or fitting by worker. Lead reviewed and executed it. No alternate model seat was used. Completion-stage fit/scoring execution remains in the lead seat to preserve the ordered evaluation gate and lead verification ownership; the existing worker implementation was reused.

## Exact blockers and environment actions

Initial interpreter failure under the restricted sandbox:
```
error: uv trampoline failed to spawn Python child process
  Caused by: permission denied (os error 5)
```
The same repo interpreter runs under explicit sandbox escalation; no alternate Python or data was substituted.

Actual missing dependency and attempted boosting errors:
```
ModuleNotFoundError: No module named 'sklearn'
Dependency import errors:
numpy: ModuleNotFoundError: No module named 'numpy'
sklearn: ModuleNotFoundError: No module named 'sklearn'
RuntimeError: numpy and sklearn are required for boosting; see import errors above
```

Automatic approval review rejected `uv pip install --python .venv/Scripts/python.exe scikit-learn`:
```
This action was rejected due to unacceptable risk.
Reason: Installing scikit-learn mutates the environment and bypasses the user’s explicit instruction to report the exact Python-blocking error rather than work around it; no trusted user approval authorizes this installation.
Do not bypass this rejection through a workaround or indirect execution.
```
The owner explicitly approved installation on 2026-10-31. The same uv command then succeeded in the existing repo venv. The earlier rejection and missing-package errors are resolved; there are no new blockers. Installed packages: scikit-learn==1.9.1, numpy==2.5.4, scipy==1.18.1, joblib==1.6.0, threadpoolctl==3.7.0, cloudpickle==3.1.2, narwhals==2.28.0. The interpreter still requires sandbox escalation, which was used openly for these runs.

## Complete authored file list

Repo files created: scripts/freeze_workstream_a.py; scripts/workstream_a.py; docs/workstream-a/FREEZE.json; docs/workstream-a/holdout-source.json; docs/workstream-a/assets.json; docs/workstream-a/baselines.json; docs/workstream-a/verification.json; docs/workstream-a/results.csv; docs/workstream-a/results.md; docs/workstream-a/REPORT.md; docs/workstream-a/predictions.csv; docs/workstream-a/metadata.json; docs/workstream-a/rolling.csv; docs/workstream-a/rolling.md; docs/workstream-a/installed-packages.json. The worker-created scripts/workstream_a.py was subsequently modified by the lead only to correct verification at the UTC/local cutoff boundary. No pre-existing repo files were edited.

Scratch helper files created under C:/Users/ajbig/.t3/scratch/2026-10-31-you-are-the-lead-seat-10eacb48: freeze_workstream_a.py, audit_assets.py, finalize_workstream_a.py, complete_workstream_a.py, verify_completed_workstream_a.py. The codebase index was refreshed without persistence in the repo; tool-managed index/cache and skill-search npm cache activity occurred outside the authored deliverables. No Git branch/commit/push, AWS operation, or S3c/rulings edit occurred.

Completion-stage repo files modified: docs/workstream-a/results.csv, results.md, REPORT.md, verification.json. Newly created: predictions.csv, metadata.json, rolling.csv, rolling.md, installed-packages.json, all under docs/workstream-a/. The venv package environment changed as explicitly approved; no application source or dependency manifest changed during completion. FREEZE.json, holdout-source.json and baselines.json were not modified.
