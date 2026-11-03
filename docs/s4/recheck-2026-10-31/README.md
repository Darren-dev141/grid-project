# S4 fixes awaiting host rerun and independent recheck

Superseded status: the second checker returned NOT READY. See
[remaining blockers and bounded publication fix](../second-recheck-blockers/README.md).

The independent checker's last verdict remains **NOT READY**. This revision
addresses its six findings and the reported dbt failure, but is not a stage pass.
No files were committed or pushed. No S5 work or secret-store access occurred.

The coordinator supplied the previous host result: Python 3.14.7, pytest 9.2.0,
**1 failed, 180 passed, 1 warning in 215.48 seconds**. The failed test was
`tests/test_dbt.py::test_demand_build_rejects_bad_units_negative_and_nonfinite_values[electricity/rto/region-sub-ba-data-row5-demand_bge_demand_range]`.
Its dbt process raised `concurrent send_bytes() calls are not supported`.
The NWS tests retried the same error. The lead requested the raw host log and
complete traceback; they were not available during this revision.

## Changes against the six findings

| Finding | Revised behavior | Regression evidence |
| --- | --- | --- |
| Backdated receipts and forgeable commit dates | Uncommitted and staged receipts fail after the target local day starts. Default verification requires independent GitHub push-run timestamps for every historical receipt introduction. `--integrity-only` explicitly reports timing unverified. | Backdated candidate, staged candidate, missing-witness, and late-public-witness tests |
| Simplified merge history | Enumerate the complete reachable DAG without a ledger path filter. Compare every parent edge, including merges whose tree equals another parent. | Two-parent merge drops a definition; both branch refs are removed; verification fails |
| Exercised-code-only guard and PowerShell bypass | Scan maintained Python, PowerShell, shell, and workflow entry points; retain aliases and simple local call/return path flow. Runtime auditing installs on package import. Route PowerShell definition hashing through the ledger CLI. | Unexecuted Python, import aliases, helper functions, subprocess literals, PowerShell, shell fixtures; actual temporary violations fail the repository test |
| Partial staging | Reject all unstaged tracked changes, untracked nonignored files, and unresolved index entries before checks. Recheck the snapshot after tests, scanning, and ledger checks. | Partially staged source fails; fully staged source succeeds; untracked source fails |
| Receipt-of-record selection | `select_receipt` verifies first and selects latest issue time for that forecaster/date, including no-calls. Equal timestamps use the lexicographically greatest content hash as a fixed tie-break. | Latest stale-input no-call supersedes an earlier issuance |
| Later definition validates earlier receipt | Read definition bytes from the receipt's own Git commit and compare their hash there. Merge additions of an already existing receipt are not treated as new issuance times. | Receipt committed before its definition fails even after the definition is added |

The original PLAN discrepancy is unchanged: PLAN requires multiple content-hash
receipts under a forecaster/date directory and mandatory checks; the proposal's
single-file-per-day and optional-check language is not authoritative.

## Timing proof and local checks

Default `ledger verify` fails closed without a trustworthy publication witness.
In GitHub Actions it reads this repository's push workflow runs using GitHub's
automatically supplied, read-only job token. It uses server-created `created_at`
timestamps and verifies that the receipt commit is an ancestor of the observed
push head. Neither a timestamp supplied by a receipt nor a repository witness file
can certify timing. The request is pinned to `Darren-dev141/grid-project`, checks
the remote identity, bounds pagination, and suppresses response bodies and
credential-bearing HTTP errors. No EIA credential is used.

The CI job has `actions: read` and passes its built-in job token only to the
verification step. No agent fetched, printed, persisted, or moved a token.
This lookup has not been exercised against a real forecast receipt in Actions.
The real repository still has zero forecast receipts.

Before a commit, publication has not happened. The local hook therefore runs
the integrity checks with `--integrity-only`, after rejecting a mismatched
snapshot. Its result says `timing: unverified_integrity_only`. CI runs the strict
default command. Local integrity success does not certify prospective publication.
Absent or expired Actions history, unavailable Git objects, permission failures,
and lookup failures fail closed; no assertion of public timing is made from
commit dates alone. Actions retention is a limitation for long-lived receipts.

`select_receipt` also requires strict verification. It cannot silently choose an
uncommitted, backdated, or unwitnessed issuance for scoring.

## dbt diagnosis and change

