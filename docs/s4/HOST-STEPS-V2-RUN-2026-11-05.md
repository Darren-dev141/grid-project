# Grid S4 HOST-STEPS v2 run, 2026-11-05 (steps A, B-adopt, 3, 4, 5, final trio)

Run window: 2026-11-05T01:02-05:00 to 01:51-05:00 (America/New_York). Operator: Hermes agent on the host PC.
Authorization: Darren approved HOST-STEPS v2 verbatim on Nov 5, 2026 (~01:00 ET), including the three flagged deviations (housekeeping commits outside C; B landed on main; step 5 with enforce_admins=false) and adoption of e954035 as snapshot C. Claude checker READY is the independent approval; Codex gates nothing.
Host logs (outside the repo): `C:/Users/ajbig/AppData/Local/Temp/grid-s4-v2-host/` (step34.log, final.log, push_A2.log, ruleset_*.json, status_pre.txt, bucketA.txt, new-main-protection.json).
No ledger receipt was written or faked. No EIA key was read, requested, or needed.

## Result summary

| Step | Result | One line |
|---|---|---|
| A housekeeping | PASS | 121 untracked = A(117)+B(4) exactly. Evidence commit 0244323 pushed to main, CI green (run 41979067494, 249 passed). |
| B adopt C | PASS | C = e954035 adopted, no new commit. 13/13 Appendix A hashes match. |
| 3 tag + ruleset | PASS | Ruleset 26592294 active, read-back matches repo file. Tag s4-acceptance (object ef29124) -> e954035, pushed. |
| 4 boundary B | PASS | B = 84a51af43c3b324462f0d793b0305f7976c3cfae on main, hook ran (249 passed), hooksPath unset after, CI run 41980869574 green, `anchored_remote`. |
| 5 protection | PASS | First PUT attempt was held by the approval gate and timed out (never ran). Applied at 01:52:50 after Darren's explicit "continue" instruction. Read-back: strict true, check tests-and-ledger app 15368, enforce_admins false, force-push denied, deletion denied. |
| Final trio | PASS | Scan 0 candidates; 249 passed (01:40, HEAD 84a51af); integrity exit 0 `anchored_local`; witness exit 0 `anchored_remote`. Scan + integrity + witness re-run after step 5 (01:53), same results. |

## A. Housekeeping

Preconditions (01:02): HEAD f0adcbaf1b1c92559900f6c89afc53a88ee2fbc7 on main, origin/main same, nothing staged or modified, hooksPath unset, no s4 tag, 0 rulesets, ledger/policy absent. `git status --porcelain --untracked-files=all` = 121 lines, all `??`.

Bucket check (python, exact set comparison): A1 100 (99 under docs/s3c/evidence-2026-10-31-sol/ + probe-after-rulings.json), A2 15, A3 1, A4 1, B 4 = 121. Untracked not in buckets: none. Bucket entries not untracked: none.

.gitignore diff (CRLF file, LF in index):

    @@ -31,3 +31,7 @@ pytest-temp/
     .venv-*/
     *.parquet
    +suite_out.txt
    +synthetic-twin/feed_load.json
    +synthetic-twin/feed_temperature.json
    +synthetic-twin/interchange_series.csv

Staged 118 paths (117 A + .gitignore). Exact-index scan before commit: `{"bytes": 30479671, "candidates": [], "files": 310, "scope": "exact index blobs", "unreadable": []}`, exit 0. Hook not installed (hooksPath unset), as planned for housekeeping.

Commit: `02443231eb85e11de67262e730bfa097d3864890` "HOST-STEPS v2 housekeeping: project-record evidence outside the S4 acceptance boundary", 118 files changed. Post-commit `git status --porcelain --untracked-files=all` = 0 lines.

Push deviation: the first `git push` hung because the host's bundled git (system gitconfig `credential.helper = helper-selector`) launched `git-credential-helper-selector`, a GUI chooser with no one to answer it. The push never reached GitHub (remote main stayed f0adcba). An attempt to kill the hung processes was held for manual approval and timed out, so it was not run; I did not retry it. Two idle processes from that attempt may still exist (git-remote-https 109700, git-credential-helper-selector 90328, started 01:06:42). The push was redone with `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin HEAD:refs/heads/main` (uses the existing gh login, no token printed): `f0adcba..0244323  HEAD -> main`, exit 0. All later pushes used the same override.

