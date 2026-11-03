# Diagnosis: stale_load on S3c issuances (2026-11-01, 2026-11-02)

Diagnosis only. No code, data, or commits changed.

## Failing check

Issuance entry point: `scripts/issue_stress.py` (run by Hermes cron job
`d977b52c965c`, "Grid S3c daily prospective issuance 07:00 ...", via
`grid_s3c_repo_launcher.py` with workdir = repo root).

Relevant code (issue_stress.py):

- `input_cutoff = min(issued_at, scheduled_cutoff)` (scheduled cutoff 07:00 ET)
- `latest_completed_peak = target_date - timedelta(days=2)`  (D-2 by design)
- `all_history = load_first_recorded_history(LOAD_DB, TEMP_DB, indexed_by=input_cutoff)`
- `target = by_date.get(target_date)`  (target_date == issuance date)
- `load_fresh = target is not None and target.load_first_recorded is True`
- `weather_fresh = target is not None and target.temperature_first_recorded is True`
- `Features(..., load_fresh=..., weather_fresh=..., mode="prospective", ...)`
- `stress.forecast` returns `no_call('stale_load' if not features.load_fresh else 'stale_weather', receipt)` when `not features.load_fresh or not features.weather_fresh`.

Staleness/recency rule applied upstream in `src/grid_pipeline/stress_inputs.py`:
`indexed_by` becomes a SQL cutoff `WHERE loaded_at <= TIMESTAMPTZ '<input_cutoff UTC>'`
on both `load_rows` and `temperature_rows`. Only committed raw rows whose
`loaded_at` is at or before the issuance cutoff are eligible, and a target day
counts as fresh only if it survives that filter with `load_first_recorded is True`.

Second rule (stress.py, prospective history gate, quoted):
`_aware(features.issued_at) and day.date <= features.issued_at.astimezone(ZoneInfo('America/New_York')).date() - timedelta(days=2)`
i.e. D-2 is the latest completed peak, by design.

Which check failed on Nov 2: `load_fresh` (and consequently `weather_fresh`)
for target_date 2026-11-02. `target` was `None` because no history row exists
for 2026-11-02; `all_history`'s latest date is 2026-10-28. `stale_load`
takes precedence over `stale_weather` in stress.py, so the artifact records
`stale_load`.

## Failing input: location, last update, updater

Load input (EIA PJM demand):
- Path: `C:\Users\ajbig\Documents\grid-project\data\s1-live\grid.duckdb`
  (raw batches/records, cleaned mart).
- Last committed batch `loaded_at`: 2026-10-29 06:56:23 EDT.
- Max EIA period in raw records: 2026-10-29T02:00 UTC (2026-10-28 22:00 EDT).
- Latest history/mart day: 2026-10-28 (incomplete).
- Raw files on disk: 17 EIA JSONs, newest mtime 2026-10-29 06:55.

Temperature input (NCEI BWI daily summaries):
- Path: `C:\Users\ajbig\Documents\grid-project\data\s3a-verification\grid.duckdb`.
- Last committed batch `loaded_at`: 2026-10-29 09:09:29 EDT.
- Max NCEI daily summary date: 2026-10-24.
- Latest history day with temperature: 2026-10-24.

Updater / process:
- Intended: the scheduled daily run fetches EIA/NCEI/NWS, builds dbt, then
  issues. Per PLAN.md that runner is GitHub Actions, but no `.github/workflows/daily.yml`
  exists; only CI (`ci.yml`) exists. The actual scheduler is Hermes cron on the PC.
- Cron job `d977b52c965c` (0 7 * * *) runs only `grid_s3c_repo_launcher.py`
  -> `scripts/issue_stress.py`. It does NOT fetch or build data. No data refresh
  step exists in the scheduled path.
- Evidence of no refresh: no files under `data/` have mtime on/after 2026-11-01;
  EIA/NCEI last committed batches are 2026-10-29.
