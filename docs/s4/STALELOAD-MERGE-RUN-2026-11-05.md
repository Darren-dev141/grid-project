STALELOAD MERGE RUN, 2026-11-05 (PC side, Hermes)
Window: 05:4x to 06:03 America/New_York. Repo: C:\Users\ajbig\Documents\grid-project (main checkout, directory name grid-project).
Status of this file: UNTRACKED on purpose. Not committed, not pushed.
Scope kept: no issuance run, no issue_stress.py run, no EIA, no ledger.py change, no 07:00 gate change, no weather merge or rebase, branch and checkpoint tag kept.

RESULT
Merged fix/stale-load-keyless @ 40b75ab into main by merge commit (no conflicts), pushed to origin/main, CI green (308 passed), local full suite 308 passed, prospective scan 0 candidates, verify integrity-only anchored_local exit 0, verify witness anchored_remote exit 0, NCEI wiring confirmed.
One deviation to read: the weather worktree (grid-project-weather) was NOT in the same state at close-out as at Step 1. Another actor committed there during my run. I did not write to it. Details in section 9b.

1. PRE-MERGE STATE (read-only)
main                      84a51af43c3b324462f0d793b0305f7976c3cfae
fix/stale-load-keyless    40b75ab5aed76562db2e0af33bb7d06619f9d5d6
merge-base                f0adcbaf1b1c92559900f6c89afc53a88ee2fbc7
origin/main (ls-remote)   84a51af43c3b324462f0d793b0305f7976c3cfae
s4-acceptance (remote)    tag object ef291241a6ec41e16e59930510e5a219f0a941d0 -> e954035a50692600053f977fa97733354a1e0f3e
Ancestry verdict: main is NOT an ancestor of the branch. They had DIVERGED from f0adcba. Main carried 2 commits the branch lacked (0244323, 84a51af: housekeeping evidence, s4-acceptance boundary record, ledger/policy/s4-acceptance.json). The branch carried 6 commits main lacked (ccb10a1, 4b5c316, 5bbc735, 724126a, 374d038, 40b75ab). Fast-forward was impossible; a merge commit was required.
Conflict preview before merging: git merge-tree --write-tree --name-only main fix/stale-load-keyless returned exit 0 with tree f23860ce9fa52c8bd64365d7411cf86e77b3d9cc and no conflict entries. The two sides touched disjoint paths. The branch changes stress.py and issue_stress.py but main did not, and main changed ledger/policy/s4-acceptance.json but the branch did not, so no STOP-rule file conflicted.
The branch had no upstream and was not on the remote (remote heads: main, feat/energy-ingestion).

2. WORKTREES, BEFORE (git --no-optional-locks status --porcelain, so no index refresh writes)
main checkout   C:/Users/ajbig/Documents/grid-project                      main                          84a51af   1 line: ?? docs/s4/HOST-STEPS-V2-RUN-2026-11-05.md
t3-1a0cc244     .t3/worktrees/grid-project/t3-1a0cc244                      t3/nws-weather-ingestion      2601085   clean
t3-378eaf5c     .t3/worktrees/grid-project/t3-378eaf5c                      t3/eia-demand-models          1169c62   8 lines (1 M tests/test_dbt.py, 7 ??: eia_bge/pjm demand sql, eia_demand.yml, 4 dbt tests)
t3-8a2dfe33     .t3/worktrees/grid-project/t3-8a2dfe33                      t3/eia-backfill-ingestion     1169c62   4 lines (M pyproject.toml, fetch.py, fetch_cli.py, tests/test_fetch.py)
t3-9668dd3e     .t3/worktrees/grid-project/t3-9668dd3e                      t3/retire-v1-price-powerbi    34670e8   clean
staleload       C:/Users/ajbig/Documents/grid-project-staleload             fix/stale-load-keyless        40b75ab   clean
weather         C:/Users/ajbig/Documents/grid-project-weather               fix/weather-fresh-nws         954f3ba4b80f2bc79259a076c8cbda11b0d5a4e6   10 lines, NOT clean:
                  M dbt/models/cleaned/nws.yml
                  D dbt/models/cleaned/nws_forecast_daily_by_end.sql
                  D dbt/models/cleaned/nws_forecast_daily_by_end_date.sql
                  D dbt/models/cleaned/nws_forecast_daily_end.sql
                  D dbt/models/cleaned/nws_forecast_daily_enddate.sql
                  D dbt/models/cleaned/nws_forecast_daily_night_end.sql
                  M tests/test_nws.py
                  M tests/test_nws_dbt.py
                  M tests/test_stress_inputs.py
                  ?? tests/test_weather_fresh_gate.py
                (status text sha256 0054fa4d398a9f233a379c48c03164513fbe92c2108bf914ebf46277f7f206ec)