The installed dbt `DbtThreadPool` inherits CPython's `ThreadPool`. The pool uses a
shared change notifier. On Windows, CPython's `SimpleQueue` has no writer lock,
and overlapping sends through the same pipe raise the observed error. This
mechanism is visible in the primary [CPython queue source](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/multiprocessing/queues.py),
[pool source](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/multiprocessing/pool.py), and
[Windows connection source](https://raw.githubusercontent.com/python/cpython/v3.14.0/Lib/multiprocessing/connection.py).
The precise host traceback still needs to confirm the affected notifier path.

`grid_pipeline.dbt_runner` supplies a serialized notifier context to dbt's
thread pool before any worker thread starts. It changes only the dbt child
process on Windows, leaves existing queue locks intact, and does not edit dbt or
CPython files. The warehouse and dbt test helpers use this runner. The second
review found that publication was missed; its correction is in the report above.
The wrapper relies on CPython's private `_wlock` and pool initialization order;
host verification on Python 3.14.7 is required before accepting it.

The focused reproducer raises the exact transport error without serialization
and completes overlapping sends with serialization. Retries were removed from
the warehouse, NWS, and NCEI paths. A remaining transport failure cannot become
a later passing retry; nonzero dbt results and SQL test failures remain failures.
The failed demand-model test's data-quality assertions were not relaxed.

This is a source-supported fix with focused regression evidence, not a claim
that the host integration failure has passed. The host must rerun the exact
failed case and the full suite once, without retry suppression.

## Guard coverage and limits

The static test scans all maintained entry points under `src`, `scripts`,
`tests`, `.githooks`, `.github`, and top-level code files. Archived source copies
under documentation remain evidence, not active modules, and were not rewritten.
It checks explicit ledger paths, simple aliases, local function arguments and
returns, literal subprocess code, shell assignments, and PowerShell hashing.
Synthetic pytest repositories are distinguished from the real repository;
explicit expected `PermissionError` assertions are negative tests.

The production audit hook protects the actual repository ledger in every Python
process that imports `grid_pipeline`. A fresh child process was allowed to read
directly before the fix and failed with the expected guard error afterward.
The static repository test failed for a never-called Python function and for an
unexecuted PowerShell `Get-FileHash` violation. Both temporary files were removed.
Logs are in this directory.

Static analysis is not a general proof for arbitrary Python. Dynamic path
obfuscation, cross-language generated code, native IO bypassing Python audit,
inherited descriptors, and independent programs that never import the package
remain limits. The guard is not an OS security sandbox. Independent review must
assess whether this explicit boundary satisfies S4; this report does not label
that finding independently closed.

## Verification and evidence

`targeted-tests.txt` records the current focused result. `verification.json`
distinguishes coordinator-supplied host evidence from locally observed checks.
`implementation-hashes.json` identifies the reviewed source snapshot.
The previous evidence files remain intact.

The first six reviewer counterexamples were added before their fixes and all six
failed. Additional static and notifier tests also failed before their changes.
The successful focused run covers all six findings and the notifier mechanism.
The complete host suite has not been rerun by this lead because its native
Python 3.14 environment remains unavailable inside the sandbox.

The original **31 individual candidate paths, rules, and classifications** and
all **2,610 unreadable-path errors** remain in
`../preflight-classification.json`. That evidence was not regenerated, changed,
or replaced by this revision. New scan results are in `scans.json` here.
The prospective scan reads working candidates; the index scan reads only the
existing index. No S4 files could be staged, so neither substitutes for the
host's final scan of the exact intended index. Pattern matching does not prove
that every possible secret encoding is absent.

## Host rerun and independent recheck

1. Preserve the current tree and use the existing host environment. Run the
   exact failed demand test, then `.venv/Scripts/python.exe -m pytest -ra` once.
   Use a fresh evidence directory. Return complete logs, counts, warnings, and
   the original transport traceback. Do not retry a failure into a pass.
2. Run `.venv/Scripts/python.exe -m grid_pipeline.ledger verify` and
   `.venv/Scripts/python.exe scripts/s4_secret_scan.py --prospective`.
   With zero real receipts, strict verification needs no witness API request.
3. Resume the separate read-only Terra/xhigh checker session
   `01a193dd-ea59-7031-a0ab-8300c0882aa8`. Have it recheck all six findings,
   the Windows notifier fix, guard limitations, and the source hashes here.
   Return its actual `turn_context` model and effort evidence and verdict.
   The checker must not write the implementation.
4. Do not commit or push while any review failure, test failure, or committable
   secret-scan issue remains. After independent approval, the host still needs
   to stage the intended files, pass the exact-index scan and snapshot checks,
   install the hook, recheck live remote refs, and complete the previously
   authorized feature-branch CI and main-protection gates. No main merge or S5
   action is authorized by this revision.

Skills applied in this revision: systematic-debugging and test-driven-development
for the new regressions; codebase-memory for Tier 2 discovery and coverage;
poteto-mode, how, architect, github, technical-writing, and unslop carried from
the preceding S4 work. Alternative planning, delegated implementation, browser
automation, deployment, and secret-store workflows remain rejected under the
fixed S4 scope, lead-edits rule, or explicit prohibition. The checker stays
host-coordinated because nested CLI launches are unavailable.
