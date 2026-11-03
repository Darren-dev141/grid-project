# Stage 9: Implementation Readiness (egm-implementation-readiness, egm-codebase-details, egm-style)

Target: `docs/architecture-s3-s7.md`, DetailedRange lines 152-171 (Build order, Owner
decisions). Standard: `implementation-readiness-standard.md`.
Reviewer status: implementation readiness completed, codebase details completed, style completed.

Raw counts:

| Reviewer | Blocker | Major | Nit |
| --- | --- | --- | --- |
| Implementation readiness | 2 | 8 | 5 |
| Codebase details | 4 | 10 | 7 |
| Style | 0 | 5 | 5 |

Duplicate findings are merged below.

## Blockers

- **R1. S3c leaves the core model decisions to the implementer.**
  - Undecided: the NCEI-to-NWS temperature date alignment and every value in `stress-index-v1.toml` (window, hinge bases, percentile cuts and their population, analog count, tolerance, `settle_days`).
  - The alignment also feeds `mart_day_history` in S3b, which comes one step earlier.
  - v1 can never be edited, so a wrong choice costs a v2 amendment.
  - Sources: readiness B1, codebase B3, style M2.
- **R2. S5 needs `scoring.score` and `Score`, but they arrive in S6.**
  - Fix: move `score` and `Score` into S5, or have S5 run with `yesterday=[]`.
  - Source: readiness B2.
- **R3. `grid ledger verify` can't run in S4.**
  - `grid` is still the replay parser (`cli.py`), so `grid ledger` fails with argparse "invalid choice".
  - No step creates the subcommand CLI.
  - Source: codebase B2.
- **R4. The Actions prerequisites are incomplete.**
  - The warehouse state on the runner is missing (Stage 5 B1, Stage 7 C2).
  - `NWS_USER_AGENT` is required (`nws.py:77`).
  - `dbt-duckdb` is only a dev extra.
  - Token permissions are unstated, and no `.github/` folder exists.
  - Sources: codebase B4, readiness M5.
- **R5. The source-name claim (line 149) is false.**
  - Adding `ncei` touched four places: the `storage.land` set, the `storage.ingest` dispatch, the `cli.py` choices, and the `grid-temps` script.
  - Source: codebase B1, the same as Stage 5 Nit 13.

## Majors

- **R6. S3b `mart_day_history` is underspecified.** Open questions:
  - which folder, schema and materialization it uses;
  - whether `hour_utc` is hour-beginning or hour-ending;
  - which quality values count;
  - how ties are broken;
  - whether completeness is a count or a boolean;
  - the NCEI join and its quality filter.

  Sources: readiness M1, codebase M7.
- **R7. No step names its tests**, despite the "TDD" heading. Edge cases that need tests:
  - DST days, and a 25-hour day with one hour missing;
  - verify failing on a modified, deleted or late receipt;
  - no-call receipts;
  - frozen thresholds after a v2 definition.

  Sources: readiness M2, codebase M1.
- **R8. The v1 deletion list is incomplete**, and plain `dbt build` fails until it lands (`bge_node()` needs `bge_pnode_id`).
  - Missed items: the macro, three dbt tests, the `schema.yml` entries, the `serving` block, `powerbi/`, `test_freshness.py`, and the mixed tests in `test_dbt.py`.
  - Renewable share exists only in `grid_hourly`.

  Sources: readiness M3, codebase M3.
- **R9. The Owner decisions section is stale against PLAN.md v3.** Decision 2 has no default, and decision 1 has no reversal path.
  - Sources: readiness M4, codebase M2, style M4.
- **R10. The runner work belongs to no step.** Unowned:
  - workflow files and cron times, which must allow for UTC, DST shifts and delays;
  - the pinned issue;
  - branch protection;
  - the Pages deploy;
  - the repo secret and the merge to `main`.

  Source: readiness M5.
- **R11. S4 is underspecified.**
  - The `--since` scope versus a full scan is unresolved.
  - `Violation` has no fields.
  - It is unclear whether the hook is the pre-commit framework or a git hook.
  - The ledger-access guard test is not assigned to any step.

  Source: readiness M6.
- **R12. Components and CLIs have no owning step.**
  - The `run.py`/`cli.py` change and the `grid ncei daily-summaries` replay belong to no step.
  - It is unclear whether `grid-fetch`, `grid-backfill`, `grid-weather` and `grid-temps` survive.
  - `grid-freshness` breaks when `check` changes signature.

  Sources: readiness M7, codebase M4.
- **R13. Undecided items:**
  - the numeric dependency for least squares (no numpy today);
  - which module owns the shared types (`Forecast` cannot live in `ledger` without breaking the "pure modules import no IO" rule);
  - how `grid daily` runs dbt (`GRID_DATABASE`, the dbt.exe lookup, the send_bytes retry).

  Sources: readiness M8, codebase M6/M8.
- **R14. Fetch windows for `grid daily` are not specified.**
  - EIA allows at most 31 days and has a checkpoint.
  - NCEI needs an overlap window.
  - `bge-demand` and `fuel-mix` are never fetched, so they go stale.

  Source: codebase M5.
- **R15. `features` edge cases are open.**
  - Should "before as_of" use `issued_at` or `fetched_at`? Replayed bodies get the replay time.
  - What happens with a null high or low?
  - The complete-day rule needs to be "ok hours equal the date's expected hours".

  Sources: codebase M9, Stage 7 C7.
- **R16. "v1" means two things.** The index definition and the retired pipeline share the name, and the deletion has three different names across the doc.
  - Source: style M1, same as C13.
- **R17. S7 can't be checked.** "Docs" and "resume gate" are undefined.
  - PLAN.md's bar of 14 daily briefs plus 2 weekly scorecards should be copied in.
  - Sources: style M3, codebase M10, readiness N3.
- **R18. "Push time is the timestamp proof" overstates the evidence.**
  - A PC push also gets a push time.
  - The real difference is that `issued_at` is produced on GitHub's machines.
  - Source: style M5.

## Nits

- S3a's row has no done status and lists incomplete deliverables.
- The module map is missing the `LoadError` import from `fetch`.
- "The docs say so" (line 148) is untrue for now.
- `ledger.append` should reuse `storage.land`'s exclusive-create and integrity pattern.
- The `v1-final` tag target isn't stated. It is now tagged locally at e01a80d.
- S3c tests should read the definition through a fixture, not a path under `ledger/`.
- The `grid weekly` schedule is not covered.
- "The VPN blocks" has no object. "No new secret" is wrong for the PC option.
- Naming is inconsistent between `stress.py` and `features`.
