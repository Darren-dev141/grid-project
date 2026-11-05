# Independent receipt accounting. This does not implement a substitute forecast.
$evidencePath = $PSScriptRoot
$probePath = Join-Path $evidencePath 'external-run-fixed/probe.json'
$probeResult = Get-Content -LiteralPath $probePath -Raw | ConvertFrom-Json
$mode = $probeResult.modes.retrospective
$entries = @($mode.dates)
$errors = [System.Collections.Generic.List[string]]::new()
$levels = @('calm', 'watch', 'strained', 'severe')
$scored = @($entries | Where-Object { $_.outcome -in $levels })
if ($entries.Count -ne 2833) { $errors.Add('Wrong target count') }
if (@($entries.date | Sort-Object -Unique).Count -ne 2833) { $errors.Add('Duplicate dates') }
$outcomes = @($entries | Group-Object outcome | ForEach-Object {
    [pscustomobject]@{Outcome=$_.Name;Count=$_.Count}
})
foreach ($outcome in $outcomes) {
    if ($mode.outcomes.($outcome.Outcome) -ne $outcome.Count) {
        $errors.Add('Outcome aggregate mismatch: ' + $outcome.Outcome)
    }
}
$priorPassed = 2833
foreach ($gate in $mode.target_gates.PSObject.Properties) {
    $counts = $gate.Value
    if ($counts.entered -ne $priorPassed -or
        $counts.entered -ne $counts.passed + $counts.rejected) {
        $errors.Add('Target gate accounting mismatch: ' + $gate.Name)
    }
    $priorPassed = $counts.passed
}
if ($priorPassed -ne $scored.Count) { $errors.Add('Classification total mismatch') }
$historyReceipts = 0
foreach ($entry in $entries) {
    $receipt = $entry.receipt
    if (-not $receipt) { continue }
    if ($receipt.mode -ne 'retrospective' -or $receipt.issued_at -ne $null -or
        $receipt.publication_availability -ne 'unverified') {
        $errors.Add('Retrospective mode or invented issuance: ' + $entry.date)
    }
    if (-not $receipt.history_evaluated) { continue }
    $historyReceipts += 1
    $priorPassed = $null
    foreach ($gate in $receipt.history_gates.PSObject.Properties) {
        $counts = $gate.Value
        if ($counts.entered -ne $counts.passed + $counts.rejected -or
            ($null -ne $priorPassed -and $counts.entered -ne $priorPassed)) {
            $errors.Add('Historical gate accounting mismatch: ' + $entry.date + ' ' + $gate.Name)
        }
        $priorPassed = $counts.passed
    }
    if ($receipt.sample_sizes.threshold -ne $receipt.history_gates.season.passed -or
        $receipt.sample_sizes.fit -ne $receipt.history_gates.day_type.passed -or
        $receipt.sample_sizes.analog_candidates -ne $receipt.analog_gates.peak_hour.passed) {
        $errors.Add('Sample count mismatch: ' + $entry.date)
    }
    if ($entry.outcome -notin $levels) { continue }
    if ($receipt.sample_sizes.threshold -lt 20 -or $receipt.sample_sizes.fit -lt 20 -or
        $receipt.sample_sizes.analog_candidates -lt 5 -or
        $receipt.sample_sizes.analogs_selected -ne [Math]::Min(10, $receipt.sample_sizes.analog_candidates)) {
        $errors.Add('Scored below frozen sample floor: ' + $entry.date)
    }
    if (@($receipt.analog_dates).Count -ne $receipt.sample_sizes.analogs_selected -or
        @($receipt.analog_dates | Sort-Object -Unique).Count -ne $receipt.sample_sizes.analogs_selected) {
        $errors.Add('Analog selection count mismatch: ' + $entry.date)
    }
    foreach ($analog in $receipt.analog_dates) {
        if ([datetime]$analog -ge [datetime]$entry.date) {
            $errors.Add('Target or future analog: ' + $entry.date)
        }
    }
}
$integration = $mode.integration
$call = $integration.forecast
$expectedLevel = if ($call.peak_mw -ge $call.thresholds_mw[2]) { 'severe' }
                 elseif ($call.peak_mw -ge $call.thresholds_mw[1]) { 'strained' }
                 elseif ($call.peak_mw -ge $call.thresholds_mw[0]) { 'watch' }
                 else { 'calm' }
if (-not $integration.passed -or -not $integration.complete -or
    $call.status -ne 'SCORED' -or $call.level -ne $expectedLevel -or
    -not $integration.claims_identical_with_alert) {
    $errors.Add('Real integration classification or annotation mismatch')
}
foreach ($source in $probeResult.source_sha256_before.PSObject.Properties) {
    $path = $probeResult.sources.($source.Name)
    if ($source.Value -ne $probeResult.source_sha256_after.($source.Name) -or
        $source.Value -ne (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash) {
        $errors.Add('Source database changed: ' + $source.Name)
    }
}
$result = [pscustomobject]@{
    Passed=($errors.Count -eq 0)
    Targets=$entries.Count
    Scored=$scored.Count
    HistoryReceipts=$historyReceipts
    Outcomes=$outcomes
    Errors=@($errors.ToArray())
}
$result | ConvertTo-Json -Depth 5 |
    Tee-Object -FilePath (Join-Path $evidencePath 'independent-probe-check.json')
if ($errors.Count -ne 0) { throw 'Independent probe accounting failed' }
