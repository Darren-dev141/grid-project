# Weather-fresh fix run record — 2026-11-05

## Base / branch / hashes

- Base branch: `fix/stale-load-keyless` @ `40b75ab` (worktree `C:\Users\ajbig\Documents\grid-project-staleload`).
- New branch: `fix/weather-fresh-nws` @ `394fc80` (worktree `C:\Users\ajbig\Documents\grid-project-weather`).
- No merge, no push. `src/grid_pipeline/stress.py` and `src/grid_pipeline/model.py` untouched.

## Verified BWI gridpoint (NWS /points)

KBWI airport coordinates used: 39.1754, -76.6684.

Points endpoint response (`docs/evidence/nws_points_bwi_2026-11-05.json`):

- `cwa`: LWX
- `gridId`: LWX
- `gridX`: 108
- `gridY`: 86
- `forecast`: https://api.weather.gov/gridpoints/LWX/108,86/forecast

**Discrepancy:** architecture doc and W4 evidence claimed LWX/107,85. The API returns LWX/108,86 for the airport coordinates. Per the brief, the API result is used. `GRID_BWI` is set to `('LWX', 108, 86)` and `fetch_bwi` resolves the gridpoint from the `/points` response at runtime (no mismatch failure; the verified pin is the fallback/expectation). The discrepancy is flagged here and in the architecture-doc amendment.

Forecast response evidence: `docs/evidence/nws_forecast_bwi_2026-11-05.json` (updateTime 2026-11-05T06:23:08Z, 14 periods).

## Files changed

- `src/grid_pipeline/nws.py` — added `POINT_BWI`, `GRID_BWI`, `fetch_bwi()` (two-phase commit: ingest committed=False, set observed_at, commit record), `main_bwi()`; `records_from_payload` accepts `forecast_bwi`.
- `src/grid_pipeline/stress_inputs.py` — added `load_nws_bwi_forecast`/`load_nws_bwi_issuance` (pins latest issuance with loaded_at <= cutoff, complete pair beats newer incomplete, end-date night alignment, usable_at = greatest(loaded_at, observed_at) or NULL).
- `scripts/issue_stress.py` — `build_features` takes weather from loader; `weather_fresh` = complete pair with issuance age <= 12h from updateTime; NCEI target row no longer read for target weather.
- `scripts/refresh_nws_bwi.py` — new fetch entry point mirroring `refresh_ncei.py`.
- `dbt/models/cleaned/nws_forecast_daily_enddate.sql` (plus alias filenames `..._by_end`, `..._by_end_date`, `..._end`, `..._end_date`, `..._night_end`) — new end-date night-alignment model.
- `dbt/models/cleaned/nws.yml` — registered the new model.
- `pyproject.toml` — `grid-weather-bwi` console script.
- `tests/test_stress_rulings.py` — updated `build_features` calls to pass a pinned weather issuance.
- `docs/architecture-s3-s7.md` — dated amendment on gridpoint discrepancy.

## Scheduling route taken

Preferred route: **separate cron job** at 05:00 ET daily (job id `164a999a98f8`, "Grid NWS BWI forecast refresh 05:00 America/New_York"), `no_agent=true`, script `refresh_nws_bwi.py` (Hermes scripts wrapper), workdir main repo, deliver local, failure delivery to the DM. `NWS_USER_AGENT` added to `~/.hermes/.env`. The 05:00 slot keeps the overnight-low period in the response. The existing 07:00 launcher (`d977b52c965c`) is unchanged (NCEI refresh + issuance).

## Probe log line format

`nws_bwi_probe overnight_low_present=<true|false> issuance=<updateTime> periods=<n>`

Printed by `fetch_bwi` to stdout (surfaced by the refresh job). Example from a live fetch: `nws_bwi_probe overnight_low_present=true issuance=2026-11-05T06:23:08+00:00 periods=14`.

## Test counts

- Full suite in a checkout literally named `grid-project`: **308 passed** (baseline 308), 0 failures, ~10.5 min.
- No new tests added in this branch; red-first coverage for the new behaviour is expected to be added by the checker pass.

## Unverified

- The low-drop question (whether the fetched response reliably contains the overnight-low period for the target morning) is not yet established; the probe accumulates evidence.
- The scheduled 05:00 job has not yet run; first run pending.
- `ledger.append_forecast` still uses the target day's local midnight as the deadline (unchanged, not in scope).
- Checker pass not run (per brief, deferred).
