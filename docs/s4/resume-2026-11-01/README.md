# Resumed S4: current source, proof, and remaining gates

This round resumed after the interrupted usage-limit turn. The lead inspected
the actual dirty tree and did not assume the partial edits had passed tests.
No project Git writes, commits, pushes, protection changes, secret-store access,
account creation, paid services, live PJM ingestion, or S5 work occurred.

The coordinator's previous **228 passed in 301.60 seconds** belongs to the
pre-fix snapshot digest
`736ed329ffa3dc43c7a8b89b13b9b4bd2334d3fed6fc0f43b527c9ee27fe7ad5`.
It is not a current-source pass. A fresh host suite and independent recheck
are mandatory before any commit or push.

## What landed before interruption

The relative-path guard normalization, remote-tag lookup, all-reachable-ref
future-time check, and blob-ID lookup changes were present on resumption.
The old DAG exemption was still present: any pre-boundary origin exempted
identical content on another incomparable origin, and one witness could satisfy
any origin. The two current DAG counterexamples were rerun before fixing that
logic and both failed in **46.07 seconds**. See `dag-red-current.txt`.

The interrupted turn's 14 failing relative-path/anchor/future-time regressions
remain preserved in `../review-relative-anchor/red-tests.txt`. That is prior
RED evidence, not a claim of current failure or a post-fix pass.

## Current behavior

- Process boundaries resolve the whole supplied path against the child's cwd,
  normalize separators, `.` and `..`, and check arguments, config-derived values,
  inherited or explicit environment, executable, and working directory. The
  environment and config regressions include `./ledger`, backslashes, parent
  aliases, redundant separators, and changed cwd. Config cases remove the path
  from the environment so the argument route is tested independently. The child
  imports no grid package and contains no ledger path literal. Passing bytes
  through stdin still works. This is not an OS sandbox for all native programs.
- Receipt-free witness verification queries the expected readable public
  repository and the exact remote acceptance tag. Only an explicit missing-tag
  response permits initial bootstrap. Once that remote tag exists, a branch
  missing the boundary policy fails closed, even with zero receipts. API lookup
  failures do not mean absence. Tag protection itself is still a host gate;
  it has not been set or verified here.
- The first-seen origins of one content-addressed receipt are the minimal
  ancestry frontier of its introduction commits. Git dates do not order
  incomparable commits. Each strict pre-C origin is historical. Each origin on C,
  after C, or incomparable with C requires witness coverage. A historical copy
  does not exempt another incomparable introduction. A witness for one new origin
  does not satisfy another; a witnessed merge head can cover both if it descends
  from both. Output separates receipt counts, origin counts, and first-seen commit
  IDs. Mixed-origin content reports pending timing until every required origin
  is covered. Local selection stays integrity-based and does not require network.
- Future issue times are rejected across all historical introductions on all
  reachable refs, not only the checked-out files. All parent edges still enforce
  append-only history, including merge deletion and rename-as-delete/add cases.
  Definition bytes must exist at the receipt commit.
- Git tree/index listings are decoded inside Python. Subsequent content reads
  pass only blob object IDs to `git cat-file blob`; no `COMMIT:ledger/...` or
  `:ledger/...` spec is passed. The default index scanner uses the same ID-only
  principle even though it is a standalone scanner. Boundary tests inspect actual
  Git arguments and scanner calls. The earlier exception for path-bearing object
  specs is withdrawn; the explicit path/content order is followed literally.

The local hook remains the integrity-only pre-push check under Alder's ruling.
CI adds witness verification only for required post-boundary origins. No test
fixture, mock API response, or synthetic acceptance tag is evidence that the
real witness integration has run.

## Current verification

`focused-final.txt` records the final focused run for this source. Intermediate
checks recorded **42 passed in 238.30 seconds** and **5 object/API checks passed
in 15.29 seconds**. Those intermediate counts are not a full-suite claim.
`local-verification.json` records actual command exits and sanitized output.
Witness bootstrap now needs remote absence evidence even with zero receipts;
an unavailable API in this sandbox must not be reported as a bootstrap pass.

