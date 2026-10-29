# Architecture for S3 to S7 (proposal, October 29, 2026)

Status: **proposal**. Three owner decisions are open (end of this file). Nothing
here is built yet.

Two design candidates were sketched independently, then compared:

- **A, dbt-centric.** Forecaster, index, scoring and scorecard in SQL models; the
  ledger is read back into dbt as a source over the committed files.
- **B, Python core.** dbt stays the cleaning layer and exposes one feature mart.
  The forecaster is pure Python over typed values. One `ledger` module owns the
  receipt files.

**Chosen: B's structure with A's single entry point.** The reasons are in
"Why this shape".

## Caller's usage

```
grid daily                      # one scheduled run, start to finish
grid weekly                     # Mondays: scorecard for the last ISO week
grid ledger verify --since origin/main   # CI on every push, and a pre-commit hook
git add ledger site && git commit -m "brief <date>" && git push
```

`grid daily` runs, in order:
1. fetch `pjm-demand`, NWS and BWI observed temperatures;
2. `dbt build`;
3. freshness;
4. forecast tomorrow;
5. `ledger.append`;
6. score settled days;
7. render the brief to `site/`;
8. post it as a comment on a pinned GitHub issue.

The issue comment notifies Darren through GitHub, with no email address or mail secret in the repo.

Stale inputs do not skip the forecast. They write a **no-call** receipt with a reason (`stale_load`, `stale_weather`), so a miss is on the record too.

Adding PJM's official forecast later takes one new file. `forecasters/pjm.py` turns the lawful feed into a `Forecast` with `forecaster_id="pjm"`, and `grid daily` appends it. Scoring and the scorecard group by `forecaster_id`. There is no list to update.

## Types

Receipt file, written once:
`ledger/forecasts/<forecaster_id>/<target_date>/<issued_at:%Y%m%dT%H%M%SZ>_<sha256[:12]>.json`.
The hash in the filename covers the canonical JSON bytes, so the name certifies the
content.

```
schema: 1
forecaster_id, forecaster_version
definition: {version, sha256}              # null for external forecasters
issued_at_utc, target_date_local, tz: "America/New_York"
geography: {target: "PJM RTO (EIA-930 PJM/D)", weather: "NWS LWX/100,98 point; BWI history"}
claims: {peak_mw, peak_hour_local, level}  # each nullable; all null = no-call
thresholds_mw: {watch, strained, severe}   # frozen at issue time
drivers: [{name, value, effect_mw}]
inputs: {weather_issuance_id, demand_last_hour_utc, history_digest}
no_call_reason: null | "stale_load" | "stale_weather"
```

The index definition is `ledger/definitions/stress-index-v1.toml`. It is read with stdlib `tomllib`, and each receipt carries the sha256 of the raw bytes. Its sections:

| Section | What it sets |
| --- | --- |
| `[window]` | Days either side of the date, history years, weekday/weekend split |
| `[temperature]` | Cooling and heating hinge bases (F) |
| `[levels]` | Percentile cut points |
| `[alerts]` | An active heat/cold alert raises the level one step |
| `[peak_hour]` | Number of analog days |
| `[scoring]` | Peak-hour tolerance and settle days |

An amendment adds a v2 file next to v1. It never edits v1. Each version is published as `docs/index/<version>.md`.

Python types (frozen dataclasses): `Level` (calm, watch, strained, severe), `Definition`, `DayHistory`, `Features`, `Forecast`, `Actual`, `Score`, `Scorecard`, `Brief`.

## Signatures

| Module | Function | Behavior |
| --- | --- | --- |
| `stress` (pure) | `parse_definition(raw: bytes) -> Definition` | Validates every field; carries the sha256 |
| `stress` (pure) | `forecast(f: Features, d: Definition) -> Forecast` | Seasonal window, degree-hinge least squares on BWI history, percentile thresholds, analog peak hour, alert bump |
| `scoring` (pure) | `score(fc: Forecast, actual: Actual) -> Score` | The actual level uses the receipt's own frozen thresholds |
| `scoring` (pure) | `scorecard(scores, week) -> Scorecard` | Peak-hour hit rate, peak-MW MAE, stress-day precision/recall, per forecaster |
| `brief` (pure) | `render(call, yesterday: list[Score], fresh: Report) -> Brief` | Fixed template |
| `features` (IO) | `load(conn, target: date, as_of: datetime) -> Features` | The only SQL into the marts; pins the latest NWS issuance before `as_of` |
| `features` (IO) | `actuals(conn, dates) -> dict[date, Actual]` | Complete days only (23, 24 or 25 ok hours) |
| `ledger` | `append(root, fc) -> Path` | `open('xb')`; rejects `issued_at` at or after the target day's local midnight |
| `ledger` | `entries(root) -> list[Forecast]` | Verifies every filename hash while reading |
| `ledger` | `definition(root, version) -> Definition` | Loads a published definition |
| `ledger` | `verify(repo, since) -> list[Violation]` | Any non-add git change under `ledger/`, any hash mismatch, any late issue |
| `freshness` (rewritten) | `check(conn, now) -> Report` | Load, weather and forecast lag; price and renewables removed |
| `ncei` | `fetch(root, start, end)` | Keyless BWI daily summaries, landed via `storage.ingest` |

