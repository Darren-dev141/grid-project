# Stage 5: Initial Zoom Out (egm-zoom-out)

Target: `docs/architecture-s3-s7.md`, full file (170 lines, October 29, 2026).
Standard: `zoom-out-standard.md`. Reviewer status: completed.
Verdict: not ready. 2 Blockers, 4 Majors, 10 Nits.

## Blockers

1. **Actions runners start empty, and the doc never says where the warehouse lives**
   (lines 21-35, 101-106, 109, 168; `.gitignore` line 8).
   - Everything the forecaster reads sits under the git-ignored `data/` folder:
     - the DuckDB warehouse;
     - the raw store;
     - the EIA checkpoints;
     - 68,594 hours of PJM demand;
     - the NCEI history;
     - every NWS issuance.
   - A fresh runner has none of it.
   - The Actions cache can be evicted, so it cannot be the source of truth.
   - Needed: one explicit decision on what is persisted and where. One option is to rebuild what can be refetched and to persist only what cannot, such as the NWS issuances.
2. **Branch protection with a required check probably blocks the job from pushing receipts to `main`**
   (lines 134-136, 159, 168, 24).
   - The reviewer did not verify this against GitHub's current rules.
   - Options: a ruleset bypass for Actions, a receipts branch, or the workflow running `ledger verify` itself before it pushes.

## Majors

3. **The status is out of date** (lines 3-5, 24, 128, 130, 164-170). PLAN.md v3 has resolved all three owner decisions. The doc still keeps three ruled-out paths:
   - the "if NCEI is declined" fallback;
   - the PC Task Scheduler option;
   - a human-run `git commit && git push`.
4. **Nothing checks the third-party timestamp** (line 138). `ledger verify` only checks the `issued_at` that each receipt records itself. Push events and Actions logs expire after about 90 days. Fix: put each receipt's filename and hash in the pinned-issue comment, and treat the comment's server time as the timestamp of record.
5. **"One new file, no list to update" overstates how easy PJM will be** (lines 41, 53, 101-105). Adding PJM really needs:
   - a new storage parse branch;
   - a call from the runner;
   - nullable thresholds.

   There is also a layout mismatch: a `forecasters/pjm.py` package next to a top-level `stress.py`. Keep `forecaster_id` in the path, state the real cost, and defer the null rules until the route is approved.
6. **No objective statement, and the README contradicts the doc** (lines 1-16). The README still describes the charging tool, Power BI and price freshness.

## Nits

7. `--since origin/main` contradicts "scans the full git log". Always scan the full history.
8. The pre-commit hook is redundant when Actions is the only writer and CI already checks.
9. Delete `nws_forecast_latest` (only its own tests use it) instead of keeping it "display-only".
10. The alert bump may double-count temperature now that NCEI is adopted. Justify it in `docs/index/v1.md` or drop it from v1.
11. Extend `cli.py` instead of renaming it to `run.py`. Say which console scripts survive. `replay` is missing from the caller's usage.
12. Don't commit `site/`. Deploy Pages from a workflow artifact.
13. A new source touches three places (the `land` set, the `ingest` dispatch, the `cli.py` choices), not one.
14. "One feature mart" and "the only SQL into the marts" are inaccurate: NWS inputs and `freshness` also read the warehouse.
15. The NCEI fetch window is undefined. Fuel mix is "kept" but never fetched by `grid daily`.
16. The retirement list misses:
    - `powerbi/`;
    - the dbt tests `finite_values`, `hour_alignment` and `renewable_share_range`;
    - the `bge_pnode_id` var;
    - the price sections of `layer-1.md` and `README.md`.
