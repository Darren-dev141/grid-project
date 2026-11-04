# S4 independent checker report (Claude, cross-family): 2026-11-03

| Field | Value |
|---|---|
| Checker provider / model | Anthropic **Claude Opus 5.5** (`claude-opus-5-5`), Claude Code harness inside T3 Code, as configured for this thread |
| Date / time | 2026-11-03, work 06:57–07:20 EST; report written 07:14–07:20 EST |
| Suite result observed | **249 passed in 345.68 s (0:05:45), exit 0**: `.venv` Python 3.14.7, pytest 9.2.0, clean `env -i` shell, wall time 347 s |
| Skills / playbooks used | **none**. No skills, playbooks, subagents or delegation. Direct tool use only: shell, file reads, greps, read-only `git`/`gh` |
| Role | Verification only. No commit, push, tag, protection change, S5 work or source edit. The only file written in the repo is this report |
| Reviewed snapshot | branch `feat/energy-ingestion`, HEAD `e01a80d1f74f4cf4ec2b45045bc82f95ff6a2087`, uncommitted working tree; S4 file hashes in Appendix A |

## Verdict per PLAN.md S4 criterion

PLAN.md S4 line: "`ledger.py` with `verify`; CI workflow + pre-commit hook; branch protection on. The receipts ledger goes live here. Includes the ledger-access guard from the proposal's known weaknesses: a test asserting no module other than `ledger` opens paths under `ledger/`."

| Criterion | Verdict | Basis |
|---|---|---|
| `ledger.py` with `verify` | **PASS** | Full reachable-DAG scan for non-add changes, hash/path mismatches, late issue and commit, frozen definitions, staged/working mismatch. `grid ledger verify` and `python -m grid_pipeline.ledger verify` both exit 0 on the real tree (`bootstrap_no_receipts`). 35 ledger/boundary/regression tests pass. |
| CI workflow | **PASS (present; never run)** | `.github/workflows/ci.yml`: secret scan, full tests, `--integrity-only`, then `--witness`. The repo has zero Actions runs, so CI is first exercised by HOST-STEPS step 2, as designed. |
| Pre-commit hook | **PASS, with a robustness defect** | `.githooks/pre-commit` runs `precommit.py`: snapshot check, index secret scan, full tests, `verify --integrity-only`. It is not installed yet (`core.hooksPath` unset), which matches the gate. Defect H3 below can make it fail on harness refs. |
| Branch protection on | **Not yet: host step** | `main` is unprotected, there are no rulesets, no `s4-acceptance` tag. This is correct for this gate. |
| Receipts ledger goes live | **Mechanism ready; no receipt; witness path not exercised** | No receipt exists in any ref. No production code calls `append_forecast`. The witness path has never run against GitHub. Nobody may claim it works yet (§5). |
| Ledger-access guard test | **PASS on the letter; strength partial** | `test_repository_ledger_access_policy` plus the runtime audit hook (conftest and package import) assert the PLAN requirement, and the issue-1 routes are mutation-proven. I reproduced 5 sibling bypass routes and 9/15 static misses (§2–§3). |

**Overall: READY for the HOST-STEPS sequence**, with three required amendments to how the host steps are run (H1–H3 in §7). None of them is a PLAN S4 criterion failure, so none carries a PLAN sentence; each is a defect in the procedure or the environment. The guard gaps (§3) must be fixed before S5 adds any production ledger caller. This verdict is **not** "S4 complete": HOST-STEPS step 6 (a genuine witnessed receipt) cannot happen until something writes receipts, and nothing does today.

---

## 1. Full host suite: what I observed

- **First attempt was invalid (my mistake, recorded for honesty).** My first clean shell stripped `PATH` down to `/usr/bin:System32` with no `git`. That gave 7 errors in `test_ledger.py`, all in the `repository` fixture (`git init`). I stopped that run at about 40%. It is not evidence about the code.
- **Valid run:** `env -i` with PATH = `.venv/Scripts`, `/mingw64/bin` (git), `/usr/bin`, `System32`; `DBT_SEND_ANONYMOUS_USAGE_STATS=false` (as CI sets); `-p no:cacheprovider`; `--basetemp` outside the repo.
  Result: **249 passed in 345.68 s**, exit 0, started 07:03:49 and ended 07:09:36 EST. Per file: day_history 5, dbt 15, dbt_runner 7, fetch 27, freshness 6, ledger 8, ledger_access 30, ncei 18, ncei_dbt 2, nws 17, nws_dbt 9, publish 5, s3c_diagnosis 2, s4_boundary 17, s4_regressions 10, storage 9, stress 20, stress_inputs 11, stress_rulings 26, warehouse 5.
  The count matches the builder's 249. The time does not: I measured 346 s against the builder's 758.80 s. Not a concern, but the builder's figure is not what I observed. My light read-only probes ran at the same time as part of this run.