The receipt "of record" for a forecaster and target date is the latest one issued before the target day starts. It is a fixed rule, so there is nothing to cherry-pick.

## Module map

```
run.py  (grid daily | weekly | ledger verify | replay; replaces cli.py)
  -> fetch.py, nws.py, ncei.py -> storage.py
  -> features.py, freshness.py   (DuckDB reads)
  -> ledger.py                   (only reader/writer of ledger/)
  -> stress.py, scoring.py, brief.py   (pure; import none of the IO modules)
dbt: raw -> cleaned (eia_*, nws_*, ncei_bwi_daily_temps) -> mart_day_history
```

`mart_day_history` holds one row per local date: PJM peak MW, peak hour, completeness and the BWI observed high and low. The forecast weather comes from the existing `nws_forecast_daily`.

## Why this shape

- **Shallower to call, deeper to own.** The caller sees three commands. The modelling sits behind one pure `forecast(features, definition)` that tests can drive in milliseconds, so strict TDD stays fast. A puts the same logic in CTEs, where a wrong call means reading SQL and every test needs a real dbt build (about 5 s each here: 24 dbt tests ran in 126 s).
- **One owner per piece of state.**
  - Receipts and definitions: `ledger`.
  - The warehouse: dbt.
  - `site/`: regenerable output, not a receipt.

  A reads the receipt format in both Python (verify) and dbt (source). That is a hand-synced schema, and A's own critique flags it.
- **Frozen thresholds in each receipt.** An amended definition can never rescore an old call.
- **Taken from A:**
  - One entry point instead of a seven-line shell script.
  - The pinned-issue notification.
  - Every receipt carries both geographies.

## Gaps, handled

1. **Temperature history.** Verified on October 29 that NOAA NCEI daily summaries for BWI (`USW00093721`) answer with no key, from 2019-01-01, with the latest day about 5 days behind. That is enough to fit the temperature term. If you decline this source, v0 uses demand-only seasonal percentiles, temperature enters only through the alert bump, and a temperature model comes later as a published v1 amendment.
2. **Geography.** Every receipt and every brief says "PJM-wide call, Maryland weather". Scoring uses PJM RTO demand only. BGE stays display-only trailing color, never a claim. The scorecard reports residual against temperature, so a weak Maryland-to-PJM link shows up as numbers, not hidden tuning.
3. **Runner.** See decision 2 below.
4. **Immutability, enforced.**
   - Content-addressed names.
   - Exclusive create.
   - `ledger verify` in CI as a required check, and as a pre-commit hook.
   - It scans the full `git log --diff-filter=DMRT -- ledger/`.
   - Branch protection blocks force-push.

   Commit dates can be forged; the GitHub push event is the third-party timestamp.
5. **Retired v1 pieces.**
   - Tag `v1-final` first.
   - Then delete `pjm_bge_hourly_price`, `serving.grid_hourly`, `publish.py` and the `grid-publish` script, and their tests.
   - Fuel mix stays, as a possible brief driver.
   - `storage` keeps accepting `pjm`, so the old raw bytes stay replayable.

## Known weaknesses

- Python cannot block an import of `ledger` internals. A test will assert that no other module opens paths under `ledger/`.
- `nws_forecast_latest` picks issuances in SQL, while `features.load` pins by `as_of`. The view becomes display-only, and the docs say so.
- `storage` hard-codes its source names. Adding `ncei` edits that set. It is the one remaining list a new source must touch.
- EIA revises history. Scores wait `settle_days`, and each scorecard prints the actuals digest.

## Build order (TDD, one commit each)

| Step | Delivers |
| --- | --- |
| S3a | `ncei` source, `cleaned.ncei_bwi_daily_temps` |
| S3b | `mart_day_history` |
| S3c | `stress.py`, `stress-index-v1.toml`, `docs/index/v1.md`; settle the "low = night starting that date" convention here |
| S4 | `ledger.py` with `verify`, CI workflow, pre-commit hook |
| S5 | `features`, rewritten `freshness`, `brief`, `grid daily`, v1 deletion |
| S6 | `scoring`, `grid weekly` |
| S7 | Docs; the resume gate counts receipts, not intentions |

## Owner decisions

1. **Add NOAA NCEI BWI daily temperatures as the history source?** Default: yes. It is keyless and verified above.
2. **Who runs `grid daily`?**
   - **GitHub Actions** (free on a public repo): GitHub's push time is the timestamp proof, and it runs when the PC is off. It needs the EIA key as a repo secret, and `feat/energy-ingestion` merged to `main`.
   - **PC Task Scheduler**: no new secret anywhere, but runs are missed when the PC is off or the VPN blocks.
3. **Delete the v1 price pieces** after tagging `v1-final`? Default: yes. The plan says they are retired.
