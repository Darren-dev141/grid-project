# Ordered host steps for S4

These commands are for the supervisor's host, not a sandbox escalation. Run only
inside `C:/Users/ajbig/Documents/grid-project`. Stop on unexpected refs, identity,
files, permissions, scan findings, tests, or review failures. No reset, stash,
discard, amend, force-push, main merge, account creation, or EIA secret action.
Do not run the whole document blindly; observe each prerequisite before its write.

## 1. Verify source and obtain fresh approval

```powershell
Set-Location -LiteralPath C:/Users/ajbig/Documents/grid-project
$s4HostEvidence = Join-Path $env:TEMP ('grid-s4-host-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $s4HostEvidence -ErrorAction Stop | Out-Null
$s4Python = (Resolve-Path .venv/Scripts/python.exe).Path
$env:PATH = (Split-Path $s4Python) + [IO.Path]::PathSeparator + $env:PATH
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
& $s4Python -c 'import subprocess; r=subprocess.run(["git","remote","get-url","origin"],capture_output=True,text=True); assert r.returncode==0 and r.stdout.strip()=="https://github.com/Darren-dev141/grid-project", "STOP: unexpected origin; value withheld"; print("Origin identity verified")'
gh api repos/Darren-dev141/grid-project --jq '{full_name,visibility,default_branch,permissions}'
git ls-remote --heads origin main feat/energy-ingestion
git status --short
```

The expected branch is `feat/energy-ingestion`; origin must be the exact project
URL without embedded credentials. If its URL has unexpected credentials, do not
print it: inspect identity through a value-withholding comparison instead.
Expected observations before any new host changes were local HEAD
`e01a80d1f74f4cf4ec2b45045bc82f95ff6a2087`, live feature
`60194df7f30cdbf5a6772774fa4e0bdb11b25403`, and live main
`863d4fca31a0139e0384ef672232fd8b705d869e`. These are comparison inputs, not
permission to overwrite a changed remote. Reverify immediately before each push.

```powershell
& $s4Python scripts/s4_secret_scan.py --prospective
if ($LASTEXITCODE -ne 0) { throw 'STOP: prospective scan unresolved' }
& $s4Python -m pytest -ra --basetemp (Join-Path $s4HostEvidence 'pytest')
if ($LASTEXITCODE -ne 0) { throw 'STOP: full host suite failed' }
& $s4Python -m grid_pipeline.ledger verify --integrity-only
if ($LASTEXITCODE -ne 0) { throw 'STOP: integrity failed' }
& $s4Python -m grid_pipeline.ledger verify --witness
if ($LASTEXITCODE -ne 0) { throw 'STOP: bootstrap/witness check failed' }
```

Record counts, warnings, elapsed time, source hashes, and exit codes. The final
command should report `bootstrap_no_receipts`, not an accepted S4 gate. Keep host
logs outside the repository so the exact-snapshot hook does not see new artifacts.
No credential values, `gh auth token`, complete environment dumps, or secret
store files belong in logs. A scan finding prints metadata only and requires
classification without printing the matching value.

The supervisor launches a **fresh** read-only worker, using its functioning
standalone Codex CLI. Its task is limited to these S4 modules, tests, workflow,
hook, and bootstrap protocol. It must not edit, access secret stores, commit,
push, create accounts, or start S5. Example invocation shape:

```powershell
codex exec --model gpt-6.1-terra -c 'model_reasoning_effort="xhigh"' --sandbox read-only --json 'Read-only independent S4 final check. Inspect ledger integrity/full DAG, acceptance boundary, subprocess env/config path denial and stdin-content route, local selection, hook integrity versus additional CI witness checks, source hashes and tests. No edits, secrets, commits, pushes, accounts, or S5. Distinguish ready-for-receipt-free-bootstrap from S4 complete; real receipt gate is waiting. Report concrete findings and evidence.'
```

Capture the fresh session ID and events in the host's protected scratch location.
Find only that UUID's `rollout-*.jsonl` under `~/.codex/sessions`. Parse its actual
`turn_context` records and report only `model` and `effort`; they must be
`gpt-6.1-terra` and `xhigh`. Do not substitute the old session or the CLI banner.
Return the independent verdict and full host results to the lead. Do not proceed
to C until source and bootstrap mechanics have independent approval; a waiting
real-receipt gate is still explicitly reported.

## 2. Commit reviewed receipt-free code as C on the feature branch

The explicit intended scope is `intended-commit-files.txt`: the preserved
tracked source plus nonignored project working files, including previously
pending S3 source/tests/dbt/docs and the S4 implementation/evidence. No `.venv`,
local database, raw `data/`, cache, `.idea`, or external file is included. Review
that manifest against the starting tree; stop on unexpected files. Do not discard
or hide pre-existing work to make the hook pass.

