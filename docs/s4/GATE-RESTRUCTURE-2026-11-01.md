# S4 Gate Restructure — Darren's Ruling, 2026-11-01 ~14:19 EST

Recorded by Hermes at Darren's direction (relayed by Alder). Supersedes the
prior "four checker issues" framing in S4-STATUS-2026-11-01.md for gate
purposes. PLAN.md requirements are unchanged; only the gate's precondition
set changes.

## New gate structure

1. S4 ACCEPTANCE closes on:
   - Issue 1 (subprocess guard) — done in source, unit tests only.
   - Issue 2 (witness split) — done by design, unit tests only.
   - Issue 3 (acceptance boundary bootstrap) completed.
   - The interrupted DAG fix finished and retested.
   - Full host suite green.
   - A fresh independent checker pass.
   - Host steps executed: commit, push, s4-acceptance tag, branch protection
     with ledger verify required, protection read back.
   Nothing else is an acceptance precondition.

2. ISSUE 4 IS RECLASSIFIED from a gate task to a POST-ACCEPTANCE WATCH.
   It is an event, not work: the first scheduled issuance that lands in the
   ledger AFTER acceptance, witnessed by CI, closes it.
   - Absence deadline: 7 days after acceptance. If no qualifying witnessed
     ledger receipt exists within that window, that absence is the reportable
     event. Report it as itself; do not let it sit as an "open issue."

3. Checker seat: per Darren's ruling, a Claude-family checker after the PC
   Claude seat resets (Nov 3, 06:00 ET) is acceptable; cross-family
   independence is a point in its favor. The DAG fix stays with the sol lead
   unless a handoff is judged cheaper — see Acknowledgment below.

4. Banked Codex reset stays IN RESERVE per Darren's 12:10 PM ruling today.
   NOT authorized for S4. Lead work requiring the weekly quota waits for
   Nov 6, 5:12 PM EST.

## Required answer — what writes a receipt into ledger/forecasts/ after acceptance?

Nothing currently does. The existing daily issuance path
(scripts/issue_stress.py, invoked by the scheduled run) writes its artifact
to docs/s3c/S3C-FIRST-ISSUANCE-*.json, NOT to ledger/forecasts/. It does
not call ledger.append_forecast. The ledger append API exists in
src/grid_pipeline/ledger.py and is tested, but no production caller invokes
it. The Nov 1 diagnostic confirms this: it is late, unscored, availability-
unverified, and lives under docs/s3c.

Therefore the post-acceptance watch's absence deadline exists precisely to
surface this gap. What would close it: S5 work — wiring the daily issuance
path to ledger.append_forecast with exclusive-create, real issue time, future
target date, and verified input availability — which does not exist yet.
Until that wiring lands, no qualifying receipt can appear, and the watch
will report absence at the 7-day deadline.

## Acknowledgment

Checker-seat choice: retain the sol lead (gpt-6.1-sol) for the DAG fix and
remaining implementation. Rationale: the DAG fix is small and already
understood from the checker's report; the lead has the full context of the
interrupted edits and the test harness. A Claude-family checker will be
requested after the PC Claude seat resets (Nov 3, 06:00 ET) for the final
independent pass, per Darren's ruling that cross-family independence is a
point in its favor. Cost: zero; the banked Codex reset is not used.

Skills used: codex (autonomous-ai-agents/codex), grid-stress-forecaster,
systematic-debugging, test-driven-development, github, unslop.