CI for 0244323: run 41979067494, event push, path .github/workflows/ci.yml, completed/success. Full tests `249 passed in 228.90s`; integrity and witness `bootstrap_no_receipts`.

## B. Adopt C = e954035

No commit made. C = `e954035a50692600053f977fa97733354a1e0f3e` (on main, ancestor of origin/main, pushed). Bootstrap CI: run 41645076408, head_sha C, event push, conclusion success, path .github/workflows/ci.yml, 249 tests, `bootstrap_no_receipts`.

Hash spot-check of the 13 checker Appendix A sha256 values (docs/s4/CHECKER-CLAUDE-2026-11-03.md lines 197-209) against `git show e954035:<path>`: 13 / 13 match. 11 match the git blob byte-for-byte. `src/grid_pipeline/ledger.py` and `tests/conftest.py` match after CRLF normalisation (the checker hashed the CRLF working copies; the blobs in e954035 are LF), same as the Nov 4 recon found.

## 3. Tag ruleset and tag

Preconditions re-verified immediately before (01:20): HEAD 0244323 clean, remote main = HEAD, no local or remote tag, 0 rulesets, C ancestor of HEAD, run 41645076408 as above.

    01:20:33  gh api -X POST repos/Darren-dev141/grid-project/rulesets --input docs/s4/alder-round/tag-ruleset.json   -> ruleset id 26592294
    read-back (GET rulesets/26592294) compared to the repo file by script:
    RULESET READBACK MATCHES REPO FILE: {"id": 26592294, "name": "s4-acceptance-immutable", "target": "tag", "enforcement": "active", "bypass_actors": [], "conditions": {"ref_name": {"exclude": [], "include": ["refs/tags/s4-acceptance"]}}} ['update', 'deletion']
    current_user_can_bypass: never
    01:20:34  git -c tag.gpgSign=false tag -a s4-acceptance e954035a50692600053f977fa97733354a1e0f3e -m 'S4 reviewed source boundary; real receipt witness gate remains separate'   exit 0
    tag object  ef291241a6ec41e16e59930510e5a219f0a941d0   peels to  e954035a50692600053f977fa97733354a1e0f3e
    01:20:35  git push origin refs/tags/s4-acceptance:refs/tags/s4-acceptance   -> [new tag] s4-acceptance -> s4-acceptance, exit 0
    git ls-remote --tags origin 's4-acceptance*':
      ef291241a6ec41e16e59930510e5a219f0a941d0  refs/tags/s4-acceptance
      e954035a50692600053f977fa97733354a1e0f3e  refs/tags/s4-acceptance^{}
    gh api git/ref/tags/s4-acceptance -> object.sha ef291241..., type tag

H2 outcome (expected): the tag push started CI run 41979768410 (head e954035, ref s4-acceptance, push) which ended `failure`. Failing step: "Prospective ledger witness verification", `ledger verify failed: remote acceptance anchor exists but boundary policy is absent`, after the full suite had run. Treated as expected per H2. Red window: tag push 01:20:37 to B push 01:30:26 (about 10 minutes).

## 4. Boundary record B

    01:20:38  python -m grid_pipeline.ledger establish-boundary --acceptance-commit e954035a50692600053f977fa97733354a1e0f3e --tag-object ef291241a6ec41e16e59930510e5a219f0a941d0 --bootstrap-run-id 41645076408
              {"boundary_record": "C:\\Users\\ajbig\\Documents\\grid-project\\ledger\\policy\\s4-acceptance.json", "remote_acceptance": "pending_verification"}   exit 0
    status after: only `?? ledger/policy/s4-acceptance.json`
    git add -- ledger/policy/   staged: ledger/policy/s4-acceptance.json (only file)
    verify --integrity-only (record staged): "acceptance": "pending_boundary_commit", "history_commits": 5, "receipts": 0   exit 0
    s4_secret_scan.py (exact index): candidates [], files 311   exit 0
    refs/t3 fingerprint unchanged between establish-boundary and commit (54 refs, 15906af508b0): H3 hazard did not occur
    01:21:24  git config --local core.hooksPath .githooks
    git commit (hook ran: exact-index scan, then `249 passed in 440.61s (0:07:20)`, then integrity)   exit 0
    [main 84a51af] Anchor S4 source boundary to immutable tag and successful bootstrap run
     1 file changed, 1 insertion(+)  create mode 100644 ledger/policy/s4-acceptance.json
    01:29:39  git config --local --unset core.hooksPath -> hooksPath now unset (re-confirmed empty at 01:34 and 01:40)