```powershell
git config --local core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) { throw 'STOP: hook installation failed' }
Get-Content -LiteralPath docs/s4/alder-round/intended-commit-files.txt | ForEach-Object {
    git add -- $_
    if ($LASTEXITCODE -ne 0) { throw 'STOP: staging failed' }
}
git update-index --chmod=+x -- .githooks/pre-commit
if ($LASTEXITCODE -ne 0) { throw 'STOP: hook mode failed' }
git diff --cached --stat
& $s4Python -c 'from pathlib import Path; from grid_pipeline.precommit import check_snapshot; print(check_snapshot(Path.cwd()))'
if ($LASTEXITCODE -ne 0) { throw 'STOP: staged/working snapshot differs' }
& $s4Python scripts/s4_secret_scan.py
if ($LASTEXITCODE -ne 0) { throw 'STOP: exact-index scan unresolved' }
git commit -m 'Add S4 append-only ledger, access guards, CI and witness bootstrap'
if ($LASTEXITCODE -ne 0) { throw 'STOP: hook or commit failed' }
$s4CodeCommit = (git rev-parse HEAD).Trim()
```

The hook repeats the index scan, full suite, and integrity checks. It rejects
unstaged/untracked source and an index changed during tests. Do not bypass it.
Record C's actual hash; do not guess it or backdate the commit. No acceptance
policy or fabricated receipt is part of C. If fixing a failure requires another
commit, rescan and validate that commit too; do not amend old work.

Immediately before push:

```powershell
gh api repos/Darren-dev141/grid-project --jq '{full_name,visibility,permissions}'
git ls-remote --heads origin main feat/energy-ingestion
git fetch origin feat/energy-ingestion main --tags
if ($LASTEXITCODE -ne 0) { throw 'STOP: fetch/ref mismatch' }
git merge-base --is-ancestor origin/feat/energy-ingestion HEAD
if ($LASTEXITCODE -ne 0) { throw 'STOP: remote feature is not an ancestor' }
git push origin HEAD:refs/heads/feat/energy-ingestion
if ($LASTEXITCODE -ne 0) { throw 'STOP: push failed' }
gh api "repos/Darren-dev141/grid-project/actions/runs?head_sha=$s4CodeCommit&event=push&per_page=100" --jq '.workflow_runs[] | {id,head_sha,path,status,conclusion,event}'
```

Observe the actual `CI` run for C, not a different head or old run. Set its ID
only after observing the response. `gh run watch` must exit successfully:

```powershell
$s4BootstrapRun = <OBSERVED_CI_PUSH_RUN_ID_FOR_C>
gh run watch $s4BootstrapRun -R Darren-dev141/grid-project --exit-status
if ($LASTEXITCODE -ne 0) { throw 'STOP: C CI failed' }
gh run view $s4BootstrapRun -R Darren-dev141/grid-project --json databaseId,headSha,event,status,conclusion,jobs
```

Record actual CI test counts by extracting only the pytest summary from logs;
do not dump unreviewed raw logs or tokens. A receipt-free green run is bootstrap
evidence, not evidence of a genuine witnessed forecast.

## 3. Create and protect the annotated acceptance tag