w3check         C:/Users/ajbig/Documents/w3check/grid-project               (detached)                    724126a   1 line: ?? W3-CHECKER-RESULTS.md
scratch verify  C:/Users/ajbig/AppData/Local/hermes/cache/scratch/verify/grid-project2   detached 394fc80, directory missing, listed prunable (not pruned by me)

3. CHECKPOINT TAG
git tag pre-staleload-merge 84a51af43c3b324462f0d793b0305f7976c3cfae (lightweight, local only).
Read back: pre-staleload-merge -> 84a51af43c3b324462f0d793b0305f7976c3cfae. Remote tags after the push: only s4-acceptance (ef29124, peeled e954035). The checkpoint tag was not pushed.

4. MERGE
Method: git merge --no-ff fix/stale-load-keyless -m "Merge fix/stale-load-keyless into main — W1-NCEI wiring + catch-up code, W3 availability provenance, W2 same-day semantics"
Result: merge made by the ort strategy at 05:48:56, exit 0, no conflicts, no manual resolution.
Resulting main HEAD: df1d1c0778b21793feb7f3276ec6eaaee00319d8, parents 84a51af43c3b324462f0d793b0305f7976c3cfae and 40b75ab5aed76562db2e0af33bb7d06619f9d5d6.
Tree df1d1c0 = f23860ce9fa52c8bd64365d7411cf86e77b3d9cc, identical to the merge-tree preview.
git diff 84a51af..HEAD: 45 files changed, 1554 insertions, 41 deletions. No path under ledger/ changed.
Files of note: scripts/refresh_ncei.py and tests/test_refresh_ncei.py added; scripts/issue_stress.py, src/grid_pipeline/stress.py, stress_inputs.py, model.py changed (as on the branch).

5. PUSH
Command: git -c credential.helper= -c "credential.helper=!gh auth git-credential" push origin main (gh-authenticated admin route; the plain form was not tried, so no hang occurred).
Output, verbatim:
    remote: Bypassed rule violations for refs/heads/main:
    remote:
    remote: - Required status check "tests-and-ledger" is expected.
    remote:
    To https://github.com/Darren-dev141/grid-project
       84a51af..df1d1c0  main -> main
Exit 0. Not a force push. The required-check rule was bypassed through the admin lane (enforce_admins=false), as planned. Consequence: df1d1c0 was on main before its check had run; the check ran afterwards (section 6).
ls-remote after: refs/heads/main = df1d1c0778b21793feb7f3276ec6eaaee00319d8.

6. POST-MERGE VERIFICATION (on main, in the main checkout; interpreter .venv/Scripts/python.exe 3.14.7; PYTHONPATH=src)
Raw logs: C:/Users/ajbig/AppData/Local/hermes/cache/scratch/postmerge-out/ (timeline.txt, *.out, *.exit)
HEAD at start of verification: df1d1c0778b21793feb7f3276ec6eaaee00319d8.

6a. CI
Run id 42013840657, workflow CI, event push, head sha df1d1c0778b21793feb7f3276ec6eaaee00319d8, created 10:49:05Z, updated 10:53:00Z. Status completed, conclusion success.
https://github.com/Darren-dev141/grid-project/actions/runs/42013840657
Every step success: secret scan (exact index: candidates [], files 347), Full tests "308 passed in 203.04s (0:03:23)", ledger integrity (anchored_local, history_commits 3), witness (anchored_remote, history_commits 3).
Check run tests-and-ledger, app_id 15368, completed/success on df1d1c0.

