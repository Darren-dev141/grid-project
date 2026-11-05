param(
    [string]$EvidenceDirectory = 'docs/s3c/evidence-2026-10-31-sol/external-run'
)

# Run outside the restricted Codex sandbox using the existing project venv.
# No source data is written. A new evidence directory preserves previous runs.
$repoPath = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repoPath
$outputPath = [System.IO.Path]::GetFullPath((Join-Path $repoPath $EvidenceDirectory))
if (-not $outputPath.StartsWith($repoPath + [System.IO.Path]::DirectorySeparatorChar,
                                [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Evidence directory must be inside the repository.'
}
New-Item -ItemType Directory -Path $outputPath -ErrorAction Stop | Out-Null
$pythonPath = Join-Path $repoPath '.venv/Scripts/python.exe'
$martPath = 'C:/Users/ajbig/AppData/Local/Temp/grid-s3c-20261030/history-complete/grid.duckdb'
$commands = @(
    "& '$pythonPath' -m pytest -ra tests/test_stress_inputs.py tests/test_s3c_diagnosis.py --basetemp '$outputPath/targeted-temp'",
    "& '$pythonPath' -m pytest -ra --basetemp '$outputPath/pytest-temp'",
    "& '$pythonPath' scripts/diagnose_s3c.py '$martPath' --output '$outputPath/probe.json'"
)
$commands | Set-Content -LiteralPath (Join-Path $outputPath 'commands.txt') -Encoding utf8
$sourceFiles = @('src/grid_pipeline/stress.py', 'src/grid_pipeline/model.py',
                 'src/grid_pipeline/stress_inputs.py', 'scripts/diagnose_s3c.py',
                 'tests/test_stress.py', 'tests/test_stress_inputs.py',
                 'tests/test_stress_rulings.py', 'tests/test_s3c_diagnosis.py',
                 'ledger/definitions/stress-index-v1.toml')
Get-FileHash -Algorithm SHA256 -LiteralPath $sourceFiles |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $outputPath 'source-hashes-before.json') -Encoding utf8
$targetedProcess = Start-Process -FilePath $pythonPath -WindowStyle Hidden -Wait -PassThru `
    -WorkingDirectory $repoPath `
    -ArgumentList @('-m', 'pytest', '-ra', 'tests/test_stress_inputs.py',
                    'tests/test_s3c_diagnosis.py', '--basetemp', "`"$outputPath/targeted-temp`"") `
    -RedirectStandardOutput "$outputPath/targeted.stdout.txt" `
    -RedirectStandardError "$outputPath/targeted.stderr.txt"
$targetedProcess.ExitCode | Set-Content -LiteralPath "$outputPath/targeted.exit-code.txt"
if ($targetedProcess.ExitCode -ne 0) {
    Write-Output "Targeted check failed; evidence=$outputPath"
    exit 1
}
$suiteProcess = Start-Process -FilePath $pythonPath -WindowStyle Hidden -Wait -PassThru `
    -WorkingDirectory $repoPath `
    -ArgumentList @('-m', 'pytest', '-ra', '--basetemp', "`"$outputPath/pytest-temp`"") `
    -RedirectStandardOutput "$outputPath/full-suite.stdout.txt" `
    -RedirectStandardError "$outputPath/full-suite.stderr.txt"
$suiteExit = $suiteProcess.ExitCode
$suiteExit | Set-Content -LiteralPath "$outputPath/full-suite.exit-code.txt"
$probeProcess = Start-Process -FilePath $pythonPath -WindowStyle Hidden -Wait -PassThru `
    -WorkingDirectory $repoPath `
    -ArgumentList @('scripts/diagnose_s3c.py', "`"$martPath`"", '--output', "`"$outputPath/probe.json`"") `
    -RedirectStandardOutput "$outputPath/probe.stdout.txt" `
    -RedirectStandardError "$outputPath/probe.stderr.txt"
$probeExit = $probeProcess.ExitCode
$probeExit | Set-Content -LiteralPath "$outputPath/probe.exit-code.txt"
Get-FileHash -Algorithm SHA256 -LiteralPath $sourceFiles |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $outputPath 'source-hashes-after.json') -Encoding utf8
Write-Output "Suite exit=$suiteExit; probe exit=$probeExit; evidence=$outputPath"
if ($suiteExit -ne 0 -or $probeExit -ne 0) { exit 1 }