Read existing rulesets first. If a matching tag rule or existing tag already
exists, stop and reconcile its target/object with the reviewed C; never move or
delete it. The supplied rule prohibits updates and deletions but allows the
initial creation. Preserve all unrelated rulesets. API details follow
[GitHub's ruleset documentation](https://docs.github.com/en/rest/repos/rules).

```powershell
gh api repos/Darren-dev141/grid-project/rulesets --jq '.[] | {id,name,target,enforcement}'
git ls-remote --tags origin refs/tags/s4-acceptance 'refs/tags/s4-acceptance^{}'
gh api -X POST repos/Darren-dev141/grid-project/rulesets --input docs/s4/alder-round/tag-ruleset.json
if ($LASTEXITCODE -ne 0) { throw 'STOP: immutable-tag rule creation failed' }
# Record the returned ID, then read it back and verify active/tag/ref/update/deletion/no-bypass.
$s4TagRuleId = <RETURNED_RULESET_ID>
gh api "repos/Darren-dev141/grid-project/rulesets/$s4TagRuleId"
git -c tag.gpgSign=false tag -a s4-acceptance $s4CodeCommit -m 'S4 reviewed source boundary; real receipt witness gate remains separate'
if ($LASTEXITCODE -ne 0) { throw 'STOP: acceptance tag creation failed' }
$s4TagObject = (git rev-parse refs/tags/s4-acceptance).Trim()
gh api repos/Darren-dev141/grid-project --jq '{full_name,visibility,permissions}'
git ls-remote --heads origin main feat/energy-ingestion
git push origin refs/tags/s4-acceptance:refs/tags/s4-acceptance
if ($LASTEXITCODE -ne 0) { throw 'STOP: acceptance tag push failed' }
gh api repos/Darren-dev141/grid-project/git/ref/tags/s4-acceptance
gh api "repos/Darren-dev141/grid-project/git/tags/$s4TagObject"
```

This is an unsigned annotated object protected by reference policy, not a signed
attestation or historical visibility proof. Keep C, its tree hash, tag object,
CI run ID, and rule read-back together in host evidence. If the free public repo
cannot enforce the rule, report that blocker; do not buy a plan or create accounts.

## 4. Append the acceptance record in later commit B

Only the ledger CLI writes this new data file. Do not create/edit the JSON by hand.
No implementation source changes are made by the host.

```powershell
& $s4Python -m grid_pipeline.ledger establish-boundary --acceptance-commit $s4CodeCommit --tag-object $s4TagObject --bootstrap-run-id $s4BootstrapRun
if ($LASTEXITCODE -ne 0) { throw 'STOP: boundary creation failed' }
git add -- ledger/policy/s4-acceptance.json
if ($LASTEXITCODE -ne 0) { throw 'STOP: boundary staging failed' }
git diff --cached --name-only
& $s4Python -m grid_pipeline.ledger verify --integrity-only
if ($LASTEXITCODE -ne 0) { throw 'STOP: pending boundary integrity failed' }
& $s4Python scripts/s4_secret_scan.py
if ($LASTEXITCODE -ne 0) { throw 'STOP: B exact-index scan unresolved' }
git commit -m 'Anchor S4 source boundary to immutable tag and successful bootstrap run'
if ($LASTEXITCODE -ne 0) { throw 'STOP: B hook or commit failed' }
$s4BoundaryCommit = (git rev-parse HEAD).Trim()
```

The only newly staged data should be the new policy record. Verify no unrelated
changes appeared; preserve them and stop rather than discarding them. Recheck
live refs/identity/visibility and fast-forward ancestry exactly as before C's push,
then push `HEAD:refs/heads/feat/energy-ingestion`. Observe B's actual CI pass and
counts. CI should report `anchored_remote` and zero witnessed receipts; S4's real
receipt gate still waits. Never back-edit this policy record.

## 5. Require the observed CI check on main and read protection back

Inspect [existing main protection](https://docs.github.com/en/rest/branches/branch-protection).
If protected already, preserve all settings and add the observed CI requirement
without weakening anything. If still unprotected, the minimum new body below is
authorized. Bind the check to the observed GitHub Actions app ID rather than
guessing it. The check name must be the actual `tests-and-ledger` job that ran
full tests, integrity, and witness steps. Do not use a skipped or unrelated check.

```powershell
gh api repos/Darren-dev141/grid-project/branches/main --jq '{name,protected,protection}'
gh api repos/Darren-dev141/grid-project/branches/main/protection
gh api "repos/Darren-dev141/grid-project/commits/$s4BoundaryCommit/check-runs" --jq '.check_runs[] | {name,status,conclusion,app_id:.app.id,details_url}'
$s4ObservedActionsAppId = <OBSERVED_APP_ID_FOR_SUCCESSFUL_TESTS_AND_LEDGER>
$s4Protection = @{
    required_status_checks = @{strict = $true; checks = @(@{context = 'tests-and-ledger'; app_id = $s4ObservedActionsAppId})}
    enforce_admins = $true
    required_pull_request_reviews = $null
    restrictions = $null
    allow_force_pushes = $false
    allow_deletions = $false
}
$s4ProtectionFile = Join-Path $s4HostEvidence 'new-main-protection.json'
[IO.File]::WriteAllText($s4ProtectionFile, ($s4Protection | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
# PUT ONLY if live read confirmed unprotected; otherwise preserve/merge existing settings.
gh api -X PUT repos/Darren-dev141/grid-project/branches/main/protection --input $s4ProtectionFile
if ($LASTEXITCODE -ne 0) { throw 'STOP: main protection update failed' }
gh api repos/Darren-dev141/grid-project/branches/main/protection
git config --get core.hooksPath
```

Record required check context/app, strict mode, enforcement, force-push/deletion
denial, and hook path. No main merge is part of this round.

## 6. Genuine receipt gate, then S4 verdict

Wait for the authorized real issuance, no earlier than Nov 1 07:00 EST. The
supervisor must identify a genuine qualified pipeline call, future target day,
actual pinned input availability, and unmodified issue time. The same-day S3
diagnostic is not that call. Do not fabricate features, advance the clock,
backdate a commit, or produce a fixture in the real ledger. If no such call is
available, report this gate waiting and do not begin S5.

The qualified call must use `ledger.append_forecast` exclusive-create. Its real
receipt is staged, passes the local hook and exact intended-index scan immediately
before commit **D**, and is pushed normally before the target's local midnight.
Reverify live refs, identity, and public visibility before that push too. Observe
D's actual Actions witness result with `witnessed_receipts >= 1`, its actual run
ID and counts, and confirm the source hash/path matches the genuine receipt.
Do not count a synthetic fixture or historical receipt as this integration test.

Only after the fresh independent review, host suite, C/B/D evidence, installed
hook, main protection and immutable-tag read-backs, exact-index scans, and the
genuine receipt witness all pass can the supervisor declare S4 complete. Until
then, no S5 deployment, schedule, credentials, accounts, or retirement work.