- **Tree mutation check:** I took `git status --porcelain --untracked-files=all` and ledger file hashes before and after. The ledger was unchanged. The only new path was `docs/s3c/S3C-FIRST-ISSUANCE-2026-11-03.json`, written at 07:00:07 by the daily `scripts/issue_stress.py` job running outside this thread. That was before the valid run started, and no test references `docs/s3c`. The suite does not dirty the tree.

## 2. Issue 1 (subprocess bypass): verified in source

**Source.** `ledger_access.install_runtime_guard()` is installed by `src/grid_pipeline/__init__.py` (every production process) and by `tests/conftest.py`. Its audit hook inspects `subprocess.Popen`, `os.system`, `os.exec` and `os.posix_spawn`. For each it checks the executable, cwd, every argument and every environment value (inherited or explicit). It denies any value that contains the absolute ledger path, or a slash-bearing or bare `ledger`/`.`/`..` token that resolves under `ledger/` relative to the child's cwd. The coordinator's closing condition ("the demonstrated bypass must be in the guard test suite") is met: `test_external_child_cannot_receive_dynamic_ledger_path` covers argument, environment and config, and `test_relative_dynamic_child_path_is_denied` covers 6 relative forms × env/config.

**Reproduction of the old bypass (my probe, guard installed, child only reads the definition):**

| Route | Result |
|---|---|
| 1a `subprocess.run([py, -c, child, <abs ledger path>])` | DENIED |
| 1b same, path via environment variable | DENIED |
| 1c `./ledger/...` argument, cwd = repo | DENIED |

**Do the tests go red if it reopens? Mutation test in an isolated copy** (`%TEMP%\s4check\mut`, imported via `PYTHONPATH`; the real repo was untouched):

| Mutation | Tests that turned red |
|---|---|
| A: process-creation check disabled | 13 new failures: all 3 issue-1 routes and all 12 relative cases |
| B: relative-path resolution disabled | 12 (every relative case) |
| C: environment values not inspected | 7 (every environment case) |
| D: owner-frame check for `open` disabled | `test_ledger.py::test_guard_blocks_non_owner_and_allows_owner` |

**Verdict: issue 1 is closed as the coordinator ruled.** The demonstrated routes are denied, and the tests genuinely fail when the fix is removed.

**But the class is not closed.** These sibling routes reached a child that read the ledger file (343 bytes, the real definition):

| Route | Result | Why |
|---|---|---|
| 2e `os.spawnv(P_WAIT, py, [..., <abs ledger path>])` | **BYPASS** | `os.spawn` is not among the audited events. On Windows, the host platform, this is the native spawn family; `os.posix_spawn` does not exist here. Same shape as the original issue 1. |
| 2c MSYS-form absolute path `/c/Users/.../ledger/...` to Git's `wc.exe` | **BYPASS** | Resolved against the current drive, so it does not match the protected prefix |
| 2a `--input=ledger/definitions/...` (option=value relative path) | **BYPASS** | The token is not path-shaped at its start |
| 2b path delivered on **stdin** | **BYPASS** | stdin is never inspected |
| 2d path inside a config **file** passed to the child | **BYPASS** | Indirection |
| 3a in-process DuckDB `read_text('ledger/...')` | **BYPASS** | Native IO raises no Python `open` audit event |

2b and 2d cannot be fixed by an argument check and need the static layer or review. 2a, 2c and 2e are cheap fixes in `external_path` and the audited-event list. Also, `alder-round/README.md` says the guard "handles audited system/exec/posix-spawn calls". That is literally true but misleading on Windows.

Minor: `test_relative_dynamic_child_path_is_denied[...-./grid-project/ledger/...-..]` depends on the checkout directory being named `grid-project`. It fails in a copy with any other name. That holds in the real checkout and in Actions (`.../grid-project/grid-project`), so it does not block.

