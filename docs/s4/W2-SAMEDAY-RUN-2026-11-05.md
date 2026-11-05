# W2 run record, 2026-11-05: same-day issuance semantics

Worktree: `C:\Users\ajbig\Documents\grid-project-staleload`, branch `fix/stale-load-keyless`, cut from `724126a`.
Code, tests and docs: commit `374d038` ("W2: same-day issuance semantics (Darren's ruling, Nov 5, 2026)"). This record and its logs are committed on top of it, matching how `STALELOAD-FIX-RUN-2026-11-05.md` and `staleload-run/` were handled on this branch.
Logs: `docs/s4/w2-sameday-run/`.
Nothing was merged. Nothing was pushed: the branch has no upstream and does not exist on `origin`. No issuance (W4) was run. No EIA key was used and the EIA fetch path was not touched. `data/` was not read or written. The main checkout was not edited.

## The ruling

**Darren's ruling, Nov 5, 2026 (02:19 ET): SAME-DAY. The 07:00 job forecasts today's peak; freshness judged on completed history through target - 2.**

`target_date` stays D (the issue day). The D-2 freshness rule is unchanged: for a forecast issued on D the latest completed peak is D-2, and freshness is judged on completed history through D-2 (= target - 2). Only the issuance-timing gate changes.

## Restatement (Step 0)

Darren ruled that the 07:00 job forecasts the same day's peak. `target_date` stays the issue day D, and the D-2 freshness rule is unchanged: freshness is judged on completed history through target - 2, and a stale load must still no-call `stale_load`. The only semantic change is the issuance-timing gate in `stress.py` and `issue_stress.py`, which today rejects same-day issuance. It must instead pass issuance at or before 07:00 local on D and no-call issuance after the day's peak. I verify the "Lean spec already assumes same-day" claim against the spec and the Nov 1-4 receipts before touching code, add tests, run the full suite in a `grid-project`-named checkout, amend the docs without rewriting settled history, and commit locally with no merge, no push unless the branch already tracked a remote, and no issuance run.

## Lean-spec verification (Step 1)

Verdict: the phase-2 claim holds. The spec and model assume same-day (target == issue day == slot day). No next-day wording exists anywhere in `lean-spec/`; a search for `next-day`, `next day`, `tomorrow`, `D+1`, `day + 1` found nothing in SPEC.md, CONFORMANCE.md, GridLedger.lean or BUILD-LOG.txt. The spec was not edited.

- `lean-spec/SPEC.md`, I1: "A day may be recorded **scored** only if the inputs it used were (a) no older than the freshness bound relative to the target day - the recorded "D-2 ceiling": latest input day >= target - 2; (b) strictly before the target day (no lookahead); and (c) availability-verified". Its source line: "Nov 1 issuance (inputs' latest date Oct 28 vs D-2 ceiling Oct 30 for target Nov 1 -> `stale_load` no-call)". The Nov 1 issuance is scored against target Nov 1, so target is the issue day.
- `lean-spec/SPEC.md`, grounding: "One issuance obligation per local day (the 07:00 America/New_York slot ...)". A3: "Slot = day."
- `lean-spec/CONFORMANCE.md`, I1: "(a) `latest_completed_input_date >= target_date - 2` (the D-2 ceiling; Nov 1 failed exactly this: Oct 28 < Oct 30); (b) `latest_completed_input_date < target_date` (no lookahead, S3c Ruling 6)".
- `lean-spec/lean/GridLedger.lean`: `def scheduled (day : Nat) : Nat := day * 1440 + 420` (the 07:00 local slot of day `d`); `StepOK` requires `r.day = cfg.firstDay + l.length` and `scheduled r.day <= r.issuedAt` ("never stamped earlier than its slot"); `OutcomeOK` for a scored record requires `r.availVerified = true` and `exists s, r.inputStamp = some s /\ s < r.day /\ r.day <= s + cfg.freshBound`. The record's `day` is both the target day and the slot day. The checked Nov 1-3 example uses the 07:00 slot of the same day.

Artifacts half (`scheduled-run-lateness.txt`): issue date equals target date in every receipt.