6b. Prospective scan (same as HOST-STEPS: python scripts/s4_secret_scan.py --prospective), 05:49:55 to 05:49:57, exit 0:
{"bytes": 31502659, "candidates": [], "files": 348, "scope": "prospective working files", "unreadable": []}
Result: 0 candidates, 0 unreadable, as expected.

6c. Full suite (python -m pytest -ra --basetemp <scratch>/pytest-basetemp), detached with log, 05:51:47 to 06:01:07, exit 0:
======================= 308 passed in 559.07s (0:09:19) =======================
308 passed, 0 failed, 0 errors. Wall time 559.07 s by pytest (560 s by script clock). Working tree after the suite: git status --porcelain --untracked-files=all showed only the pre-existing untracked HOST-STEPS-V2 evidence file. The suite left nothing behind.

6d. verify --integrity-only (python -m grid_pipeline.ledger verify --integrity-only), 05:49:57 to 05:50:50, exit 0:
{"acceptance": "anchored_local", "first_seen_commits": {}, "historical_origins": 0, "historical_receipt_additions": 0, "historical_receipts": 0, "history_commits": 7, "pending_receipts": 0, "prospective_origins": 0, "prospective_receipts": 0, "public_visibility": "not_inferred", "receipt_status": {}, "receipts": 0, "timing": "unverified_integrity_only", "witnessed_origins": 0, "witnessed_receipts": 0}

6e. verify --witness (python -m grid_pipeline.ledger verify --witness), 05:50:50 to 05:51:47, exit 0:
{"acceptance": "anchored_remote", "first_seen_commits": {}, "historical_origins": 0, "historical_receipt_additions": 0, "historical_receipts": 0, "history_commits": 7, "pending_receipts": 0, "prospective_origins": 0, "prospective_receipts": 0, "public_visibility": "not_inferred", "receipt_status": {}, "receipts": 0, "timing": "witness_checked", "witnessed_origins": 0, "witnessed_receipts": 0}