## 3. Ledger-access guard test: does it meet PLAN, and is it strong enough?

PLAN requires "a test asserting no module other than `ledger` opens paths under `ledger/`". Two layers implement it:
1. **Static:** `check_repository()`, asserted `== []` by `test_repository_ledger_access_policy`. It does AST taint-to-sink analysis on `.py` files and regex checks on shell, PowerShell and YAML files under the repo root, `src/`, `scripts/`, `tests/`, `.githooks/` and `.github/`, skipping only `ledger.py`.
2. **Runtime:** the audit hook denies `open`, `listdir`, `scandir`, `remove`, `rename`, `mkdir` and `rmdir` under the real `ledger/` unless `ledger.py` is on the call stack.

It meets the letter, and the repository passes today. Strength, from my probes of `violations()` with realistic shapes:

| Shape | Static | Runtime (only if a test executes it) |
|---|---|---|
| `open('ledger/...')`, `Path('ledger')/...read_bytes()`, `os.path.join(...,'ledger',...)`, f-string, `rglob` loop, `tomllib.load(Path(...).open())` | flagged | denied |
| `shutil.copy('ledger/...')`, class attribute `self.root = Path('ledger')`, default argument `root=Path('ledger')`, **cross-module constant** (`from x import LEDGER_DIR`) | **missed** | denied |
| **DuckDB** `execute/sql("... read_json('ledger/...')")`, `sqlite3.connect('ledger/...')` | **missed** | **missed** (native IO) |
| `os.spawnv(..., 'ledger/...')`, path on stdin | **missed** | **missed** |

Python and script files outside the scan roots are not scanned (`world-model/`, `synthetic-twin/`, `dbt/`, `docs/`). I checked them by hand: none opens `ledger/` today. `synthetic-twin/run_pipeline.py` goes through `ledger.read_definition`, and `world-model/provenance.py` only refuses ledger paths. The archived copies under `docs/s3c/evidence-2026-10-31-sol/**` contain direct `read_bytes()` of `ledger/...`, but they are inert evidence snapshots.

**Judgment:** the guard reliably catches the common accidental violation, direct Python file IO in the scanned trees. It will **not** catch a module that reads receipts through DuckDB, the warehouse engine this project already uses. That is the most likely real violation at S6 (scoring against actuals). It also won't catch a cross-module path constant in code no test executes. This is not a host-step blocker, because the guard is not an immutable artifact. It **should be fixed before S5/S6 code touches the ledger**. Cheapest strong addition: a static rule that any string literal containing a `ledger/` path segment, in any non-owner file under any scanned root (including `world-model/` and `synthetic-twin/`), is a violation unless allowlisted. Plus `os.spawn`/`os.startfile` audit events and option=value tokenisation at runtime.

## 4. Hook vs CI behaviour against the ruled witness design

| Ruling | Code | Result |
|---|---|---|
| Local hook = integrity verification | `precommit.py:28` runs `verify --integrity-only`; integrity mode makes no network call | matches |
| CI adds witness checks | `ci.yml` runs `--integrity-only`, then `--witness` with `GITHUB_TOKEN` and `actions: read` | matches |
| Witness applies only to receipts first seen at or after C | `ledger.py:396-407`: historical means a *strict* ancestor of `acceptance_commit`; C itself, its descendants and **incomparable** introductions are prospective (conservative) | matches; covered by `test_receipt_on_acceptance_commit_is_prospective` and both incomparable-origin tests |
| Historical receipts labeled, integrity-only | status `historical_not_required`; counted in `historical_receipts` | matches; `test_historical_selection_is_offline_and_labeled` |
| Witness reported, not gating, for historical | the witness loop (`ledger.py:427-438`) iterates `prospective` only | matches |
| Local selection not blocked by historical receipts | `select_receipt` calls `verify(integrity_only=True)` and attaches `witness_status` in memory | matches (test patches `_push_witnesses` to raise) |
| Receipt-free branch before B cannot pass `--witness` once the tag exists | `ledger.py:424-425` | matches; `test_remote_anchor_prevents_missing_policy_bootstrap` |
| Issue 4 (visibility at historical push) | output always says `public_visibility: not_inferred`; `_remote_acceptance_tag` requires the repo to be public *now* | watch item, as ruled |

Wording note: the coordinator's text calls the local hook the "pre-push check". The code installs a **pre-commit** hook, as PLAN says. PLAN governs, and the code matches PLAN.

