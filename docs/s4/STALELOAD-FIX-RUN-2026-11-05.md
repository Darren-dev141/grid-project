# Stale-load keyless fix run, 2026-11-05 (Phase 2: W1-NCEI wiring / W2 / W3)

Worktree: `C:\Users\ajbig\Documents\grid-project-staleload`, branch `fix/stale-load-keyless`, cut from `main` at `f0adcba`.
The main checkout was not edited. Nothing was pushed. No EIA key was used or requested; nothing EIA was touched.
Tests run with the main checkout's `.venv` interpreter and `PYTHONPATH=src` so the worktree's `src/` is the code under test.
Raw logs live in `docs/s4/staleload-run/`.

## Rulings the work rests on (quoted before coding)

`docs/s3c/S3C-RULINGS-SETTLED-2026-10-31.md` line 13, "Issuance freeze":

> Issuance cutoff 7:00 AM ET. For a forecast issued on day D, D-2 is the latest completed peak. Prospective mode uses only data with availability time at or before issuance and fails closed when availability cannot be verified. Retrospective mode remains available and labeled.

- W3 rests on sentence 3 ("only data with availability time at or before issuance ... fails closed when availability cannot be verified").
- W2 would rest on sentence 2 (D-2 anchored to the ISSUE day D) plus the issue-before-target boundary
  (`docs/s3c/S3C-DIAGNOSIS-2026-10-31.md` line 28: "`PLAN.md` already require issuance before the target local date starts. The model now enforces that documented boundary directly, with `issue_time_not_before_target_date` ... This is not the deferred 7 AM rule.";
  `docs/architecture-s3-s7.md` step 4 "**Forecast tomorrow:**").

## W2: STOPPED on a ruling/plan conflict

Plan text (the task brief, from HOST-STEPS v2 §3, defect 2):

> Reconcile the target-day and freshness definitions with the S3C rulings: issue before the target day; freshness judged on the completed history through target-2, not on the target day's own load row.

Ruling text (above): "For a forecast issued on day D, D-2 is the latest completed peak."

Conflict, stated as arithmetic. The cron issues at 07:00 ET on day D.
- "Issue before the target day" means target >= D+1, so "history through target-2" means history through >= D-1.
- The ruling says the latest completed peak at an issuance on day D is D-2. D-1 is not a completed peak yet.
- So the plan's freshness bound asks for a completed day (D-1) that the ruling says does not exist at issuance. With next-day targets the plan's bound is never satisfiable.
- The only pair that satisfies "D-2 == target-2" is target == D, which `stress.py:232-233` rejects (`issue_time_not_before_target_date`) and the plan itself forbids.

The project record is split the same way:
- Same-day reading: `lean-spec/SPEC.md` I1 and `lean-spec/CONFORMANCE.md` I1 use "latest input day >= target - 2" and say the Nov 1 issuance (target Nov 1) "failed exactly this: Oct 28 < Oct 30". That treats target as the issue day.
- Next-day reading: `docs/architecture-s3-s7.md` ("Forecast tomorrow"), `PLAN.md`, and `stress.py:232-233`.

Probe (`docs/s4/staleload-run/w2_conflict_probe.py`, output `w2_conflict_probe.out`; real `stress.forecast`, synthetic Features, no data, no files written):

```
issued_at (D) = 2026-11-05T07:00:00-05:00
ruling latest completed peak = D-2 = 2026-11-03
same-day target (D): target=2026-11-05  target-2=2026-11-03  ruling D-2 == target-2? True  -> UNSCORED/issue_time_not_before_target_date
next-day target (D+1): target=2026-11-06  target-2=2026-11-04  ruling D-2 == target-2? False  -> UNSCORED/unverified_issue_time_availability
```

Decision needed from the coordinator / Darren (which one is the product):
1. Same-day: the 07:00 job forecasts TODAY's peak. Then `stress.py:232-233` must be relaxed to something like "issue before the peak, at or before the 07:00 cutoff on the target day", and PLAN.md / architecture "issuance before the target local date starts" must be amended. The 11-01 to 11-04 artifacts and the Lean spec already assume this.
2. Next-day: the 07:00 job forecasts TOMORROW. Then freshness must be judged through the ruling's D-2 = target-3 (not target-2), the Lean spec's "target - 2" ceiling must be amended, and `issue_stress.py` must move `target_date` to D+1.
Also true under either choice: the target-day weather (`high_f`, `morning_low_f`) cannot come from NCEI observed temperatures at 07:00 (the Nov 2 diagnosis, "Smallest fix" item 2). That needs the NWS forecast adapter (separate branch), which is outside this phase.

