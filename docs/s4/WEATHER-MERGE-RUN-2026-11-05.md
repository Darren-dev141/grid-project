WEATHER MERGE RUN, 2026-11-05 (PC side, Hermes)
Window: 06:22 to about 06:40 America/New_York. Repo: C:\Users\ajbig\Documents\grid-project (main checkout, directory name grid-project).
Status of this file: UNTRACKED on purpose. Not committed, not pushed.
Format mirrors docs/s4/STALELOAD-MERGE-RUN-2026-11-05.md.
Scope kept: no issuance run, no issue_stress.py run, no Hermes job triggered/edited/executed (job files read only), no EIA, no ledger.py change, no branch deleted, checkpoint tag not pushed, no force push.

RESULT
Merged fix/weather-fresh-nws @ a05c740 into main by merge commit (no conflicts), pushed to origin/main, CI green (321 passed), local full suite 321 passed, prospective scan 0 candidates, verify integrity-only anchored_local exit 0, verify witness anchored_remote exit 0, ledger receipts 0 / pending 0. scripts/refresh_nws_bwi.py is now tracked on main.

1. PRE-MERGE STATE (read-only, 06:22)
main                      df1d1c0778b21793feb7f3276ec6eaaee00319d8 (df1d1c0)  == origin/main  [precondition OK]
fix/weather-fresh-nws     a05c74058cce11e363e246bcc555c6276cb28cf5 (a05c740)                  [precondition OK]
merge-base                40b75ab5aed76562db2e0af33bb7d06619f9d5d6 (40b75ab; already in main)
Weather worktree path     C:/Users/ajbig/Documents/grid-project-weather  branch fix/weather-fresh-nws, HEAD a05c740, git status --porcelain: 0 lines (clean)  [precondition OK]
Stale-load branch         fix/stale-load-keyless = 40b75ab5aed76562db2e0af33bb7d06619f9d5d6
Stale-load worktree       C:/Users/ajbig/Documents/grid-project-staleload  HEAD 40b75ab, 0 porcelain lines (clean)
Contact with both worktrees: git --no-optional-locks status --porcelain, rev-parse, branch --show-current only.
Ancestry: main is NOT an ancestor of the branch. The branch was built on 40b75ab (in main), but main had since gained 3 commits (0244323, 84a51af, df1d1c0 = HOST-STEPS v2 evidence, s4-acceptance boundary anchor, stale-load merge). Branch carries 4 commits main lacks: 394fc80, 954f3ba, db07934, a05c740. Fast-forward impossible; merge commit required.
Main checkout working tree before: 2 untracked files only (HOST-STEPS-V2 run record, STALELOAD-MERGE run record).

2. CHECKPOINT TAG
git tag pre-weather-merge df1d1c0778b21793feb7f3276ec6eaaee00319d8 (lightweight, local only). Read back: pre-weather-merge -> df1d1c0778b21793feb7f3276ec6eaaee00319d8. Remote tags after push: only s4-acceptance (ef29124, peeled e954035). Tag was not pushed. No branch deleted (fix/stale-load-keyless, fix/weather-fresh-nws still present).