- Nov 1: cron job `f15a60000b7f` ran the stale Hermes copy
  `AppData/Local/hermes/scripts/issue_stress.py` and failed with
  `ModuleNotFoundError: No module named 'grid_pipeline'` (exit 1) at 07:00.
  Salvage run at 11:15 succeeded in writing the artifact but was UNSCORED/stale_load.
- Nov 2: cron job `d977...` ran the repo launcher at 07:00:15; script exited 2
  with `Issuance no-call: ... reason=stale_load`, writing
  `docs/s3c/S3C-FIRST-ISSUANCE-2026-11-02.json` (issued_late true,
  latest_completed_peak_date 2026-10-31, input_availability_verified false).

## Context vs. D-2 design

D-2 latest completed peak is by design (S3C rulings, 2026-10-31): for a
forecast issued on day D, D-2 is the latest completed peak; history is filtered
to `day.date <= issued_at.date() - 2 days`. On Nov 2 that bound is 2026-10-31.

Classification:
- (a) Data genuinely older than design allows: YES, partially. EIA history
  stops at 2026-10-28 and NCEI at 2026-10-24, roughly 3 days short of the
  2026-10-31 bound. A refresh is required.
- (b) Availability verification failing for a non-data reason: NO. The check
  reads the databases successfully; `Path.resolve(strict=True)` and the
  `load_first_recorded` flag are populated. No path/credential/module error
  occurs on the Nov 2 path.
- (c) Rule/threshold mis-set relative to D-2 design: YES, and this is the
  blocking cause. `load_fresh` requires the TARGET day (today, 2026-11-02) to
  be present in history with `load_first_recorded is True`. But by the D-2
  design the target day is never in the completed-peak history, and its observed
  NCEI daily temperature cannot exist at 07:00 on that day. Therefore
  `load_fresh` is False for every on-time issuance regardless of data currency;
  the check is testing the wrong day. Even with perfectly current data through
  2026-10-31, target 2026-11-02 would still be absent and the result would
  still be `stale_load`.

Additional gate: `stress.forecast` prospective mode unconditionally returns
`no_call('unverified_issue_time_availability', ...)` after the freshness and
weather checks, and `input_availability_verified` is hardcoded False. So
`stale_load` is only the first of two blockers; fixing data currency alone
would surface `unverified_issue_time_availability`, not a SCORED forecast.

ModuleNotFoundError class (Nov 1): the stale Hermes copy problem is resolved
for the scheduled path (Nov 2 uses the repo launcher + repo `.venv`), but it is
not fully eliminated: the stale copy still exists at
`AppData/Local/hermes/scripts/issue_stress.py`, and the disabled one-shot job
`f15a60000b7f` still references it. A manual or misconfigured run could
reproduce it.

## Smallest fix to make tomorrow's issuance score (described, not applied)

1. Refresh data through D-2: run the EIA backfill (`grid-backfill`) and NCEI
   fetch (`grid-weather`/`grid-temps`) so `data/s1-live` and
   `data/s3a-verification` cover through 2026-10-31, then rebuild dbt.
   (Or add a fetch+build step to the cron/GitHub Actions runner; currently none.)
2. In `scripts/issue_stress.py`, stop gating freshness on the target day:
   - `load_fresh` should reflect availability of completed history through
     `latest_completed_peak` (D-2), not `target.load_first_recorded`.
   - Target weather (`high_f`, `morning_low_f`, `weather_available_at`) must
     come from the NWS forecast for target_date with its real issuance time,
     not from NCEI observed daily temps (which do not exist yet).
3. In `src/grid_pipeline/stress.py`, prospective mode must permit a SCORED
   result when `weather_available_at` is a verified NWS issuance time at or
   before `issued_at`, instead of unconditionally returning
   `unverified_issue_time_availability`. Until this lands, even a correct
   availability stamp yields UNSCORED.

Without (2) and (3), refreshing data alone will not produce a scored
issuance.
EOF
echo written