## 5. Genuine receipt for the end-to-end witness exercise: **none exists**

- `ledger/` holds only `definitions/stress-index-v1.toml` (sha256 `63cb5726…9fbfca`, matching `definition-hashes`). It is untracked in the index.
- None of the **62** commits reachable from any ref has a path under `ledger/forecasts/`.
- `append_forecast` has **no production caller** in `src/`, `scripts/`, `synthetic-twin/` or `world-model/`. `scripts/issue_stress.py` writes `docs/s3c/S3C-FIRST-ISSUANCE-<date>.json`. All four of those files (Oct 31 to Nov 3) target their own issue date. `_validate` would reject them ("issued after target day began"). They are `stale_load`, and three record `input_availability_verified: false`.
- The repo has **zero Actions runs**. The real `_push_witnesses` and `_verify_boundary_remote` have never run against GitHub. Every witness test monkeypatches them, and `_push_witnesses` has no direct test of its env gating, pagination or parsing.
- What I could check: the real API field shapes the code depends on, using public repos' push runs. `path` is `.github/workflows/<file>.yml`, `created_at` is ISO-8601 with `Z` (which `datetime.fromisoformat` accepts), and `event`, `head_sha` and `conclusion` are present. That is a shape check only, not an exercise.

**Conclusion: the end-to-end witness exercise did not happen.** No one should claim the witness path works. This is consistent with GATE-RESTRUCTURE (issue 4 moved to a post-acceptance watch) and with HOST-STEPS step 6. Step 6 cannot be satisfied until code wires the daily issuance into `ledger.append_forecast` with a future target date, which GATE-RESTRUCTURE places in S5.

## 6. Git and remote state against the gate