No W2 code was written. `issue_stress.py` target/freshness lines (29, 32, 42-43) are untouched.

## Test counts

| Run | Collected | Passed | Failed | Log |
|---|---|---|---|---|
| Baseline, worktree at `f0adcba` | 249 | 247 | 2 | `staleload-run/baseline-suite.txt` |
| After W3 + W1 wiring, worktree | 281 (= 249 + 32 new) | 279 | 2 (same two) | `staleload-run/after-suite.txt` |
| After, clone of the branch in a directory named `grid-project` | 281 | 281 | 0 | `staleload-run/after-suite-dir-named-grid-project.txt` |

Pre-existing failures, recorded and not fixed: `tests/test_ledger_access.py::test_relative_dynamic_child_path_is_denied` for the two params using `./grid-project/ledger/definitions/stress-index-v1.toml` with cwd `repo/..`. They hardcode the repo directory name `grid-project`, so they fail in any checkout with another name (this worktree is `grid-project-staleload`). Same commit `f0adcba` exported into a directory named `grid-project`: 12 passed (`staleload-run/ledger_access_namecheck.txt`). Not a code regression.

New tests: `tests/test_availability.py` (21) and `tests/test_refresh_ncei.py` (11).

## W3: landed (commit `ccb10a1`)

What changed:
- `model.py`: `HistoryDay.load_usable_at / temperature_usable_at`, `Features.weather_usable_at`, `AvailabilityCheck`, `ForecastReceipt.input_availability`. All new fields default to None, so existing callers (`synthetic-twin`, `diagnose_s3c`, `backtest_stress`) are unchanged.
- `stress_inputs.py`: the loader derives first-usable time per selected row as `greatest(loaded_at, observed_at)` for committed batches only, `NULL` when a committed batch has no `observed_at`. A day's value is the latest across contributing rows (load includes the adjacent hours the quality model reads) and is `NULL` if any contributing row is `NULL` (DuckDB `greatest()` skips NULLs, so this is tested explicitly). Row selection (first-recorded by `loaded_at`) and the existing `*_available_at` fields are unchanged.
- `stress.py`: new `verify_input_availability(features, used_days)`. The unconditional `no_call('unverified_issue_time_availability')` is replaced by: run the history gates, verify every day the forecast would use plus the target weather, no-call with that reason if anything is unproven, otherwise set `publication_availability='verified'` and continue into the normal calculation. The old indexing-time `availability` gate is untouched.
- `scripts/issue_stress.py`: `input_availability_verified` and its note now come from `availability_fields(result)`, which reads the receipt's `input_availability`. A run that no-called before the check reports False with "not reached". Nothing is hardcoded true.

