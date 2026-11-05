# Architecture for S3 to S7 (revision 2, October 29, 2026)

Status: **design accepted for build, pending one more review round.**
- S3a (NCEI history) is implemented and verified ([S3a notes](s3a-ncei.md)).
- This revision applies the EGM review
  ([consolidated report](reviews/egm-architecture-s3-s7/consolidated_review_report.md))
  and the facts measured on October 29 ([Evidence](#evidence-behind-this-revision)).
- Purpose, audience and owner decisions live in `PLAN.md`; this file says how the
  build works.

> **Darren's ruling, Nov 5, 2026: SAME-DAY — the 07:00 job forecasts today's peak;
> freshness judged on completed history through target − 2.** `target_date` is the
> issue day D. Issuance must be at or before the 07:00 America/New_York cutoff on
> the target day and before that day's peak; the D−2 latest-completed-peak rule is
> unchanged. This supersedes the next-day issuance wording below ("a call for
> tomorrow", "Forecast tomorrow", the append refusal "at or after the start of the
> target day", and the 17:17 EDT afternoon cron under Schedule). Those passages are
> amended inline where they state the semantics; the Schedule and the `ledger`
> No-backdating rule (target day not started by the verifier's clock) are design
> text for the not-yet-built S4/S5 runner and are **not** re-planned here. In code,
> `stress.forecast` and `scripts/issue_stress.py` follow the ruling (W2);
> `ledger.append_forecast` and `ledger verify` still use the target day's local
> midnight as the deadline and are not yet aligned.

## Objective

S3 to S7 turn the ingested data into a daily public forecast with receipts:

1. Each morning, by the 07:00 America/New_York cutoff, publish a call for that
   day's PJM-wide peak demand, peak hour and stress level. *(Amended Nov 5, 2026,
   same-day ruling; was "each afternoon ... tomorrow's".)*
2. Write that call to a file that can never be quietly changed.
3. Score it against EIA actuals once the day has passed.

The point is a checkable track record. Anyone can see every call, including the
misses, and confirm that nothing was edited or backdated. The brief's reader is
Darren's household (Darren owns the project). The public page is a byproduct.

Terms used below:

| Term | Meaning |
| --- | --- |
| **PJM** | The regional grid operator covering Maryland. |
| **BGE** | Baltimore Gas and Electric, the local utility zone. Its demand data runs about 2 days behind, so the brief shows it as background only and never scores it. |
| **S3 to S7** | The build stages in [Build order](#build-order). |
| **Legacy v1 pipeline** | The retired price and Power BI code. It is unrelated to *stress index v1*, the first published index definition. |

## Design in one paragraph

- dbt cleans raw data and builds one daily history table. Pure Python modules
  make the forecast, score it and render the brief.
- One module, `ledger`, is the only code that reads or writes the committed
  receipt files.
- One scheduled GitHub Actions workflow runs the whole day: fetch, build,
  forecast, verify, commit, publish.
- Two candidates were compared before choosing this shape (dbt-centric vs Python
  core; see [Why this shape](#why-this-shape)).

## Caller's usage

The scheduled workflow (`.github/workflows/daily.yml`) runs:

```sh
grid daily        # fetch, build, forecast, append receipt, verify, render brief
git push          # only if `grid daily` exited 0
```

A deploy step then publishes `site/` to GitHub Pages from a workflow artifact,
and a final step posts the brief as a comment on the pinned issue.

The weekly workflow runs `grid weekly` on Tuesdays and posts the scorecard the
same way. The other commands are for people:

```sh
grid ledger verify --new-since <sha>   # what the daily job runs before its push
grid replay <source> <dataset> <file>  # re-ingest a saved response
```

The existing manual tools stay: `grid-fetch`, `grid-backfill`, `grid-weather`
and `grid-temps`. `grid-publish` and `grid-freshness` go away with the legacy v1
pipeline.

`grid daily` steps, in order. Any failure stops the run before `git push`.

1. **Fetch:**
   - PJM demand for the last 3 years plus 30 days, using `fetch_cli.backfill`
     (it resumes from the checkpoint when the warehouse is cached);
   - BGE demand for the last 7 days;
   - NCEI BWI daily temperatures for the same span as PJM demand, as 366-day
     requests (about 4);
   - the NWS forecast for **two points**: BWI (gridpoint LWX/107,85, used by the
     model) and Reisterstown (LWX/100,98, the household line);
   - NWS alerts for Reisterstown, recorded per target local date as validation/display annotations only; they never affect the stress level.
2. **Build:** `warehouse.build(database)` runs `dbt build`, with up to 3 attempts
   on the known dbt `send_bytes()` failure.
3. **Check freshness** (`freshness.check`), which returns a `Report`:
   - the PJM load is stale if the last ok hour is older than 3 hours;
   - the BWI forecast is stale if it was issued more than 12 hours ago or is
     missing the target date's high or the night before it;
   - the NCEI history lag is reported, but it does not block the forecast.
4. **Forecast the target day (same-day):** *(Amended Nov 5, 2026; was "Forecast
   tomorrow".)*
   - `features.load(conn, target, as_of=now)`, then
     `stress.forecast(features, definition)`;
   - stale load or stale weather produces a no-call with that reason.
5. **Append:** `ledger.append(fc)`. It refuses if this forecaster already has a
   receipt for that target date, and refuses an issue time after the 07:00
   America/New_York cutoff on the target day. *(Amended Nov 5, 2026; was "at or
   after the start of the target day". `ledger.append_forecast` has not been
   changed and still refuses after the target day began.)*
6. **Verify:** run `ledger.verify(new_since=<origin/main at job start>)`, then
   commit `ledger/` only.
7. **Score yesterday, provisionally:** `scoring.score` using provisional
   actuals.
8. **Render:** `brief.render` writes `site/index.html` and the issue-comment
   text. The comment lists each new receipt's path and full sha256.

**Owner setup before the first scheduled run.** These are outward-facing, so each
is confirmed with Darren at the time.

- Merge `feat/energy-ingestion` to `main`. Scheduled workflows run only on the
  default branch.
- Add repo secret `EIA_API_KEY`.
- Add repo variables `NWS_USER_AGENT` and `BRIEF_ISSUE`, the number of a pinned
  issue Darren creates.
- Set Pages source to "GitHub Actions".
- Protect `main` (see [Integrity](#integrity)).

## Integrity

What the receipts can prove, and how:

- **Receipts are only ever added.**
  - `ledger.append` uses exclusive create.
  - `ledger.verify` scans the full `git log -m --diff-filter=DMRT -- ledger/` and
    fails on any change that is not an add. `-m` includes merge commits.
  - `main` is protected against force-push and deletion, with admins included.
  - It has **no required status check**. GitHub rejects a direct push to a branch
    whose required check has not yet passed, and on a personal repo Actions
    cannot be a bypass actor (W2).
- **Content matches its name.** Every file's full sha256 must start with the
  12-hex-character prefix in its filename. The hash covers the file's bytes as
  written; no canonical JSON form is needed.
- **No backdating.**
  - For receipts added in the commits being pushed, `verify` checks that the
    target day had not started by the *verifier's* clock.
  - It does not trust the receipt's own `issued_at`.
  - Receipts outside that range were checked when they were added. Checking them
    against today's clock would flag every old receipt.
- **A third-party timestamp.**
  - The issue comment lists each new receipt's sha256.
  - GitHub sets the comment's `created_at`; the API offers no way to set it.
  - Edits are visible to anyone with read access (W2).
  - Actions logs expire after 90 days, so they are not the record.
- **What this does not stop.** Darren, as owner, could delete a comment or
  disable protection. Doing so leaves a visible gap rather than a silent edit. For
  an audience of one, being able to detect tampering is the goal.

Pushes made with the workflow's own `GITHUB_TOKEN` do not trigger other
workflows, so `verify` runs inside the daily job. A second workflow runs the same
command on human pushes.

## Receipt format

Each forecaster gets at most one receipt per target date:
`ledger/forecasts/<forecaster_id>/<target_date>_<sha256[:12]>.json`

The receipt of record is that single file. Nothing is chosen after the fact,
because no second receipt can exist.

Example:

```json
{
  "schema": 1,
  "forecaster_id": "ours",
  "forecaster_version": "0.1.0",
  "definition": {"version": "stress-index-v1", "sha256": "9f2c..."},
  "issued_at_utc": "2026-11-03T21:19:42Z",
  "target_date_local": "2026-11-04",
  "tz": "America/New_York",
  "geography": {"target": "PJM balancing authority (EIA-930 respondent PJM, type D)",
                "weather": "NWS LWX/107,85 forecast; NCEI USW00093721 history (BWI)"},
  "claims": {"peak_mw": 98500, "peak_hour_ending_local": 19, "level": "watch"},
  "thresholds_mw": {"watch": 97100, "strained": 101800, "severe": 107300},
  "drivers": [{"name": "forecast_high_f", "value": 71},
              {"name": "forecast_morning_low_f", "value": 48},
              {"name": "day_type", "value": "weekday"}],
  "inputs": {"nws_bwi_issued_at_utc": "2026-11-03T19:52:00Z",
             "pjm_last_ok_hour_utc": "2026-11-03T20:00:00Z"},
  "no_call_reason": null
}
```

A no-call sets every claim to null and `no_call_reason` to `stale_load` or
`stale_weather`.

## Stress index v1

The published definition is `ledger/definitions/stress-index-v1.toml`, explained
in `docs/index/v1.md`. Every receipt names the definition and its sha256, and
scoring uses the definition the receipt names. A later amendment, such as v2,
cannot change how an earlier call is scored. v1 is never edited.

| Setting | v1 value | Why |
| --- | --- | --- |
| Weather point | NWS LWX/107,85 (BWI) | Matches the NCEI station used for fitting. W4 measured Reisterstown daytime forecasts 1 to 3 F cooler than BWI, 35 km away. |
| Temperature alignment | Target date D uses NWS high for D, and NWS low of the night starting D-1 (the morning of D). History uses NCEI TMAX(D), TMIN(D). | NCEI's calendar-day minimum usually falls before dawn on D, which is the night that starts on D-1. Winter peaks fall at 08:00 or 19:00 local (W3). |
| History | Same calendar window, ±21 days around D, last 3 complete years plus the current year | Limits drift from PJM load growth. |
| Day type | Weekday vs weekend. Holidays are not modeled in v1. | Known weakness: holidays will be over-forecast. |
| Model | `peak_mw = b0 + b1·max(0, high − 65) + b2·max(0, 50 − morning_low)`, least squares over same-day-type days. A hinge with fewer than 10 nonzero days is dropped. | Three parameters, solved in pure Python (3×3 normal equations; no numpy). |
| Levels | Percentiles of observed daily peaks in the window, all day types: watch ≥ p75, strained ≥ p90, severe ≥ p97 | Plan v2 defines stress relative to the season. |
| Stress day (for precision/recall) | Level ≥ strained | |
| Peak hour | Mode of the peak hour over the 10 nearest same-day-type days by (high, morning low); tie goes to the earlier hour | Peak hour is strongly seasonal (W3). |
| Peak-hour hit | Within ±1 hour | |
| Alerts (`[alerts]`) | Recorded as a per-day annotation for validation/display; never affect the level | Darren, Oct 30, 2026: temperature terms already carry heat and cold, so a bump would double-count them. |
| `settle_days` | 2 (provisional) | Revisions were unmeasurable in the backfill (W3). The scorecard reports any actual that changed between the daily and weekly scoring. |

**Darren ruling, Oct 30, 2026.** Any earlier alert-bump fallback is superseded; alerts are annotation only. This revision contains no alert-bump fallback passage or separate sections table to amend. The earlier line 128 concerns verifier timing, not fallback behavior.

The definition stays unpublished until S3c tests pass on the 2019-2026 history,
including a backtest table in `docs/index/v1.md`.

## Scoring

- **Complete day.** The local date's count of ok hours equals that date's
  expected hours (23, 24 or 25 in America/New_York). W3 measured 2,831 of 2,859
  dates passing. The looser "23, 24 or 25 ok hours" rule would have accepted 21
  dates that are each missing an hour.
- **Actual peak** comes from ok hours. W3 found no complete day with a non-ok hour
  next to its peak.
- **Actual level** uses the receipt's frozen `thresholds_mw`.
- **No receipt counts as a miss.** A target date with no receipt for a forecaster
  counts as a miss. That covers a failed build, a crash, a skipped cron run and a
  disabled schedule, with no extra recovery logic.
- **Weekly scorecard.** `grid weekly` covers the previous ISO week, after
  `settle_days`, per forecaster:
  - peak-hour hit rate;
  - peak-MW MAE;
  - stress-day precision and recall;
  - the miss count;
  - residual vs temperature.

  It is posted as an issue comment, so the published numbers carry a GitHub
  timestamp.

## Types, signatures and modules

`model.py` holds the shared frozen dataclasses. It is pure, and imports nothing
from the project.

| Type | Fields |
| --- | --- |
| `Level` | Enum: calm, watch, strained, severe |
| `Definition` | version, sha256, and the v1 table values |
| `DayHistory` | date, day_type, peak_mw, peak_hour_ending, complete, tmax_f, tmin_f |
| `Features` | target_date, day_type, history: tuple[DayHistory], fcst_high_f, fcst_morning_low_f, inputs |
| `Forecast` | the receipt fields |
| `Actual` | date, peak_mw, peak_hour_ending, complete |
| `Score` | forecast, actual, hour_hit, abs_err_mw, predicted_level, actual_level |
| `Scorecard` | week, per-forecaster rows |
| `Report` | load_lag_h, weather_issued_at, history_last_date, stale: set[str] |
| `Violation` | path, rule, detail |
| `Brief` | html, comment_md |

| Module | Kind | Public functions |
| --- | --- | --- |
| `stress` | pure | `parse_definition(raw) -> Definition`, `forecast(Features, Definition) -> Forecast`; computes and stores per-day alert annotations for validation/display only, never for the level |
| `scoring` | pure | `score(Forecast, Actual, Definition) -> Score`, `scorecard(list[Score], week) -> Scorecard` |
| `brief` | pure | `render(Forecast, list[Score], Report) -> Brief` |
| `features` | DuckDB reads | `load(conn, target, as_of) -> Features`, `actuals(conn, dates) -> dict[date, Actual]` |
| `freshness` | DuckDB reads | `check(conn, now) -> Report` |
| `warehouse` | dbt | `build(database) -> None`; the dbt test helpers reuse it |
| `ledger` | ledger IO | `append(root, Forecast) -> Path`, `entries(root) -> list[Forecast]`, `definition(root, version) -> Definition`, `verify(repo, new_since) -> list[Violation]` |
| `cli` | entry point | `grid daily`, `grid weekly`, `grid ledger verify`, `grid replay` |

```text
cli -> fetch, fetch_cli, nws, ncei -> storage
cli -> warehouse, features, freshness, ledger
cli -> stress, scoring, brief -> model   (pure; never import IO modules)
ledger -> model
dbt: raw -> cleaned (eia_*, nws_*, ncei_*) -> marts.mart_day_history
```

Two rules are enforced by tests:
- pure modules import no IO module;
- no module except `ledger` opens paths under `ledger/`.

**`features.load` pins the weather issuance by `fetched_at_utc <= as_of`.** It
uses fetch time, not NWS `updateTime`, because only fetch time rules out
lookahead. `nws_forecast_latest` stays a display view and is not a model input.

**A new source touches four places:**
- the `storage.land` set;
- the `storage.ingest` dispatch;
- the `cli` replay choices;
- its console script.

That is accepted at five sources; no registry.

## Runner state

The runner rebuilds the warehouse every day.
- Each run starts from an Actions cache of `data/` when one exists. The cache
  evicts entries unused for 7 days, with 10 GB per repo (W2).
- On a cache miss it refetches everything, about 7 EIA requests (180-day windows) plus 4 NCEI
  requests.
- The ledger in git is the only durable state.

Tradeoff: on Actions, raw responses and past NWS issuances last only as long as
the cache. The receipt records the forecast inputs it used. The PC keeps the full
raw archive when run there.

**Schedule.**
- The daily cron is `17 21 * * *`, i.e. 21:17 UTC (17:17 EDT, 16:17 EST). That
  leaves at least 6.7 hours of slack before local midnight, and avoids the top of
  the hour, when GitHub delays and drops runs (W2).
- A backup cron at `17 1 * * *` runs the same job. It does nothing if the receipt
  already exists.
- Both use `concurrency: grid-daily`.
- Permissions: the daily job gets `contents: write` and `issues: write`. The Pages
  job gets `pages: write` and `id-token: write`.

**Known risk, unconfirmed.** GitHub disables scheduled workflows in a public repo
after 60 days without "activity". It does not document whether bot commits count
(W2).
- If the schedule stops, the missing receipts show up in the scorecard as misses,
  and the brief stops arriving.
- Checking this is part of S5 acceptance.

## Why this shape

- **The pure core is fast to test.** `stress`, `scoring` and `brief` are tested
  without dbt. Each dbt-backed test costs seconds: 24 dbt tests ran in 126 s in
  the S2 suite. Candidate A, the dbt-centric design, put the model in SQL and read
  the receipts in both dbt and Python. That is two parsers of one format.
- **One owner per piece of state:**
  - the ledger: `ledger`;
  - the warehouse: dbt;
  - `site/`: build output, never committed.
- **Frozen thresholds and the named definition** keep old calls scored by the
  rules they were made under.

## Known weaknesses

- Holidays are not modeled in v1.
- Stress is relative to the season, so a severe April day is far below a typical
  July day in absolute terms. The brief prints the MW so readers can see both.
- PJM-wide demand is forecast from one Maryland weather point. Every receipt and
  brief says "PJM-wide call, Maryland weather". The scorecard's residual vs
  temperature shows if that link is weak.
- `settle_days` is a guess until revisions are observed.
- The 60-day schedule rule (see [Runner state](#runner-state)).
- Eight dates in the history peak at local midnight (W3). S3b must check whether
  they are real or data errors before they enter the history window.
- EIA's hour labeling (hour-beginning or hour-ending) is assumed hour-ending.
  S3b confirms it against EIA's documentation before the mart is built.

## Build order

One commit per step. Each step lists the tests written first.

| Step | Status | Delivers | Tests (RED first) |
| --- | --- | --- | --- |
| S3a | **Done** ([notes](s3a-ncei.md)) | `ncei` source, `cleaned.ncei_bwi_daily_temps`, `grid-temps` | As in S3a notes |
| Legacy retirement | In progress (worker W1) | Remove the legacy v1 pipeline; plain `dbt build` needs no vars | Full suite passes; `dbt parse` with no vars |
| S3b | Next | `marts.mart_day_history` (new `marts` folder, schema `marts`, view); confirm the EIA hour convention and the midnight peaks; `warehouse.build`, which the dbt test helpers then share | Spring and fall DST dates; a 24-hour day with 23 ok hours is incomplete; peak-hour tie; NCEI join on local date; morning-low alignment |
| S3c | | `model.py`, `stress.py`, `stress-index-v1.toml`, `docs/index/v1.md` with backtest | Hinge drop rule; percentile thresholds; analog peak hour and tie; no-call on stale input; definition hash |
| S4 | | `ledger.py`; `grid ledger verify` and `grid replay` in `cli.py`; `.github/workflows/verify.yml` for human pushes | Append refuses duplicate and late receipts; verify flags modify, delete, rename, hash mismatch and late add in range; merge-commit delete caught; import and path guard tests |
| S5 | | `features`, `freshness`, `scoring.score`, `brief`, `grid daily`, `daily.yml` with Pages and comment steps, dbt-duckdb moved to runtime deps, second NWS point | Freshness thresholds; no-call receipts; provisional score; brief golden file; a dry run of the workflow on a branch with `workflow_dispatch` |
| S6 | | `scoring.scorecard`, `grid weekly`, `weekly.yml` | Misses counted; precision and recall; scoring with frozen thresholds after a v2 definition exists |
| S7 | | README and layer docs rewritten | Gate: 14 consecutive daily receipts of record plus 2 weekly scorecards, all receipts passing `ledger verify` |

## Evidence behind this revision

| Worker | Finding |
| --- | --- |
| W2 | GitHub docs, fetched October 29, 2026: required checks block direct pushes; personal repos have no Actions bypass; `GITHUB_TOKEN` pushes trigger no workflows; schedule delays, drops and the 60-day disable; cache eviction; comment edit history; Pages from an artifact. |
| W3 | `data/s1-live` warehouse: 68,594 hours; 2,831 of 2,859 dates complete; one peak tie; no revisions in raw; peak-hour table by month. |
| W4 | NWS `/points`: BWI is LWX/107,85, 35.2 km from Reisterstown LWX/100,98. Daytime forecasts were 1.9 F warmer on average, nights 0.7 F different. |
| W5 | Repo state: `main` unprotected; no workflows, secrets or Pages; `GITHUB_TOKEN` defaults to read. |

Worker reports are in the T3 thread for this session.

## PLAN.md follow-ups (for Alder, who keeps the plan of record)

PLAN.md v3 repeats four mechanics this revision changes:

1. `ledger verify` as a required check and pre-commit hook. Now it runs in the
   daily job and on human pushes; it is not a required check, and there is no hook.
2. The push event as the timestamp. Now the issue comment with the receipt
   sha256 is the timestamp.
3. "One new file" for PJM. That paragraph is removed; adding a forecaster is
   designed when its route is approved.
4. The receipt of record as "the latest before the day". Now there is one receipt
   per forecaster per date.

Also new: the BWI forecast point for the model. Reisterstown stays for the
household line.

