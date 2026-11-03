# Host rerun before any S4 Git write

Use a fresh external evidence directory. Do not modify implementation, restore
old files, retry failures into a pass, or use the pre-fix 228-pass result.

```powershell
Set-Location -LiteralPath C:/Users/ajbig/Documents/grid-project
$s4Python = (Resolve-Path .venv/Scripts/python.exe).Path
$s4ResumeEvidence = Join-Path $env:TEMP ('grid-s4-resume-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $s4ResumeEvidence -ErrorAction Stop | Out-Null
& $s4Python -m pytest -ra --basetemp (Join-Path $s4ResumeEvidence 'pytest')
if ($LASTEXITCODE -ne 0) { throw 'STOP: full host suite failed' }
& $s4Python scripts/s4_secret_scan.py --prospective
if ($LASTEXITCODE -ne 0) { throw 'STOP: prospective scan unresolved' }
& $s4Python -m grid_pipeline.ledger verify --integrity-only
if ($LASTEXITCODE -ne 0) { throw 'STOP: integrity failed' }
& $s4Python -m grid_pipeline.ledger verify --witness
if ($LASTEXITCODE -ne 0) { throw 'STOP: witness/bootstrap failed; investigate remote anchor/policy state' }
```

The last command now genuinely checks remote absence before allowing initial
bootstrap. If a remote anchor exists but the policy is missing, refusal is
required. Do not suppress that check or treat a failed lookup as absence.

Verify all entries in `implementation-hashes.json` before and after the suite.
Return observed counts, warnings, timing, exit codes, and the exact source
snapshot identity. Do not print credentials, complete environments, or potential
secret matches. Store host logs outside the repository.

Resume independent read-only worker **01a19539-2804-7ff3-bc5f-9e2109727053** with
`gpt-6.1-terra`, `model_reasoning_effort=xhigh`. Verify actual `turn_context` again.
Have it inspect the final source hashes and regressions for:

1. `./ledger` and aliases from env/config, with child cwd and no package import;
2. remote-anchor-present/policy-absent refusal and genuine initial absence;
3. incomparable first-seen origins, per-origin witness coverage, all-ref clocks;
4. ID-only Git content reads in ledger and default index scanner;
5. preservation and non-qualification of the Nov 1 diagnostic;
6. mandatory integrity checks, CI witness split, and unchanged baseline behavior.

It must not edit code, access secrets, commit, push, or start S5. Return the fresh
verdict and actual model/effort evidence. Any actionable NOT READY finding goes
back to the lead before Git writes.

Only once both pass, use the existing `../alder-round/HOST-STEPS.md` for the
authorized feature-branch C/tag/B bootstrap and protection setup, with these
corrections:

- Use this round's `intended-commit-files.txt`, not the older manifest.
- Scan the exact intended index immediately before each commit. The current
  index scan covers only the old index and is not permission to skip that gate.
- Reverify live refs, exact repository identity, public visibility, and existing
  settings immediately before each push. Preserve any existing protections.
- After tag creation, a tag-push run of C with no policy may correctly fail
  closed. Record that expected denial separately. The original successful C
  branch run remains the bootstrap run; B must then pass its own complete CI.
- Do not claim tag protection or main protection until actual API read-backs.
- The late same-day Nov 1 diagnostic is not D. Do not append it to the real ledger,
  backdate it, or label it witnessed. The genuine receipt gate is still waiting.

No S5 work, new account, paid service, EIA key action, main merge, or force-push.