B = `84a51af43c3b324462f0d793b0305f7976c3cfae`, parent 0244323 (as required). B contains only ledger/policy/s4-acceptance.json.

Local verify after commit (01:30): `"acceptance": "anchored_local", "history_commits": 6, "receipts": 0, "timing": "unverified_integrity_only"`, exit 0.

Push (01:30:25): remote main re-checked = 0244323 (fast-forward), then `0244323..84a51af  HEAD -> main`, exit 0.

CI for B: run 41980869574, event push, completed/success at 01:34:03. Check run `tests-and-ledger`, app_id 15368, success. Log excerpts:

    Full tests: 249 passed in 171.75s (0:02:51)
    Ledger integrity verification: "acceptance": "anchored_local", "history_commits": 2, "receipts": 0, "timing": "unverified_integrity_only"
    Prospective ledger witness verification: "acceptance": "anchored_remote", "history_commits": 2, "receipts": 0, "timing": "witness_checked", "witnessed_receipts": 0

## 5. Branch protection (APPLIED 01:52:50, after a first attempt was blocked)

Outcome first. Applied and read back; details of the blocked first attempt follow, then the applied run (section 5b).

Preconditions (01:35): `gh api .../branches/main` -> `protected: false`; `.../branches/main/protection` -> 404 "Branch not protected"; B's check run `tests-and-ledger` app_id 15368 success. Prepared body (`new-main-protection.json` in the host dir):

    {"required_status_checks": {"strict": true, "checks": [{"context": "tests-and-ledger", "app_id": 15368}]},
     "enforce_admins": false, "required_pull_request_reviews": null, "restrictions": null,
     "allow_force_pushes": false, "allow_deletions": false}

The command carrying `gh api -X PUT repos/Darren-dev141/grid-project/branches/main/protection --input <that file>` was held by the host's approval gate. No answer came within 5 minutes and the tool returned: "BLOCKED: Command timed out without user response ... Do NOT retry this command, do NOT rephrase it, and do NOT attempt the same outcome via a different command." The command did not execute. I did not retry or route around it.

State read back afterwards (read-only): `{"name":"main","protected":false,...}`, protection endpoint 404. The ruleset on the tag is in place; main is unprotected. Nothing about step 5 is half-applied.

### 5b. Applied after the coordinator's explicit "continue" instruction (01:52)

The coordinator replied with an explicit instruction to apply step 5 with enforce_admins=false. That superseded the timed-out approval, so the same prepared body was sent once:

    01:52:49  preconditions: branches/main -> {"name":"main","protected":false}
              commits/84a51af.../check-runs -> {"app_id":15368,"conclusion":"success","name":"tests-and-ledger","status":"completed"}
    01:52:50  gh api -X PUT repos/Darren-dev141/grid-project/branches/main/protection --input new-main-protection.json   exit 0
    read-back  gh api repos/Darren-dev141/grid-project/branches/main/protection   exit 0
      required_status_checks.strict            true
      required_status_checks.checks            [{"context":"tests-and-ledger","app_id":15368}]   (contexts: ["tests-and-ledger"])
      enforce_admins.enabled                   false
      allow_force_pushes.enabled               false
      allow_deletions.enabled                  false
      required_pull_request_reviews            null
      restrictions                             null
      required_linear_history / block_creations / lock_branch   false / false / false
    scripted comparison with the intended body: READBACK MATCHES INTENDED SETTINGS
    gh api .../branches/main -> {"name":"main","protected":true}
    gh api .../rulesets/26592294 -> {"current_user_can_bypass":"never","enforcement":"active","id":26592294,"name":"s4-acceptance-immutable"}

No test or junk commit was pushed to probe the rule.