| File | issued_at | issue date | target_date | seconds after 07:00 | status / reason |
|---|---|---|---|---|---|
| 2026-10-31 | 2026-10-31T14:21:23-04:00 | 10-31 | 10-31 | 26483.5 | UNSCORED / stale_load |
| 2026-11-01 | 2026-11-01T11:15:49-05:00 | 11-01 | 11-01 | 15349.4 | UNSCORED / stale_load |
| 2026-11-02 | 2026-11-02T07:00:23-05:00 | 11-02 | 11-02 | 23.6 | UNSCORED / stale_load |
| 2026-11-03 | 2026-11-03T07:00:07-05:00 | 11-03 | 11-03 | 7.5 | UNSCORED / stale_load |
| 2026-11-04 | 2026-11-04T07:00:08-05:00 | 11-04 | 11-04 | 8.8 | UNSCORED / stale_load |

`CADENCE-TRACKER.md` ends at Nov 2; it has no Nov 3 or Nov 4 rows. The Nov 3 and Nov 4 artifacts exist.

Note for the amendment question: the spec needs no change under same-day. One refinement worth knowing: in the Lean model a late record can still be scored (`IsLate` is derived, not forbidden), while the Python gate now no-calls any prospective issuance after the cutoff. The model permits the stricter behavior, so there is no conflict.

## Gate semantics before and after (Step 2)

Before (`stress.py`, prospective branch of `forecast`): `if features.issued_at.astimezone(ZoneInfo('America/New_York')).date() >= features.target_date: return no_call('issue_time_not_before_target_date', receipt)`. With `target_date = issued_at.date()` this rejected every same-day run. The brief cited lines ~232-233; after W3 the line was ~265.

After (`src/grid_pipeline/stress.py`):
- `ISSUANCE_CUTOFF = time(7, 0)` (line 139), `issuance_cutoff(target_date)` (142): 07:00 America/New_York on the target day.
- `peak_hour_start(target_date, peak_hour_ending)` (147): local start of the target day's hour ending H, at hour H-1.
- `_issued_after(issued_at, boundary)` (153): compares instants in UTC. Aware datetimes that share one tzinfo object would otherwise compare wall clocks, which is wrong across DST.
- Timing gate (line ~287, same position as the old one, after the freshness and temperature checks and before the weather-availability check): issuance after `issuance_cutoff(target_date)` no-calls `issue_time_after_target_day_cutoff`. Issuance at or before it, including on an earlier day, passes.
- Peak gate (line ~322-327, after the analogs are selected and before the fit): `peak_hour = _mode_hour(...)`. In prospective mode, issuance after `peak_hour_start(target_date, peak_hour)` no-calls `issue_time_after_peak`. The Forecast reuses `peak_hour`; nothing else in the calculation changed.
- Reason names: `issue_time_after_target_day_cutoff` and `issue_time_after_peak`, following the existing `issue_time_*` and `*_at_issuance` pattern. `issue_time_not_before_target_date` is retired because it would now be false. Reasons are open strings (nothing enumerates them in `ledger.py`; the Lean `NoCallReason` enum never listed the issue-time reasons).