3. PREVIEW
git merge-tree --write-tree --name-only main fix/weather-fresh-nws -> exit 0, tree 6fdfbd96acaff65045f180dce1dc9656f320dba3, no conflict entries.
Branch diff vs merge-base touches 16 paths; main side since merge-base touched .gitignore, docs/s3c/evidence-2026-10-31-sol/*, docs/s4/* evidence, docs/workstream-a/holdout-source.json, ledger/policy/s4-acceptance.json. The two sides are disjoint.
Protected-file check: the branch does NOT touch src/grid_pipeline/stress.py, anything under ledger/, the boundary record, or the manifest. The branch DOES modify scripts/issue_stress.py (+29/-8: imports load_nws_bwi_forecast, build_features takes weather from the loader, weather_fresh = complete pair with updateTime age 0..12h before input cutoff, calls load_nws_bwi_forecast in main()). Main did not change that file since the merge-base, so there is no conflict; the STOP rule is for conflicts and did not fire. Stated here because it is a protected path that changes on main.

4. MERGE
Method: git merge --no-ff fix/weather-fresh-nws -m "Merge fix/weather-fresh-nws into main — BWI NWS forecast source with W3 provenance, end-date night alignment, weather_fresh gate, 05:00 refresh script"
Result: ort strategy, 06:23:17, exit 0, no conflicts, no manual resolution.
Resulting HEAD: d452d24362df90d7c0dd1a1ecc6643411798b5ee (d452d24). Parents: df1d1c0778b21793feb7f3276ec6eaaee00319d8, a05c74058cce11e363e246bcc555c6276cb28cf5.
Tree d452d24 = 6fdfbd96acaff65045f180dce1dc9656f320dba3, identical to the merge-tree preview.
git diff df1d1c0..HEAD: 16 files changed, 1261 insertions, 16 deletions. Only protected path changed: scripts/issue_stress.py. Nothing under ledger/, no stress.py change.

5. PUSH
Command: git -c credential.helper= -c "credential.helper=!gh auth git-credential" push origin main (gh admin lane, same as stale-load). Not a force push. Verbatim:
    remote: Bypassed rule violations for refs/heads/main:
    remote: - Required status check "tests-and-ledger" is expected.
    To https://github.com/Darren-dev141/grid-project
       df1d1c0..d452d24  main -> main
Exit 0. ls-remote origin refs/heads/main = d452d24362df90d7c0dd1a1ecc6643411798b5ee == local HEAD. git status -sb: main...origin/main (in sync).
Consequence of the bypass (as with stale-load): d452d24 was on main before its check had run; the check ran afterwards (section 6a).

6. POST-MERGE VERIFICATION (main checkout; .venv/Scripts/python.exe 3.14.7; PYTHONPATH=C:/Users/ajbig/Documents/grid-project/src)
HEAD during verification: d452d24362df90d7c0dd1a1ecc6643411798b5ee. Raw logs: C:/Users/ajbig/AppData/Local/hermes/cache/scratch/weathermerge-out/ (timeline.txt, scan.out, integrity.out, witness.out, suite.out, ci.log, *.exit)

6a. CI
Run id 42018571022, workflow CI, event push, head sha d452d24362df90d7c0dd1a1ecc6643411798b5ee, created 11:23:26Z, updated 11:28:06Z. Status completed, conclusion success (tests-and-ledger 4m37s, all steps success). Check run tests-and-ledger, app_id 15368, completed/success on d452d24.
https://github.com/Darren-dev141/grid-project/actions/runs/42018571022
CI details: secret scan (exact index blobs) candidates [], files 353; Full tests "321 passed in 246.39s (0:04:06)"; ledger integrity anchored_local (history_commits 4, CI shallow view); witness anchored_remote (history_commits 4).

6b. Prospective scan (python scripts/s4_secret_scan.py --prospective), 06:23:34, exit 0:
{"bytes": 31574776, "candidates": [], "files": 355, "scope": "prospective working files", "unreadable": []}
Result: 0 candidates, 0 unreadable.

6c. verify --integrity-only, 06:23:36 to 06:24:40, exit 0:
acceptance anchored_local, history_commits 8, receipts 0, pending_receipts 0, witnessed_receipts 0, timing unverified_integrity_only.

6d. verify --witness, 06:24:40 to 06:25:46, exit 0:
acceptance anchored_remote, history_commits 8, receipts 0, pending_receipts 0, witnessed_receipts 0, timing witness_checked.

6e. Full suite (python -m pytest -ra --basetemp <scratch>/weathermerge-out/pytest-basetemp), 06:26:01 to about 06:36, exit 0:
======================= 321 passed in 606.46s (0:10:06) =======================
321 passed, 0 failed, 0 errors. This independently confirms the 321 figure the weather branch's own record claimed (a05c740). git status after the suite: only the 2 pre-existing untracked records; the suite left nothing behind.

7. LEDGER STATE
acceptance anchored_remote (witness) / anchored_local (integrity-only, by design). receipts 0, pending_receipts 0, witnessed_receipts 0, no origins. Nothing written or faked. history_commits 7 -> 8 locally (previous baseline at df1d1c0 was 7); I attribute the +1 to the new merge commit, inference only, not traced in ledger.py.

8. 05:00 ET HERMES JOB (job 164a999a98f8) - SCRIPT PATH CONFIRMATION (read only; nothing executed or edited)
Job definition (C:\Users\ajbig\AppData\Local\hermes\cron\jobs.json, read only): name "Grid NWS BWI forecast refresh 05:00 America/New_York", script "refresh_nws_bwi.py" (the Hermes scripts wrapper), no_agent true, schedule "0 5 * * *", enabled true, state scheduled, workdir C:\Users\ajbig\Documents\grid-project, deliver local, next_run_at 2026-11-06T05:00:00-05:00.
Wrapper (C:\Users\ajbig\AppData\Local\hermes\scripts\refresh_nws_bwi.py, read only): sets REPO = C:\Users\ajbig\Documents\grid-project, SCRIPT = REPO / "scripts" / "refresh_nws_bwi.py"; if not SCRIPT.exists() it prints "refresh_nws_bwi: missing <SCRIPT>" to stderr and returns 1; otherwise runs it with REPO/.venv/Scripts/python.exe, cwd=REPO.
Path the job looks for: C:\Users\ajbig\Documents\grid-project\scripts\refresh_nws_bwi.py
Confirmed on main after the merge:
  git ls-files -s: 100644 13ed26d55b9aba5d99098effb130aa89ed1f26ea 0  scripts/refresh_nws_bwi.py
  HEAD:scripts/refresh_nws_bwi.py == 13ed26d55b9aba5d99098effb130aa89ed1f26ea == fix/weather-fresh-nws:scripts/refresh_nws_bwi.py (byte-identical blob, 1481 bytes in the object; working copy is 1526 bytes with CRLF checkout, git hash-object of the working file returns the same blob)
  origin/main tree contains the same blob (git ls-tree origin/main).
  File exists on disk in the main checkout (created 06:23 by the merge).
Why it matters: the job's first scheduled run, 2026-11-05 05:00:20, FAILED because the file did not exist yet. Saved output (C:\Users\ajbig\AppData\Local\hermes\cron\output\164a999a98f8\2026-11-05_05-00-20.md): "Script exited with code 1 ... refresh_nws_bwi: missing C:\Users\ajbig\Documents\grid-project\scripts\refresh_nws_bwi.py". jobs.json still shows last_status "error" for that run. This is the expected pre-merge failure, not a defect in the merge; the job record will keep showing error until its next run (2026-11-06 05:00 ET) overwrites it. I did not trigger it.
Import check (read only): with PYTHONPATH unset, .venv python resolves grid_pipeline to C:\Users\ajbig\Documents\grid-project\src\grid_pipeline\__init__.py (editable install), so the wrapper's subprocess, which sets no PYTHONPATH, can import the repo code from the main checkout.
Not verified: that the live fetch succeeds on the network (it was not run), and that NWS_USER_AGENT is present in ~/.hermes/.env (not checked; the wrapper has a default).
Related: the existing 07:00 launcher (d977b52c965c) is unchanged by this merge; scripts/issue_stress.py on main now calls load_nws_bwi_forecast, so the first 07:00 issuance after this merge will use the weather loader. Not run or inspected-by-execution here.

9. CLOSE-OUT CHECKS
9a. fix/stale-load-keyless: ref 40b75ab5aed76562db2e0af33bb7d06619f9d5d6, unchanged. Worktree C:/Users/ajbig/Documents/grid-project-staleload: HEAD 40b75ab, 0 porcelain lines, untouched.
9b. fix/weather-fresh-nws: ref a05c74058cce11e363e246bcc555c6276cb28cf5, unchanged during the whole run (unlike the stale-load run, nobody moved it). Worktree grid-project-weather: HEAD a05c740, 0 porcelain lines. Branch kept, not deleted.
9c. docs/s4/W2-SAMEDAY-RUN-2026-11-05.md: tracked, blob 7fcbf6e55e79117fc628d799b8769b3ebd1ae667 in df1d1c0 and in HEAD, no diff vs HEAD; sha256 e42afdd0d2bf37585d15d3bb6fa5581abea896beeae638ad1ca9aa53bf2c0a5f before and after.
9d. docs/s4/STALELOAD-MERGE-RUN-2026-11-05.md: still present, still untracked, sha256 80f06390b902ceefd5d8858e92c03144b1d8a87c246d4d5a453a658aa0d37c9e before and after. docs/s4/HOST-STEPS-V2-RUN-2026-11-05.md: sha256 c24da356ba1d70d9fe4187fa0198e416eb963241d49ae754f106bdbc718b61a8 before and after.
9e. Other worktrees: not touched (t3 worktrees, w3check, wxcheck, prunable scratch/verify/grid-project2 entry all left as they were).
9f. Final: main d452d24362df90d7c0dd1a1ecc6643411798b5ee local and remote. Tags: pre-staleload-merge, pre-weather-merge (local), s4-acceptance, v1-final.

10. DEVIATIONS AND CAVEATS (stated plainly)
1. Merge type: the task said to fast-forward if ancestry allowed, else --no-ff. Ancestry did not allow it (main had advanced 3 commits past the merge-base), so this is a merge commit d452d24, not a fast-forward. Within the procedure; the task's "favorable ancestry" expectation held in the sense that the base commit is already in main and the merge was conflict-free.
2. Protected path: scripts/issue_stress.py changed on main via the merge (no conflict, so no STOP). Flagged, not blocked.
3. Push used the admin bypass of the required check "tests-and-ledger", as in the stale-load run; main briefly held d452d24 before its check ran. The check passed afterwards.
4. The 05:00 job already ran once today (pre-merge) and errored for the missing script; this record only confirms the path now exists. The next real test is 2026-11-06 05:00 ET.
5. The local full suite took 606 s (CI 246 s); both 321 passed. The prospective scan scope (355 working files) differs from CI's (353 index blobs) by the two untracked records; this file itself, written after the scan, was not covered by that scan.
6. history_commits +1 is inferred, not traced.
7. Open items from the stale-load record that this merge does not change: EIA key absent; strict 07:00:00 cutoff awaiting Darren's ruling; ledger.append_forecast still not called from src/ or scripts/ (receipts 0).
8. Left alone: idle git-remote-https processes and dirty t3 worktrees noted in the stale-load record; not re-examined.
