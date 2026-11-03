# S4 stopped after second independent NOT READY verdict

Historical report. Alder subsequently authorized the explicit witness split and
process-boundary rule. See [the current round](../alder-round/README.md); the
original evidence and rejected snapshot below remain preserved.

No stage, commit, push, main merge, protection change, or secret-store access
was performed. No S5 work started. Existing work and earlier evidence remain.

## Host evidence received

The coordinator reports the exact previously failing case passed once in
10.09 seconds. The full host suite collected and passed **207 tests in
239.25 seconds**. Those results apply to the snapshot before this revision's
publication change; they are not a pass for the current snapshot.

The supplied traceback confirms the failing path was dbt `execute_nodes` to
`pool.close`, then `_change_notifier.put(None)`, the queue writer, and Windows
`_send_bytes`. That supports the notifier diagnosis. The passing host suite
supports the previous runner change; it does not establish every shutdown or
failure path, every dbt caller, or the revised publication behavior.

Host `gh` authentication has **admin and push permission**. Host live state says
main is **unprotected** and Actions has **zero runs**. The connector's separate
403 response is not a claim about host `gh` capabilities.

## Bounded dbt changes completed

`publish.py` was a missed direct `dbt.exe` caller. It now launches
`sys.executable -m grid_pipeline.dbt_runner`, preserving its existing project,
profiles, isolated snapshot, validation arguments, timeout, error handling,
and publication pointer behavior. The v1 publication path was not retired or
redesigned. The earlier claim that all project invocations used the wrapper
was inaccurate; the inspected warehouse, dbt test helpers, and publication
caller are now routed. No claim is made about uninspected external commands.

New runner tests exercise concurrent notifier sends during close after success,
a nonzero CLI exit, and a query exception. They assert that close completes
and the original exit status or exception survives. These tests use a focused
pool/CLI harness, not a real Windows dbt process. Existing notifier reproducer,
lock-preservation, failure propagation, warehouse, and static guard tests also
ran: **24 passed in 0.63 seconds**. See `targeted-tests.txt`.

The publication integration test now asserts the actual subprocess uses the
runner. Additional timeout, startup-error, and nonzero/shutdown-error tests
assert one attempt and preservation of the prior publication pointer. These
require host DuckDB and have **not run in this sandbox**. A full host rerun and
independent check are still required after the latest edits.

## Exact unresolved blockers

1. **Prospective timing and historical visibility.** The current implementation's
   GitHub push-run timestamps can show a commit existed by a server timestamp.
   They do not establish that the repository was public at that timestamp.
   The witness integration has only mocked receipt tests; no real receipt has
   been independently witnessed by this implementation. Neither the mock nor
   the `timing: verified` label is evidence of historical public visibility.
   PLAN's existing requirement is not replaced by this added witness design.
2. **Dynamic external-process ledger access.** The current static/runtime guard
   does not enforce the supplied counterexample:
   `subprocess.run(['cat', os.environ['LEDGER_FILE']])` when the child does not
   import the package. Static literals and in-process auditing do not cover
   that boundary. No authorized enforcement mechanism for that demonstrated
   case has been established within the current S4 implementation. This finding
   remains open. The existing negative tests do not prove the entire requirement.
3. **Pre-commit and CI parity.** The hook uses `--integrity-only`; CI uses strict
   verification. They do not mirror full checks. The added strict witness design
   depends on a push that has not happened at pre-commit time. Requiring that
   same future witness locally is circular; keeping the weaker flag silently
   weakens the requested parity. No parity resolution was implemented or
   declared accepted. This is an unresolved conflict in the implementation,
   not authority to weaken CI or amend PLAN.
4. **Ordinary local selection.** `select_receipt` still invokes strict
   verification, whose witness reader rejects execution outside the named
   Actions environment. Therefore normal local selection after receipts exist
   remains blocked. There is no claimed local-selection fix in this revision.

The checker reports the merge-history counterexample addressed and the
historical-definition example accepted, pending runtime evidence. Their
regressions were included in the previous host suite, but that does not close
the other findings or provide a new independent READY verdict.

Resolving the open timing, enforcement, and parity boundaries requires
supervisor direction consistent with the existing user order and PLAN. This
report proposes no replacement plan or new security specification. Under the
stop-and-report instruction, the lead stops here rather than treating those
requirements as met or making further architectural changes.

## Gates and evidence still pending

No current-snapshot full-suite pass, new independent approval, S4 commit hash,
push, Actions run ID/pass, installed-hook read-back, or required-check protection
read-back exists. The host can perform the authorized Git and protection writes
after the blockers and checks are resolved; it is not blocked by the connector's
permissions. No such writes are requested while the verdict is NOT READY.

The existing 31 individual match classifications and 2,610 permission-denied
paths are unchanged in `../preflight-classification.json`. Current index and
prospective scan results are in `scans.json`. The index remains the previous
index, not a staged S4 snapshot, so the host still needs an exact intended-index
scan before any future commit.

`host-evidence.json` labels coordinator-supplied evidence.
`changed-source-hashes.json` identifies this revision's three changed code/test
files. Earlier implementation manifests describe their earlier snapshots.

Skills applied: codebase-memory for Tier 2 discovery and per-file coverage,
systematic-debugging and test-driven-development for the bounded dbt check,
technical-writing and unslop for this report. Relevant instructions were already
loaded in this session. Browser, deployment, secret-store workflows, alternative
planning, and delegated writing remain rejected by task scope or explicit order.
The independent worker remains host-coordinated Terra/xhigh; no substitute
worker or model was launched.