Peak-gate definition and why. The target day's actual peak time is unknowable at a prospective issuance. The only peak-time source in the repo for the target day is the forecast's own peak hour (the mode of the selected analogs' `peak_hour_ending`; `HistoryDay.peak_hour_ending` describes past days only). It exists only once the model has run, so it is checked at that point. The 07:00 cutoff stays the operative pre-model gate. The peak gate adds protection only where the predicted peak hour starts at or before the issue time (for example a winter morning peak at hour ending 7). Boundary: issuance exactly at the start of the peak hour passes; one tick later fails.

Comparison is strict (`>`): issuance at exactly 07:00:00.000000 passes, 07:00:00.000001 fails. See open finding (a).

Freshness change in `scripts/issue_stress.py` (`load_is_fresh` line 57, `build_features` line 70, `main` calls `build_features` at line 99). The old line was `load_fresh=target is not None and target.load_first_recorded is True`, which judged freshness on the target day's own load row. The brief says `load_fresh` must be judged on completed history through target - 2 and never on the target day's own load row, and the Nov 2 diagnosis (`DIAGNOSIS-STALE-LOAD-2026-11-02.md`, "Smallest fix" item 2) named this as the blocking cause: at 07:00 on D the target day's load row cannot exist, so every on-time run was `stale_load` whatever the data currency. Without the change the ruling could never produce a scored run through `issue_stress.py`, so it was required, not optional. New rule: `load_fresh` is true only when the latest completed peak (D-2) is in the first-recorded history, complete, `load_first_recorded is True`, and has a finite `peak_mw`. This is the same bound the existing history gate (`day.date <= issue_date - 2`) and the Lean ceiling (`stamp >= target - 2`, `stamp < target`) already imply. `weather_fresh` was NOT changed (open finding (c)). `target_date` stays `issued_at` in ET. The D-2 history gate in `stress.py` and W3's availability provenance (`ccb10a1`) were not touched.

## Tests (Step 3)

Replaced, in `tests/test_stress_rulings.py`: `test_prospective_issue_at_or_after_target_local_midnight_has_no_claim` (it asserted `issue_time_not_before_target_date`). Its four instants are all kept, now in two tests:
- `test_prospective_issue_after_the_target_day_cutoff_has_no_claim` (4 cases: two days after the target day; one second after 07:00 on a normal day, on the spring-forward day, on the fall-back day). Expect `issue_time_after_target_day_cutoff`.
- `test_prospective_issue_at_or_before_the_target_day_cutoff_passes_the_timing_gate` (7 cases: the three original target-local-midnight instants, exactly 07:00 on all three dates, 06:59:59 EST on the fall-back day). Expect the next gate in line, `unverified_issue_time_availability`.

Unchanged and still passing: `test_prospective_timestamps_alone_do_not_prove_issue_time_availability` (issues the day before the target, which the new gate also passes). All W3 tests in `tests/test_availability.py` pass unchanged.

New (20 collected cases), same file:
- `test_same_day_issue_at_0700_with_fresh_verified_history_is_scored`
- `test_same_day_issue_at_or_before_the_cutoff_is_scored` (4)
- `test_same_day_issue_after_the_cutoff_has_no_claim` (3, including 07:00:08, when the Nov 4 run fired)
- `test_same_day_issue_after_the_days_peak_has_no_claim` (3)
- `test_issue_after_the_start_of_the_forecast_peak_hour_has_no_claim` (5, including the hour-start boundaries)
- `test_same_day_features_with_history_through_d_minus_2_are_scored_without_a_target_load_row`
- `test_same_day_stale_history_still_no_calls_stale_load` (2; history through D-5 and D-3, with a target-day row that claims first-recorded load)
- `test_load_freshness_is_judged_on_the_completed_peak_two_days_before_the_target`

Counts. Baseline 281. The suite now collects 308 = 281 + 27 (the replaced test went from 4 collected cases to 4 + 7, which is +7, plus 20 new cases).

Partial run, 4 files (`targeted-4-files.txt`): `test_stress_rulings.py`, `test_availability.py`, `test_stress.py`, `test_stress_inputs.py`: **105 passed**.

Mutation checks (`mutation-check.sh`, output `mutation-check.txt`; scratch copy, repo untouched, originals restored byte for byte), `tests/test_stress_rulings.py` only, 53 tests:

| Mutation | Result |
|---|---|
| M0 unmutated | 53 passed |
| M1 old before-target-date gate restored | 17 failed |
| M2 peak-hour gate disabled | 2 failed |
| M3 boundary made exclusive (`>=`) | 9 failed |
| M4 target-row freshness restored | 3 failed |
| M5 restored | 53 passed |

**Full suite: 308 passed, 0 failed, 516.79 s (0:08:36), exit 0** (`full-suite-dir-named-grid-project.txt`, `.exit`). Method: `git worktree add --detach C:\Users\ajbig\w2verify\grid-project 374d038` (the branch is already checked out in the staleload worktree, so a second checkout of it was not possible), then from inside that directory `PYTHONPATH=src` with the main checkout's `.venv` interpreter, `python -m pytest -q -p no:cacheprovider`. The directory is literally named `grid-project`, so the two path-sensitive `tests/test_ledger_access.py` cases pass there (`ledger-access-in-grid-project-dir.txt`: that file alone, 30 passed). The verification worktree was removed afterward with `git worktree remove --force`, and the scratch parent is gone. The staleload-named worktree would be expected to show the same two path-sensitive failures (306 of 308); that is a directory-name artifact, as recorded in `STALELOAD-FIX-RUN-2026-11-05.md`, not a regression. I did not re-run it.

An earlier attempt to make the same verification with a scratch clone (a command containing `rm -rf`) hit a PC-client approval gate, timed out and was not retried.

## Docs amended (Step 4)

- `PLAN.md`: Receipts bullet amended in place ("latest issued at or before the 07:00 America/New_York cutoff on the target day, and before that day's peak"), ruling note attached at that point, and a dated "Nov 5, 2026 (ruling)" bullet appended to Status.
- `docs/architecture-s3-s7.md`: ruling note under the Status block; Objective item 1, step 4 and step 5 amended inline with "(Amended Nov 5, 2026 ...)" markers. The Schedule section (17:17 EDT afternoon cron) and the `ledger` No-backdating rule are named in the note as superseded design text and are NOT re-planned.
- `docs/s3c/S3C-RULINGS-SETTLED-2026-10-31.md`: settled rulings untouched; dated amendment appended (issue-time gate only; D-2 ruling stands).
- `docs/s3c/S3C-DIAGNOSIS-2026-10-31.md`: not rewritten; "Superseded in part, Nov 5, 2026" note appended.
- Lean spec: not edited.

## Commits

- `374d038` W2 code, tests and docs (on top of `724126a`).
- The commit that adds this record and `docs/s4/w2-sameday-run/` follows it; its hash is the branch head. See the final reply.

## Open findings, stated plainly

(a) **The 07:00:00 cutoff is a zero-width window for the real job.** The scheduled run fires at 07:00:07 to 07:00:23 (Nov 2: 23.6 s, Nov 3: 7.5 s, Nov 4: 8.8 s after 07:00:00, all `issued_late: true`). The launcher (`grid_s3c_repo_launcher.py`, outside the repo) refuses issuance only when `(now.hour, now.minute) < (7, 0)`, so it admits anything from 07:00:00. The Python gate, as specified, admits nothing after 07:00:00.000000. Once the data is fresh, every genuine scheduled run will therefore no-call `issue_time_after_target_day_cutoff`, and the W1 launcher refresh step adds more seconds. The input cutoff in `issue_stress.py` is already `min(issued_at, 07:00:00)`, so a few seconds of lateness adds no lookahead to the inputs. A fix, such as treating the whole 07:00 minute as on time to match the launcher and the minute-granular Lean model, is a change to a fixed rule and is Darren's call. It was NOT applied. The one-line change would be in `issuance_cutoff`/`_issued_after` (compare against 07:01:00 exclusively) plus updating `test_same_day_issue_after_the_cutoff_has_no_claim` and the `07:00:00.000001` boundary cases.

(b) **`ledger.py` still enforces the old rule.** `append_forecast` raises "cannot append a forecast after its target day began" when `now >= datetime.combine(target_date, time.min, ET)`, and `verify` requires a push witness with `issued <= observed < deadline`, where `deadline` is the target day's local midnight (two sites). A same-day receipt cannot be ledgered or witnessed under the current code. `issue_stress.py` does not call the ledger today (it writes `docs/s3c/S3C-FIRST-ISSUANCE-<date>.json`). `ledger.py` was not touched; PLAN.md and the architecture doc say it is not aligned.

(c) **`weather_fresh` still reads the target day's NCEI row.** At 07:00 on D that row does not exist, so a run with fresh load will no-call `stale_weather` until the target-day weather and its first-usable time come from the NWS side (the NWS adapter is on a separate branch). `Features.weather_usable_at` likewise has no loader. This blocks a scored production run independently of W2. It was not touched.

(d) **Other "before the target's local midnight" wording remains, left as dated records:** `docs/s4/alder-round/README.md` (fixed selection rule: "latest issuance before the target's local midnight"; Oct 31 receipt wording), `docs/s4/alder-round/HOST-STEPS.md` (push "before the target's local midnight"), `docs/s4/recheck-2026-10-31/README.md` (backdating rows), the PLAN.md "Core question" ("is tomorrow a high-stress day"), and the architecture Schedule and No-backdating text noted above. `CADENCE-TRACKER.md` stops at Nov 2.

Smaller notes: the earlier `STALELOAD-FIX-RUN-2026-11-05.md` says "The 11-01 to 11-04 artifacts and the Lean spec already assume this" (same-day); the artifacts half is confirmed above. The synthetic twin (`synthetic-twin/run_pipeline.py`) still builds `load_fresh` from the target row and issues the day before the target; it was not changed and is not part of the test suite. The Lean `NoCallReason` enum has three values and never listed `unverified_issue_time_availability` or the issue-time reasons; it is an abstraction and was not edited. An unrelated pre-existing worktree at `C:\Users\ajbig\Documents\w3check\grid-project` (detached at `724126a`) appears in `git worktree list`; it is not mine and was not touched.
