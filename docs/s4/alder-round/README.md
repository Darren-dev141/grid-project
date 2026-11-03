# S4 implementation under Alder's ruling

S4 remains incomplete until a fresh host suite, a fresh independently verified
Terra/xhigh review, real feature-branch Actions, protection read-back, and one
genuine prospective pipeline receipt through the witness flow are observed.
No S5 work has started. No Git writes, account creation, paid resources, secret
store access, or EIA key movement were performed by this lead.

PLAN.md was read in full. Its S4 requirements still govern: content-addressed
receipts, exclusive creation, append-only full-history verification, and ledger
access ownership. Alder explicitly resolved the hook/witness split; it is no
longer reported as a PLAN conflict. The proposal's one-file-per-day and optional
verification language remains superseded by PLAN. No new plan was drafted.

## Process boundary: bytes, not ledger filesystem paths

The guard checks process creation after arguments are resolved, including
subprocess arguments, inherited or explicit environment values, executable, and
working directory. It also handles audited system/exec/posix-spawn calls.
Passing the real repository ledger path through `os.environ` or a config object
is rejected before the external child starts. The child in the regression imports
no grid package and has no ledger path literal in its source.

All three demonstrated routes failed their tests before the fix: argument,
inherited environment, and config. They pass after the guard change. A positive
test reads through `ledger.read_definition` and sends bytes through stdin to an
ordinary child without a grid import. It passes. The static source guard and
in-process audit remain in place; the process check closes the demonstrated
dynamic-path boundary rather than claiming the source scanner can infer it.

The prospective secret scanner now routes file bytes through `ledger.read_content`
too. Its former direct read of the definition failed a regression under the
runtime guard before correction. Prospective scanning refuses symlink components
rather than following them to an unverified or private target. Index scanning
reads committed blob content through Git, not symlink targets.

Git plumbing inside `ledger.py` reads immutable/index object content by object
specification, such as `COMMIT:ledger/...`, not a filesystem path supplied to a
child. Worktree/index/tree enumeration no longer passes ledger filesystem
pathspecs to Git; filtering happens inside the owner module. External diff and
text conversion are disabled for worktree comparisons. A Git object spec is not
permission for an arbitrary child to receive a ledger filesystem path.

This remains a project IO policy, not an OS sandbox against arbitrary native
programs or intentionally generated code. Existing limitations must stay visible
in the fresh independent review. No subprocess is given a private secret path.

## Boundary and witness split

Local `ledger verify` defaults to integrity checks. The hook explicitly runs
`--integrity-only`, checks the exact staged snapshot against working source
before and after checks, and runs the full tests and index secret scan. This is
the authorized pre-push check. CI runs integrity and the additional `--witness`
check. The earlier requirement for identical flags has been superseded by Alder.

Local `select_receipt` uses integrity verification and returns `witness_status`.
It does not require Actions or a network call. The fixed selection rule remains
latest issuance before the target's local midnight, including no-calls, with
content hash as the deterministic tie-break for equal timestamps. Returned status
is added in memory; the original receipt is never changed.

The acceptance boundary uses a reviewed, receipt-free source commit **C**:

1. Commit and push C only after exact-index scanning, full host tests, and fresh
   independent source approval. Its actual push CI can pass with zero receipts,
   reporting `bootstrap_no_receipts`. That is not S4 completion.
2. After C's actual `CI` run passes, create an annotated `s4-acceptance` tag
   pointing to C. Lock tag updates and deletion with the supplied active ruleset,
   no bypass actors, and read it back. The tag is not backdated; its date is not
   trusted as timing evidence.
3. Through the ledger CLI, append exactly one `ledger/policy/s4-acceptance.json`
   in a later commit **B**. It records C, its Git tree hash, the annotated tag
   object hash, and C's successful Actions push-run ID. The post-commit reference
   avoids embedding C's own unknown hash into C. It is exclusive-create.
4. CI on B checks local tag/tree/ancestry, append-only policy origin, the remote
   tag object and target, and the actual successful push run for C's CI workflow.
   A changed tag, replaced record, changed tree, wrong run, or missing remote
   evidence fails closed. Local policy verification does not claim remote proof.

The content hashes make substitution detectable. The ledger history invariant
prevents editing or deleting the record, and main protection plus the immutable
tag rule protect the references against normal force/update paths. Repository
administrators remain trusted to maintain those rules; this is not a claim of
protection against an owner rewriting all governance. The host must preserve the
observed tag-object hash and protection read-back in its external evidence too.