Both strings are the expected ones: anchored_local from integrity-only, anchored_remote from witness. history_commits went from 6 to 7 locally (and 2 to 3 in CI's shallower view) against the previous baseline at 84a51af. I attribute the +1 to the new merge commit, but did not trace it in ledger.py, so treat that as inference.

7. FINAL LEDGER STATE
acceptance anchored_remote (witness mode) / anchored_local (integrity-only mode, by design). receipts 0, witnessed_receipts 0, pending_receipts 0, no boundary or tag mismatch. No receipt was written or faked. Unchanged from the 84a51af baseline apart from history_commits.

8. NCEI WIRING
Launcher: C:\Users\ajbig\AppData\Local\hermes\scripts\grid_s3c_repo_launcher.py (read, not run).
(a) Logic: REPO = C:\Users\ajbig\Documents\grid-project. refresh() sets script = repo / 'scripts' / 'refresh_ncei.py'; if not script.exists() it prints "NCEI refresh: skipped (... not present in repo)" and returns; otherwise it runs it with the repo .venv python, prints stdout/stderr, and on a non-zero exit prints a warning and continues. execute() calls refresh() first, then runs scripts/issue_stress.py. The launcher also refuses to run before 07:00 America/New_York.
(b) File presence: scripts/refresh_ncei.py now exists in the main checkout (4279 bytes), tracked, blob 7c946a66c90c08f704fef540176c02e24a12169d, byte-identical to the blob on fix/stale-load-keyless. tests/test_refresh_ncei.py is also tracked in main.
Not done: no issuance, no refresh_ncei.py run, no scheduled job triggered.

9. CLOSE-OUT STATE
9a. Worktrees, AFTER (same read-only method)
main checkout   main                          df1d1c0   1 line (?? HOST-STEPS-V2 evidence) + this file once written
t3-1a0cc244     t3/nws-weather-ingestion      2601085   clean            (same as before)
t3-378eaf5c     t3/eia-demand-models          1169c62   8 lines          (same as before)
t3-8a2dfe33     t3/eia-backfill-ingestion     1169c62   4 lines          (same as before)
t3-9668dd3e     t3/retire-v1-price-powerbi    34670e8   clean            (same as before)
staleload       fix/stale-load-keyless        40b75ab   clean            (same as before)
w3check         detached                      724126a   1 line           (same as before)
weather         fix/weather-fresh-nws         db07934c3d38ed9d52a7101b1b1c8c60c59c98eb at 06:02, a05c74058cce11e363e246bcc555c6276cb28cf5 at 06:04 (see late update in 9b)   0 lines, clean   *** CHANGED ***

9b. Weather worktree: NOT the same as Step 1, and I did not cause it.
Step 1: HEAD 954f3ba4b80f2bc79259a076c8cbda11b0d5a4e6, 10 dirty paths (section 2).
Close-out: HEAD db07934c3d38ed9d52a7101b1b1c8c60c59c98eb, clean.
Cause: the branch reflog shows "db07934 commit: Consolidate weather-fresh branch: collapse duplicate dbt models, add tests, records", author Themandme, 2026-11-05 05:53:33 -0500, which is 4m37s after my merge and during my verification run. The commit turns the dirty state I recorded into a commit and adds two more paths (docs/s4/WEATHER-FRESH-RUN-2026-11-05.md, src/grid_pipeline/stress_inputs.py), so the other actor kept editing after my Step 1 snapshot. 954f3ba..db07934: 12 files changed, 289 insertions, 167 deletions.
My contact with that worktree was read-only: git --no-optional-locks status --porcelain, git diff, rev-parse, branch --show-current, reflog and log. I ran no add, commit, checkout, reset, merge, rebase or test there.
A pytest process "python -m pytest -q" (pid 110896, started 05:53:53, using the main checkout's .venv python) appeared 20 seconds after that commit. It is not mine (mine was "-ra --basetemp" started 05:51:47 and finished 06:01:07). I left it alone and did not check its working directory.
Also unchanged and not mine: idle git-remote-https processes (pids 115304, 109700) from the hung push at about 01:06.
I cannot honestly say the weather worktree is "in the same state as Step 1". It is in the state another actor left it in.
Late update (06:04:49): the weather branch moved once more while I was writing this file. Reflog: a05c74058cce11e363e246bcc555c6276cb28cf5 at 06:04:24 "Record full-suite result (321 passed) in consolidation addendum". Worktree still clean (0 porcelain lines). So the weather branch tip at the end of my run is a05c740, not db07934 or 954f3ba. Again not my doing; my only reads there were the status/rev-parse/reflog calls above. The 321 passed figure is that actor's claim, which I did not verify.

9c. Final main HEAD
local  df1d1c0778b21793feb7f3276ec6eaaee00319d8
remote (git ls-remote origin refs/heads/main) df1d1c0778b21793feb7f3276ec6eaaee00319d8
git status -sb: ## main...origin/main (in sync). Tags: pre-staleload-merge (local), s4-acceptance, v1-final. Branches fix/stale-load-keyless and fix/weather-fresh-nws still present.

10. CAVEATS
1. EIA key still absent. Nothing EIA-related was touched or requested.
2. Weather branch fix/weather-fresh-nws not integrated. It also moved during this run (db07934, section 9b), so any verification of it from before 05:53 no longer matches its tip. It needs its own check before any merge.
3. Strict 07:00:00 cutoff is merged as-is and still awaits Darren's ruling.
4. Step-6 ledger append_forecast gap is still open: receipts 0, nothing in src/ or scripts/ calls ledger.append_forecast.
5. Timing: the merge went live at about 05:49 ET. The launcher now finds scripts/refresh_ncei.py in the main checkout, so the next 07:00 ET run (cron job d977b52c965c, if still enabled; I did not check it) will be the first to run the live NCEI refresh and the merged issue_stress.py. I did not trigger or inspect it.
6. df1d1c0 reached main through the admin bypass of the required check; CI passed afterwards (run 42013840657). Normal for enforce_admins=false, but main was briefly unchecked.
7. history_commits rose 6 to 7 locally; the cause is inferred, not traced.
8. Unrelated pre-existing items seen, not touched: prunable worktree entry for scratch/verify/grid-project2, dirty t3 worktrees (eia-demand-models, eia-backfill-ingestion), refs/t3 checkpoint refs (H3 hazard from the HOST-STEPS-RUN-2026-11-04 record; verify passed with them present), lingering idle git processes from the 01:06 hung push.
