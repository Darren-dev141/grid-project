# Consolidated EGM review: docs/architecture-s3-s7.md

Run: October 29, 2026, uninterrupted mode, all five stages. 10 fresh-context reviewers
(Claude, plugin `egm` 0.1.0). All reviewers completed; none were "not run". No fixes have been
applied to the target yet.

Split: the doc has no standard implementation header, so `## Build order` (line 152) was
chosen as the boundary. FeatureRange is lines 1-151; DetailedRange is lines 152-171.

Stage reports in this folder:

| Stage | Report |
| --- | --- |
| 5 | `zoom_out_report.md` |
| 6 | `comprehension_report.md` |
| 7 | `critic_report.md` |
| 8 | `intermediate_zoom_out_report.md` |
| 9 | `implementation_readiness_report.md` |

## Verdict

**The doc is not ready to build from.** The structure holds up: every reviewer accepted
dbt for cleaning, pure Python for judgment, and `ledger` as the single owner of the ledger.

What fails is the operating model under GitHub Actions, plus a set of decisions the build
order hands to implementers.

Stage 8 cautioned against over-correcting. Most blockers can be fixed by deleting or
rewording lines, not by adding machinery. The doc should point to `PLAN.md` for its
purpose and decisions rather than becoming a second plan. The action list below follows
that rule.

## Actions by priority

### 🔴 Blockers

| # | Action | Smallest fix (per Stage 8) | Traces to |
| --- | --- | --- | --- |
| A1 | Say where runner state lives | The warehouse is rebuilt each run (about 14 EIA pages plus about 8 NCEI requests). The Actions cache only speeds that up. The ledger is the only durable state. List the needed environment: `NWS_USER_AGENT`, the EIA key secret, dbt as a runtime dependency. | S5-B1, C2, R4 |
| A2 | Make backdating detectable, and fix the protection conflict | Drop "required check". Protection blocks force-push and deletion only. `ledger verify` runs inside the daily job before push, and in CI on every push. A new receipt fails if its target day has already started by the verifier's clock (pushed range only). The issue comment carries the receipt hash. Change "nothing to cherry-pick" to "a backdated receipt is detected". | S5-B2, S5-M4, C1, C5, S6-M2, S8-3/4, R18 |
| A3 | Decide the S3c model before S3b | State the NCEI-to-NWS date alignment and the fit/forecast point (BWI vs Reisterstown). Fill every v1 TOML value with its rationale. | R1, C8, S8-16 |
| A4 | Fix build-order dependencies | `score` and `Score` move to S5 (or S5 renders with no receipts until S6). The `grid` subcommand CLI (extending `cli.py`, with `grid replay <source>`) moves to S4. | R2, R3, S5-N11 |
| A5 | Mirror the mechanics fixes into PLAN.md v3 | PLAN.md lines 29, 31, 33 and 58 repeat the flawed text. | S8-1 |

### 🟡 Majors

| # | Action | Traces to |
| --- | --- | --- |
| A6 | Replace "Owner decisions" with "Decisions (resolved, see PLAN.md)". Delete the NCEI-declined fallback, the Task Scheduler option and the manual commit and push. | S5-M3, R9, S8-7, C13 (part) |
| A7 | Add a two-line objective that links PLAN.md. Define BGE, S3-S7 and Darren's role. Do not add Goals, Alternatives or Risks sections. | S6-M1, C3, C4, S8-5, S6-M7 |
| A8 | Delete the "PJM in one new file" paragraph. Keep `forecaster_id` in the path. | S5-M5, C9, S8-8 |
| A9 | One scorecard rule: a target date with no receipt of record counts as a miss. Score with the definition named in the receipt. Post the weekly scorecard as an issue comment. | C6, C10, C14, S8-6/12 |
| A10 | Complete-day rule: ok hours equal the local date's expected hours. Say how a non-ok hour next to the peak affects settling. | C7, R15 |
| A11 | Specify `mart_day_history`: folder and schema, hour convention, quality filter, tie-break, NCEI join. | R6 |
| A12 | Name tests per build step, including edge cases. | R7 |
| A13 | Retire v1 by scope ("everything that serves price or Power BI") and do it first, so plain `dbt build` works. | R8, S5-N16, S8-17 (**in progress: W1**) |
| A14 | Give the runner work an owning step: workflow, cron time, permissions, pinned issue, protection, Pages from artifact, secret, merge. | R10, S5-N12, S8-14 |
| A15 | Settle the open small decisions: numeric dependency, shared-types module, how dbt is invoked, fetch windows (including `bge-demand`/`fuel-mix`, or drop them). | R13, R14, S5-N15 |
| A16 | Rename the retired pipeline "legacy v1 pipeline" everywhere. The index keeps v1/v2. | C13, R16 |
| A17 | Make S7 checkable: 14 consecutive daily briefs plus 2 weekly scorecards, with the files named. | R17 |
| A18 | Command surface: keep the existing console scripts and remove only `grid-publish`. Document `replay`. | C11, R12, S5-N11 |

### 🟢 Nits

| # | Action |
| --- | --- |
| A19 | Say the hash covers the bytes as written; drop "canonical JSON". Use "identifies", not "certifies". Show one example receipt instead of the notation. |
| A20 | Drop the pre-commit hook (here and in PLAN.md). |
| A21 | Correct the source-touch count (four places). Fix future tense for work that is done. |
| A22 | Mark the S3a row done. Link the evidence for measured claims. Use anchor links. Add fence languages. Wrap lines consistently. |
| A23 | `nws_forecast_latest`: drop "the docs say so". Optionally delete the view at S5. |

## Contested or downgraded

| Finding | Decision |
| --- | --- |
| Stage 5 Nit 7 ("always scan full history") | Overruled by Stage 8. Use two scopes: the full history for non-add changes and hash mismatches, and the pushed range for late adds. |
| Stage 7 C3 (no problem statement) | Downgraded from Blocker to Major. A two-line objective that links PLAN.md is enough. |
| C4 (add Goals, Alternatives and Risks sections) | Rejected as scope creep for an architecture input doc. A baseline forecaster is new product scope and goes to the owner. |
| RFC 3161, OpenTimestamps, a receipts branch, a score ledger, forecaster discovery | Rejected as speculative machinery. |

## Facts being gathered (worker swarm, October 29)

These determine the details of A1, A2, A3, A10 and A14 before the doc is revised.

| Worker | Question |
| --- | --- |
| W2 | GitHub rules on required checks, bot bypass, cron, cache, retention and Pages |
| W3 | DST and completeness counts in the live demand data |
| W4 | NWS gridpoint for BWI vs Reisterstown |
| W5 | Current repo settings |