| Item | Observed |
|---|---|
| Branch / HEAD | `feat/energy-ingestion` @ `e01a80d1f74f4cf4ec2b45045bc82f95ff6a2087`. No S4 commit; the S4 work is uncommitted. |
| Unpushed | 3 pre-S4 commits (`769474f`, `229c231`, `e01a80d`) ahead of origin's feature branch |
| Remote heads | feature `60194df7f30cdbf5a6772774fa4e0bdb11b25403`, main `863d4fca31a0139e0384ef672232fd8b705d869e` (match HOST-STEPS' expected values) |
| Remote tags | none. `git/ref/tags/s4-acceptance` returns 404. |
| Local tags | `v1-final` only: annotated, on `e01a80d`, "retired v1 price/Power BI pipeline"; local-only and unrelated to S4 |
| Repo | `Darren-dev141/grid-project`, public; origin URL has no embedded credentials |
| Actions runs | 0 |
| `main` protection / rulesets | unprotected / none |
| Hook | `core.hooksPath` unset |
| Prospective secret scan (metadata only) | 306 files, 33.7 MB, **0 candidates, 0 unreadable** |

The state matches the gate: no S4 acceptance commit, push, tag or branch protection exists.

## 7. Host-step hazards (must be handled when running HOST-STEPS)

**H1: the commit manifest is stale, so step 2 will stop as written.** `intended-commit-files.txt` (264 entries, dated Oct 31) omits **42** current untracked paths, and this report makes 43:
- the status files `S4-STATUS-2026-11-01.md`, `WORKSTREAM-B-STEP1-STATUS-2026-11-02.md` and `suite_out.txt`
- `docs/s4/GATE-RESTRUCTURE-2026-11-01.md`, `docs/s4/resume-2026-11-01/*` and `docs/s4/review-relative-anchor/*`
- `docs/s3c/CADENCE-TRACKER.md`, `DIAGNOSIS-STALE-LOAD-2026-11-02.md` and the issuance artifacts for 11-01 to 11-03
- all of `synthetic-twin/` and `world-model/`

`check_snapshot` rejects any untracked file, so step 2's explicit pre-check and the hook will stop (fail-safe). The coordinator must decide what goes into C. Two notes for that decision:
- Anything added beyond the manifest is outside this review. I checked only that `world-model/` and `synthetic-twin/` don't open `ledger/`.
- The daily `issue_stress.py` job writes a new untracked file into `docs/s3c/` at about 07:00 ET. Don't run a commit across 07:00, because the hook's before/after snapshot comparison spans the full test run.

**H2: the step-3 tag push will produce a red CI run on C.** `ci.yml` uses `on: push` with no branch or tag filter, so pushing `s4-acceptance` triggers a run on C. That checkout has no `ledger/policy/s4-acceptance.json` while the remote tag exists. `ledger.py:424-425` raises "remote acceptance anchor exists but boundary policy is absent", after the full suite has already passed. This does not break gating: B's verification checks the recorded *bootstrap* run ID, and step 5 reads check runs on B. But HOST-STEPS says to stop on unexpected test failures. Either treat this red run as expected, or filter tag pushes out of the workflow, which would be a code change needing a recheck.

**H3: T3 checkpoint refs can break the local hook at step 4.** `verify` walks `git rev-list --all`. In this checkout that includes `refs/t3/orchestration-v2/checkpoints/*`. Those are T3 Code's turn snapshots of the **entire working tree, untracked files included**: checkpoint `3a45eec`, created at the start of this thread, holds 305 paths against 65 tracked, including `ledger/definitions/...`. It is why `verify` reports `history_commits: 1` today. That is harmless now. I simulated step 4 in a temporary repo with the unmodified `ledger` module:

| State | Result |
|---|---|
| Record staged, no checkpoint | OK (`pending_boundary_commit`) |
| A checkpoint ref captured the uncommitted record | **FAIL** "acceptance boundary differs from its append-only origin" (the hook blocks B) |
| After committing B, checkpoint ref still present | **FAIL** "acceptance boundary has multiple origins" (local verify stays red) |
| Checkpoint ref deleted | OK (`anchored_local`) |

CI is unaffected, since `refs/t3/*` is never pushed. **Mitigation:** run step 4 from `establish-boundary` through `git commit` inside a single T3 turn, or outside T3. Durable fix (a code change, small recheck): limit verification to `--branches --tags --remotes`, or exclude `refs/t3/*` and `refs/stash`.

## 8. Other findings and watch items (non-blocking)

- **W1: witness API cap.** `_push_witnesses` lists `actions/runs?event=push`. GitHub returns at most 1,000 results for filtered run listings. Past about 1,000 push runs, older prospective receipts lose their witness, and `--witness` fails closed. CI then turns permanently red on a required check. That is years away at this cadence, but the design should be revisited before then. For example, record the witness run ID per receipt and look it up directly.
- **W2: the receipt branch is unprotected.** HOST-STEPS step 6 pushes commit D to `feat/energy-ingestion`. Only `main` gets protection, and PLAN's "Branch protection blocks force-push" is what stops deletion by history rewrite (`verify` cannot see a receipt that a rewrite removed). Protect the feature branch against force-push too, or land real receipts only on `main`.
- **W3: CI on Linux is unexercised.** The tests look hermetic (synthetic inputs, `tmp_path` warehouses), and I reasoned through the Windows-specific guard tests for Linux. Step 2's CI run is the first real check.
- **W4: off-B pushes fail.** After the tag exists, CI on any commit that does not descend from B fails the witness step, for example a PR based on today's `main`. This fails closed by design, but expect it.
- **Issue 4** stays a post-acceptance watch as ruled, with a 7-day absence deadline per GATE-RESTRUCTURE. Given §5, absence at that deadline is the expected outcome unless S5 wiring lands first.

## 9. Where the status docs disagree with the code (code wins)

1. **Issue numbering differs.** S4-STATUS numbers issue 3 as the boundary bootstrap and issue 4 as the real end-to-end witness. The coordinator's numbering is: 2+3 the hook/CI split and local selection, 4 public visibility at historical push. I used the coordinator's numbering.
2. **S4-STATUS §4 credits issue 1's closure to the wrong change.** It names a static-scanner name collision (`subprocess.run` against a user `run`) as the root cause. That change, the `isinstance(node.func, ast.Name)` guard at `ledger_access.py:125`, fixes a false positive. The bypass itself is closed by the runtime process-creation check (`ledger_access.py:48-63`). Both are present.
3. **S4-STATUS §2 is stale on issue 3.** It says issue 3 is "OPEN … no green test" for the receipt-free branch after the tag. The fix (`ledger.py:424-425`) and its test exist and pass.
4. **`docs/s4/README.md` is stale on subprocesses.** It says the guard "does not claim coverage of … separate subprocesses". That predates the process check.
5. **`alder-round/README.md` overstates spawn coverage.** It claims system/exec/posix-spawn coverage, but `os.spawn*` and `os.startfile` are uncovered (§2).
6. **Builder suite figures differ from mine.** The builder reported 249 passed in 758.80 s; S4-STATUS's summary still cites "228 passed in 301.60 s". I observed **249 passed in 345.68 s**.
7. **Prospective scan size grew.** S4-STATUS reports 264 files; I observed 306 files, still 0 candidates.
8. **Recorded hashes are out of date.** No evidence file records the current `ledger.py`, `ledger_access.py`, `test_ledger_access.py` or `test_s4_boundary.py` hashes. The latest set (alder-round, Oct 31 23:46) predates the Nov 1 edits. Appendix A identifies the snapshot I reviewed, and the host should confirm C matches it.
9. GATE-RESTRUCTURE's "Nothing currently writes a receipt" is **confirmed**.

## 10. Overall

The S4 source meets PLAN's S4 code criteria, the suite is green on my clean run, and issues 1–3 are fixed in source as ruled, with tests that genuinely fail when the fixes are removed. Git and remote state match the gate.

**READY for HOST-STEPS 1–5, provided the host:**
- reconciles the stale manifest before step 2 (H1)
- treats the step-3 tag-push red run as expected (H2)
- runs step 4 within one T3 turn or outside T3 (H3)

Before S5 code touches the ledger, the guard gaps in §3 must be closed. The witness path is unexercised and must not be claimed to work. "S4 complete" (HOST-STEPS step 6) is unreachable until receipts are actually written.

---

### Appendix A: reviewed snapshot (sha256)

```
cbabc095e231f2ae86009ae2cb11f25bab538bce6eda9f1161fb9c7378274df6  src/grid_pipeline/ledger.py
be87f6002fa10f11aca9f2124bdc5ed319f69cb2d3a43ed3418e624bad0ee9b9  src/grid_pipeline/ledger_access.py
b863142d8d20f14e1efe7209b3a834be3865339c0a5c875f2ae03bca761c9c64  src/grid_pipeline/precommit.py
ccfc01e437409e5b66b9cb6ad27300d1e95a8453f490a67de96213bdede52a80  src/grid_pipeline/__init__.py
e145e4c6060e105dd63b8383fe9561c3e6849e8da8c9440430f1d6e23abb520d  .github/workflows/ci.yml
acda127e3876c8022fd2d84413ed9f69343531cefbb183a5bce3a1ad9910b520  .githooks/pre-commit
2189dc65ed029ca8022fe412363f85b8a4228ff3ad4360a2796ac10977a640d9  scripts/s4_secret_scan.py
e72a70e8656204c0465a6df787281be97266509233ed1e5c67f8c367712dc0d5  tests/conftest.py
5d61c34a60611c0957d4dbeb5f6163eeddca7707f21b214c93cd5e90cdd24315  tests/test_ledger.py
d1f6a511a8b56c0be74c7412e9d152481343a4e013ef1435382df5474a9aff91  tests/test_ledger_access.py
5011ee904fe0ccdee4458a37748b151548f389d0f4d9a8b98093195932dfd903  tests/test_s4_boundary.py
aaf94163956223c18a95d3cbdad89143d6d5f0a6fdb0906ea395fd75de37db66  tests/test_s4_regressions.py
63cb57268398ee62525499c64ecbf4c7694f2d5960eccf2a0eb2f3f3059fbfca  ledger/definitions/stress-index-v1.toml
```

### Appendix B: evidence kept outside the repo

All under `C:\Users\ajbig\AppData\Local\Temp\s4check\`:

| File | Contents |
|---|---|
| `suite_claude.txt` | the valid run |
| `suite_attempt1_nogit.txt` | the invalid first attempt |
| `status_before.txt`, `status_after.txt`, `ledger_*.txt` | tree and ledger snapshots |
| `probe_guard.py`, `probe_guard2.py` | runtime bypass probes |
| `probe_static.py` | static-scanner probes |
| `mut\` | mutation copy; source restored and checked with `cmp` |
| `sim_checkpoint.py` | H3 simulation; its temp repo is `C:\Users\ajbig\AppData\Local\Temp\s4sim-34vqh5o5` |

Every probe child only read the definition file. Nothing was written under the real `ledger/`. Remote calls were read-only GETs: `git ls-remote`, `gh api` on this repo, and public workflow runs on `actions/checkout` and `pallets/flask`.