Receipts whose first introduction is a strict ancestor of C are labeled
`historical_not_required`, with integrity checks only. C itself is inclusive:
receipts first introduced on C or its descendants require prospective witnessing.
Incomparable introductions are not silently treated as historical; witnessing
is required conservatively. Full reachable Git DAG parent edges are checked,
including merge deletions, renames represented as deletion/addition, and the
definition bytes present at each receipt's own commit.
If the identical content-addressed receipt already occurs strictly before C,
a duplicate introduction on an incomparable parent does not turn that existing
historical content into a new prospective receipt. A regression covers that DAG.

Witnesses establish existence from the mechanism's acceptance boundary forward.
They do not retroactively witness older receipts, and they do not prove historical
repository visibility. Output explicitly says `public_visibility: not_inferred`.
Commit dates cannot establish the boundary or substitute for the push-run
timestamp. API mock tests verify behavior only; they are not real acceptance or
publication evidence. Local fixture tags and run ID 123 are never used in the
real repository or cited as integration evidence.

`bootstrap_no_receipts`, `pending_boundary_commit`, and `anchored_local` are
incomplete states. Only actual remote evidence yields `anchored_remote`; even
that does not satisfy the separate genuine-receipt gate with zero witnessed
receipts. Missing or expired API history fails closed for required witnesses.

## Real receipt gate is waiting

The observed clock was 2026-11-01 03:31:32 UTC, Oct 31 23:31:32 EDT. The original
authorized first issuance window is Nov 1 07:00 EST, 12:00 UTC. No clock was
advanced and no issuance was fabricated. No real forecast receipt exists here.

The existing `scripts/issue_stress.py` writes an S3 diagnostic for the same date
as issuance. Its Oct 31 JSON cannot be reclassified as a qualifying prospective
receipt: PLAN requires commitment before the target local day begins. It remains
untouched. At a Nov 1 morning issuance, a qualifying forecast must target a
future local day and retain actual source availability and issue timestamps.
Do not invent future weather, backdate an issue, reuse realized weather as a
forecast, or blindly run that same-day diagnostic to satisfy this gate.

Alder allowed the real gate to wait. This round builds everything that can be
verified before the window. The supervisor must supply the actual qualified
pipeline invocation and availability evidence for the genuine receipt at the
authorized time. If unavailable, report the gate waiting; do not implement S5
features or start S5 merely to make the receipt exist.

## Evidence and pending verification

`focused-tests.txt` records the latest sandbox run. Its counts are observations
of isolated regression fixtures, never a substitute for the fresh host suite.
The earlier coordinator-supplied host result was 207 passed in 239.25 seconds;
it predates subsequent edits. The host-confirmed original traceback runs through
dbt `pool.close` and the notifier writer, supporting the bounded Windows fix.
Publication is now routed through the runner; host publication integration and
failure-path tests must run again on this final snapshot.

A separate fresh Terra/xhigh worker has been requested from the supervisor.
Its session ID and actual `turn_context` verification are still pending; the
previous worker's verdict is not reused as approval for this round.

The candidate evidence has an explicit correction under Alder's ruling:
**31 prior matches were excluded by `.venv/`; 10 were independently corroborated
and 21 binary matches were not independently corroborated.** Alder did not require
individual corroboration of the excluded 21. The earlier per-match paths, rule
IDs, offsets, short hashes, and lead classifications remain preserved in
`../preflight-classification.json`; its classification labels must not be read
as independent proof for those 21. No unsupported per-ID corroboration mapping
is invented here.

All **2,610 prior file errors were permission denials under `.venv`**, and the
six directory errors were excluded cache/generated-test directories. Neither the
old excluded-set scan nor a zero-pattern working scan proves every possible
secret encoding absent. `scans.json` contains current prospective and existing
index scans; the host must scan the exact intended index immediately before
each commit. No matching values may be printed. The EIA zero-file history is
coordinator-stated; no key-store or exact-key lookup was performed.

## Host execution

Follow `HOST-STEPS.md` in order. Do not copy API response credentials or use
`gh auth token`. Do not force-push, merge main, or create accounts. The host has
admin/push permission; earlier connector restrictions do not restrict host `gh`.
Recheck all live refs, identity, public visibility, permissions, and protection
immediately before each push. Current local HEAD was independently re-read as
`e01a80d1f74f4cf4ec2b45045bc82f95ff6a2087`, on `feat/energy-ingestion` with the
expected remote identity. Those observations are not a future push preflight.

Skills searched and applied: poteto-mode, codebase-memory (Tier 2 plus coverage
and current source), how and architect for the existing seams, systematic-debugging,
test-driven-development, github, technical-writing, and unslop. Alternative
planning and delegated implementation were rejected by the fixed-plan and
lead-edits order. Browser, deployment, and secret-store workflows are unnecessary
or forbidden. Delegation remains host-run with a fresh verified Terra/xhigh seat.