Note on the daily lane: with enforce_admins=false and the required check strict, Darren's gh-authenticated admin push should bypass the check. Cadence-receipt commits made by a non-admin or token-limited path would be rejected. This is confirmed only by the next genuine daily push; it was not simulated.

(Section 5 as first written, before the instruction, follows.)

When protection is on (enforce_admins=false), Darren's daily-commit lane is expected to keep working because his gh-authenticated admin push bypasses the required check. That is confirmed by the next genuine daily push, not by a test commit. Not simulated.

## Final verification trio (01:40-01:50, HEAD 84a51af, hooksPath unset)

    01:40:12  s4_secret_scan.py --prospective   {"bytes": 31380076, "candidates": [], "files": 311, "scope": "prospective working files", "unreadable": []}   exit 0
    01:40:14  python -m pytest -ra --basetemp <host dir>/pytest   249 passed in 493.34s (0:08:13)   exit 0
    01:48:28  verify --integrity-only   "acceptance": "anchored_local", "history_commits": 6, "receipts": 0, "timing": "unverified_integrity_only", "witnessed_receipts": 0   exit 0
    01:49:15  verify --witness          "acceptance": "anchored_remote", "history_commits": 6, "receipts": 0, "timing": "witness_checked", "witnessed_receipts": 0   exit 0

Final ledger state string: `anchored_remote` (witness mode; integrity-only mode prints `anchored_local` by design). Working tree clean before this file was added.

Re-run after step 5 (01:53, HEAD 84a51af, hooksPath unset, evidence file present as the only untracked path):

    01:53:08  s4_secret_scan.py --prospective   {"bytes": 31391929, "candidates": [], "files": 312, ...}   exit 0
    01:53:09  verify --integrity-only   "acceptance": "anchored_local", "history_commits": 6, "receipts": 0   exit 0
    01:53:52  verify --witness          "acceptance": "anchored_remote", "history_commits": 6, "receipts": 0, "witnessed_receipts": 0   exit 0

The full pytest suite was not repeated after step 5: step 5 is a GitHub-side setting, the local tree did not change, and the suite passed (249) at 01:40 on the same HEAD and in CI run 41980869574.

## Final state

main = origin/main = 84a51af43c3b324462f0d793b0305f7976c3cfae. Tag s4-acceptance -> object ef291241a6ec41e16e59930510e5a219f0a941d0 -> e954035. Ruleset 26592294 active. Main protected (strict, tests-and-ledger app 15368, enforce_admins false, no force-push, no deletion). core.hooksPath unset. 54 refs/t3 untouched. Step 6 not touched.

This evidence file is untracked and not committed. Protection is now on, and a direct push to main would rely on the admin bypass (enforce_admins=false) because the new commit would not yet have a passing required check. I did not use the bypass for a record file. Commit it as the next genuine push, or whenever Darren prefers. It is an untracked non-ignored file, so a hook-enabled commit would reject until it is committed or moved.

## Addendum: second operator session (written 01:5x, by the session that ran the trio and the second PUT)

Two Hermes sessions were active on this task. The session that wrote the sections above sent the first successful protection PUT at 01:52:50 (host file protection_put_response.json, 01:52:51). This session (which ran steps A, 3, 4 and the 01:40 trio) did not know that, and sent a second PUT with the identical body at 01:55:44 after the coordinator's "continue" message. Exit 0 both times, identical settings, so the second was a no-op. Its read-back (01:55:49) matches section 5b: strict true, checks [tests-and-ledger / app 15368], enforce_admins false, allow_force_pushes false, allow_deletions false, pull-request reviews null, restrictions null. branches/main reports protected:true.

Cross-check of the sections above against this session's own logs (step34.log, final.log, push_A2.log): sections A, B, 3, 4 and the 01:40-01:50 trio match line for line (hashes, run ids, exit codes, test counts). Not independently verified by this session: the "re-run after step 5 (01:53)" scan/integrity/witness lines and the "hooksPath re-confirmed 01:34 and 01:40" remark. This session confirmed hooksPath unset at 01:35 and again after the PUT. The two idle processes from the hung first push (git-remote-https 109700, git-credential-helper-selector 90328) were still present at 01:41.