The supervisor must rerun the native host suite, using the current hashes in
`implementation-hashes.json`, and resume the independent checker
`01a19539-2804-7ff3-bc5f-9e2109727053` read-only. Its previously observed actual
`turn_context` was `gpt-6.1-terra`, effort `xhigh`; its last verdict was NOT READY.
No new independent pass is claimed. The checker did not author implementation.

## Nov 1 issuance investigation: not a qualifying receipt

The newly found file is
`docs/s3c/S3C-FIRST-ISSUANCE-2026-11-01.json`, SHA-256
`01075035842a7ed11c2c5ee0108f064d35fa69197a816e719e609f06a67c57ec`.
It reports issue time **11:15:49.359408 EST**, target **Nov 1**, a **07:00 EST**
cutoff, `issued_late: true`, `UNSCORED/stale_load`, and availability unverified.
Local Git inspection found it untracked with no commit in any reachable ref.
The generator currently targets the issue date and writes this diagnostic with
exclusive creation. These current script edits were pre-existing on resumption
and were preserved; the lead did not rerun or alter the artifact or generator.

The actual ledger contains only the existing 343-byte definition. No forecast
receipt, acceptance policy, or local acceptance tag exists. `issuance-assessment.json`
records the inspected fields, SHA, file inventory, and chronology. The investigation
did not infer first usable availability from an index timestamp or filesystem mtime.

PLAN states: **"Predictions are committed as files before outcomes exist and
never back-edited; the stress index is a published, versioned definition."**
The same-day, late, uncommitted diagnostic cannot be retroactively qualified,
retargeted, backdated, or counted as a witnessed receipt. It is preserved exactly.
There is no genuine qualifying local receipt to push through the real witness
gate. A future authorized genuine call must have its real issue time, future
target date, actual freshness/availability evidence, canonical exclusive ledger
append, and commit/push after the accepted boundary. No S5 work is authorized to
manufacture that gate; it remains waiting.

## Bootstrap chronology and host actions

The receipt-free C / immutable tag / append-only policy B design remains. However,
after the remote tag exists, a tag-push workflow on old C without the policy must
fail closed. That expected anti-replay denial is not a green bootstrap and must
not be retried into a pass or hidden. Keep the original successful branch-push
run for C as the bootstrap reference. Then B, which adds the genuine policy
record, must have its own successful branch CI. Record both outcomes honestly.
No tag or protection has actually been created or verified by this lead.

Follow `HOST-RECHECK.md` before the existing host bootstrap commands. Only after
fresh independent approval and a passing host suite may the supervisor perform
authorized Git/GitHub steps. Reverify live identity, refs, visibility, and protection
immediately before pushing. No force-push, reset, stash, discard, main merge,
secret migration, account creation, or paid resource is permitted. S4 is incomplete
until actual CI/protection read-back and a genuine receipt witness also pass.

## Secret evidence and skills

The 31 prior matches remain excluded under `.venv`; **10 were independently
corroborated and 21 were not**. The 21 are not all binary: candidate 9 is a source
comment. Earlier statements labeling all 21 binary are corrected, not repeated
as fact. No unsupported per-match corroboration mapping is asserted. The original
per-match paths, rule IDs, offsets, hashes, and historical lead classifications
remain in the preserved preflight report; classification is not independent proof.
All 2,610 unreadable-file errors were permission denials under `.venv`, with six
excluded directory errors. Current scans are in `scans.json`; the existing index
is not the intended staged S4 snapshot. Host must scan that exact index before
each future commit, with no matching values printed or written.

Skills searched/reused: poteto-mode, systematic-debugging, test-driven-development,
codebase-memory (Tier 2 discovery, coverage checks, current-source fallback),
technical-writing, and unslop. GitHub instructions remain applicable to the host
handoff. Alternative planning, delegated writing, browser/deployment workflows,
and secret-store access were rejected by the fixed scope and explicit orders.
No new model or independent authoring worker was substituted.