Tests (all in `tests/test_availability.py`):
- Positive: committed archive end to end earns the flag and SCOREs; usable exactly at issuance verifies.
- Negative: usable one second after issuance; a missing, naive, or late usable time on any single used day; indexing times alone; target weather with no/late/naive usable time; backdated `loaded_at` with a later commit record (loader and end to end); batch committed with no commit record; adjacent hour with no commit record; uncommitted batch rows (never verify, and cannot pull a day's usable time earlier than the committed copy).
- Only days the forecast uses are checked (an out-of-season day with no proof does not block).

Mutation check (tests fail when the logic is broken; logs in `staleload-run/mutation-M*.txt`):
- M1 usable time ignores the commit record: 4 failed.
- M2 committed batch with no `observed_at` counted usable at `loaded_at`: 2 failed.
- M3 `verify_input_availability` always passes: 16 failed.

Real-shape checks on scratch copies of the production DBs (read-only copy of the two `grid.duckdb` files; nothing in the main checkout modified):
- `prod-copy-loader-probe.txt`: all 2859 load days and 2854 temperature days carry a usable time (every production batch has a commit record), so the strict rule is not blocked by legacy rows. Newest load usable time 2026-10-29 06:56 ET; newest temperature 2026-10-29 09:09 ET.
- `dry-main-on-prod-copies.txt`: `issue_stress.main()` with ROOT/DB paths redirected to scratch ran end to end; result `UNSCORED / stale_load`, `input_availability_verified: false` ("Availability check not reached"). Expected: W2 not done and data stale.

Limits, stated plainly:
- The evidence is the local DuckDB commit record (`observed_at`). It is not tamper-evident, so this proves what the archive recorded, not independent publication. It does not answer the diagnosis's open question 5 (immutable evidence). A backdated `loaded_at` is defeated; a backdated `observed_at` is not detectable.
- `observed_at` is overwritten when a digest is re-fetched, which can only move usable time later (conservative).
- `Features.weather_usable_at` is supplied by the caller. No loader derives it for NWS target weather yet, so a real prospective SCORED call still needs the NWS adapter (separate branch) to supply it from commit records. Under today's `issue_stress.py` the target-day row never exists at 07:00, so the run still no-calls `stale_load` (W2).
- The strict reading was chosen: one unproven used day makes the whole run unverified (no silent shrinking of the sample).

## W1 (NCEI half): wiring landed (commit `4b5c316`); catch-up held, then RUN after release (see "NCEI catch-up run" below)

The scheduled job `d977b52c965c` has `script = grid_s3c_repo_launcher.py`, `no_agent: true`, `workdir = C:\Users\ajbig\Documents\grid-project`, schedule `0 7 * * *`. The script it runs lives outside the repo at `C:\Users\ajbig\AppData\Local\hermes\scripts\grid_s3c_repo_launcher.py`. `jobs.json` was NOT edited.

Exactly what changed:
1. New in the repo (committed): `scripts/refresh_ncei.py`. It reads the newest committed NCEI `DATE` from the temperature archive, starts 3 days earlier (overlap), ends today exclusive, and calls the same `grid_pipeline.ncei.fetch` that `grid-temps` calls. `--dry-run` prints the window and the equivalent `grid-temps` command with no network. Archive already current: no-op. Failure: exit 1 with a one-line message.
2. Edited in place (outside the repo): `grid_s3c_repo_launcher.py` gained `refresh(repo, python)` and `execute()` calls it first. It runs `<repo>\scripts\refresh_ncei.py` with the repo `.venv` python, prints its output, and if it exits non-zero prints `NCEI refresh failed (exit N); issuing with existing data` and issues anyway. If `scripts\refresh_ncei.py` is absent it prints `NCEI refresh: skipped (... not present in repo)` and issues.
   - Backup: `C:\Users\ajbig\AppData\Local\hermes\scripts\grid_s3c_repo_launcher.py.bak-pre-ncei-refresh`
   - sha256 before `627d92f770d52f6b003e4b8b210eebb8eae095eae4f235035faffd7cce7a0a1b`, after `81708cc01bb2538170a6e2583906494655a5f41861bb778463d7a6c49f6fc6ac`; diff in `staleload-run/launcher-ncei-refresh.diff`.
3. Verified without touching data (`staleload-run/launcher-wiring-check.txt`): with stub scripts in a scratch repo the order is refresh then issue; a failing refresh still reaches issuance; an absent script is skipped; against the real main checkout `refresh()` prints "skipped" because the script is not in main.

Consequence to know: the edit is INERT today. The main checkout has no `scripts\refresh_ncei.py`, so the 07:00 job on Nov 5 fetches nothing. Merging this branch into main activates the refresh at the next 07:00 fire. If activation should wait for the coordinator's release, merge after releasing, or run the catch-up below first.

Catch-up command, identified and NOT run (keyless NCEI endpoint only, nothing EIA):

```
C:\Users\ajbig\Documents\grid-project\.venv\Scripts\python.exe C:\Users\ajbig\Documents\grid-project-staleload\scripts\refresh_ncei.py --root C:\Users\ajbig\Documents\grid-project\data\s3a-verification
```

Equivalent `grid-temps` form for the archive as copied on Nov 5 (newest recorded date 2026-10-24); add `--dry-run` to the command above to recompute the window at release time:

```
C:\Users\ajbig\Documents\grid-project\.venv\Scripts\grid-temps.exe --root C:\Users\ajbig\Documents\grid-project\data\s3a-verification --start 2026-10-21 --end 2026-11-05
```

Dry run on the scratch copy (`staleload-run/refresh-ncei-dry-run-on-prod-copy.txt`): `status dry_run, latest_recorded 2026-10-24, start 2026-10-21, end 2026-11-05`. The real run mutates `data\s3a-verification\grid.duckdb` and adds `data\s3a-verification\raw\ncei\<digest>.json`.

Timing finding (needs a decision): the issuance input cutoff is `min(issued_at, 07:00 ET)`. A refresh run inside the 07:00 job commits its batch after 07:00:00, so the loader's `loaded_at <= cutoff` filter excludes it for that day's issuance (the existing `test_index_cutoff_excludes_later_batches_without_claiming_commit_provenance` covers that filter). In steady state the in-job refresh therefore serves the next day's issuance. The one-time catch-up run before 07:00 is not affected. If same-day freshness is wanted, the refresh needs to run before 07:00 (for example a separate 06:30 job), which changes scheduling and was not done.

Nothing EIA was touched: no `grid-fetch`/`grid-backfill`, no key, no request for one. EIA load data remains at 2026-10-29, so `stale_load` from the EIA half persists until that is handled separately.

## NCEI catch-up run (released 2026-11-05 ~01:57 ET)

Release: the coordinator reported the HOST-STEPS v2 seat finished with its final verification trio passing and lifted the hold. Wall clock was 01:57 ET, before the 07:00 job. No live issuance was run; W4 stays pending the EIA piece.

Command run (from the worktree, against the main checkout's data directory, using the main `.venv` interpreter; same window as `grid-temps --root ... --start 2026-10-21 --end 2026-11-05`):

```
C:\Users\ajbig\Documents\grid-project\.venv\Scripts\python.exe scripts\refresh_ncei.py --root C:\Users\ajbig\Documents\grid-project\data\s3a-verification
```

- Dry run first (`staleload-run/ncei-catchup-dry-run.txt`): latest recorded 2026-10-24, window 2026-10-21 to 2026-11-05 exclusive.
- Exit code 0 (`ncei-catchup-run.exit`), stderr empty, wall time about 1 second. Output (`ncei-catchup-run.out`): `{"days": 12, "digest": "b30a4ce8...504f0", "end": "2026-11-05", "indexed": 12, "start": "2026-10-21", "station": "USW00093721", "status": "fetched"}`.
- Landed: one new committed batch, 12 BWI daily rows covering 2026-10-21 through 2026-11-01 (`ncei-catchup-landed-rows.txt`). 8 are new dates (2026-10-25 to 2026-11-01). The 4 overlap dates (2026-10-21 to 10-24) were already recorded; the earlier batches keep first-recorded precedence, so first-recorded history is unchanged.
- NCEI returned nothing for 2026-11-02 to 2026-11-04, so the archive is not yet through yesterday. That is NCEI publication lag, not a failed fetch; the next run picks those days up.

Archive state (`ncei-catchup-pre-state.txt` / `ncei-catchup-post-state.txt`):

| | Before | After |
|---|---|---|
| NCEI batches (all committed) | 8 | 9 |
| Records in committed batches | 2854 | 2866 |
| Distinct dates | 2854 | 2862 |
| Latest DATE | 2026-10-24 | 2026-11-01 |
| Latest loaded_at / observed_at | 2026-10-29 09:09 ET | 2026-11-05 01:57:31 ET |

Loader view as of now (`ncei-catchup-latest-state.txt`, read-only): latest day with temperature 2026-11-01 (every temperature day has a commit-derived usable time); latest day with load still 2026-10-28, because EIA was not touched. The D-2 bound for a Nov 5 issuance is 2026-11-03, so load is still about 6 days short and `stale_load` will persist until the EIA piece lands.

Side effects: `data\s3a-verification\grid.duckdb` gained the batch and `data\s3a-verification\raw\ncei\b30a4ce8...504f0.json` was landed. `data/` is gitignored, so main shows no tracked changes from this run. Main's `git status` shows only the other seat's untracked `docs/s4/HOST-STEPS-V2-RUN-2026-11-05.md`.

Because the main checkout now has the refreshed archive but not `scripts\refresh_ncei.py`, tomorrow's 07:00 job still does not refresh until this branch is merged (launcher is inert until then).

## Hard limits check

- Main checkout: no edits, no commits, no pushes. Reads only: the two `grid.duckdb` files were copied to scratch for probes; `data/`, `docs/`, and git state there were not modified. `git worktree add` wrote worktree metadata under the main repo's `.git`, which is how a worktree is created.
- No EIA key involved. `ledger.append_forecast` not wired. The payload flag was not edited to force a score (it is now computed).

## Open items for the coordinator

1. W2 decision (same-day vs next-day target); see the conflict above. Until then `issue_stress.py` keeps `target_date = issued_at.date()`.
2. NCEI catch-up: DONE after release (see "NCEI catch-up run"); NCEI is through 2026-11-01 and will need the next refresh for 11-02 onward.
3. Decide whether the refresh should run before 07:00 (timing finding).
4. EIA refresh remains an open dependency (key required; out of scope).
5. The NWS target-weather adapter must supply `weather_usable_at` before any real SCORED prospective call.
