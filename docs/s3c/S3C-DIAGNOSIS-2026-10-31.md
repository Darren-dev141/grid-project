# S3c diagnosis, 2026-10-31

**Worker-review revision, verified against the amended source.** Hermes reran the requested checks: **59 targeted tests passed in 1.30 seconds**, followed by **174 full-suite tests passed, one warning in 222.42 seconds**. The official original-cohort probe completed with **1,827 classified, 358 insufficient-fit no-calls, and 648 calendar exceptions**. Prospective calls now fail closed without first-usable/version provenance, and the narrow February 7 false refusal is fixed. The lead checked that all nine recorded source and test hashes remained unchanged during this run and still match the files.

The **pre-review official run** passed **160 tests, with two warnings in 232.36 seconds**. Its real `grid_pipeline.stress.forecast` probe covered the original **2,833 complete dates**: **1,820 classified**, **357 UNSCORED for insufficient fitting history**, and **656 calendar exceptions**. Those exceptions include eight February 7 false refusals, so they are not all genuine open-definition cases. The pre-review real complete date 2025-07-01 returned `SCORED / calm`. These remain historical measurements of the recorded earlier source hashes.

No retrospective result establishes historical issue-time availability or forecast performance. **S3c publication remains blocked by definition questions. Prospective/operational acceptance also lacks immutable availability provenance and real NWS input integration.** Those future input-adapter gaps were assessed, not added to this task's implementation scope. Neither the 7 AM ET cutoff nor D-2 latest completed peak was implemented.

## Independent worker evidence and current decisions

The earlier report's statement that no mirrored reports were available was wrong. Hermes copied both reports while the lead ran. The lead checked the original inaccessible cache locations and used a filename filter that did not match the mirrored `worker-*-report.txt` names. Original access errors did not establish absence of mirrors. Both files have now been read completely and preserved unchanged.

| Worker | Model and reported outcome | Findings used and limits |
| --- | --- | --- |
| [Rulings worker](evidence-2026-10-31-sol/worker-rulings-report.txt) | Independent read-only **gpt-6.1-terra MAX**, identified by Hermes. Review completed with no edits or commits. The worker reports 39 pure-model tests under Python 3.12, but no project-venv DuckDB integration or full suite. | Used pending-to-committed timestamp exposure, late issue acceptance, February 7 false refusal, disconnected NWS inputs and alert mapper, and numerical-definition questions. Verified against owning source. The worker's claim that the helper had no tests was superseded by the lead's three pre-review overlap tests. Its old diagnostic timestamp-pairing finding was already removed before the official run. |
| [Data worker](evidence-2026-10-31-sol/worker-data-report.txt) | Independent read-only **gpt-6.1-terra MAX**, identified by Hermes. Archive review and a conditional pure-model replay completed. The project venv/ABI limitation prevented the official DuckDB diagnostic and prospective measurements. No edits or commits reported. | Used the conditional-versus-unattested distinction, geography and proxy limitation, numeric alert independence, analog eligibility, and DST/completeness cross-check. Raw key counts agree with the official database inventory. Worker-reported filename hash checks are not presented as a new lead hash audit. The conditional replay is not used as the official probe. |

Model identities and MAX settings are supplied session provenance, not independently embedded attestations in the text files. Their worker-reported test outcomes are distinct from the lead's official host runs.

### Known-at verification is unsafe without commit provenance

The [rulings worker, lines 3–5](evidence-2026-10-31-sol/worker-rulings-report.txt) identified a real source problem. [storage.ingest](../../src/grid_pipeline/storage.py) writes `loaded_at` when indexing, including pending batches. [EIA fetch](../../src/grid_pipeline/fetch.py) indexes with `committed=False`, then later updates `committed=TRUE` and mutable `observed_at` in another transaction. [NCEI fetch](../../src/grid_pipeline/ncei.py) does the same. Replays preserve the old `loaded_at` and replace `observed_at`. Neither column is an immutable first-usable commit-completion event.

The loader selects batches committed **now**, then places indexing timestamps in legacy `*_available_at` fields. A value indexed before issuance but committed afterward can therefore pass the old timestamp comparison on a later replay. The old `verified_at_issuance` label checked supplied timestamps, not their provenance or binding to the exact supplied values. It was unsafe. The raw loader's docstring now explicitly states this limitation.

**Direct fix:** current `forecast()` keeps prospective receipts `unverified` and returns `UNSCORED / unverified_issue_time_availability` after basic input checks. Supplying earlier timestamps or first-recorded boolean flags cannot enable a prospective forecast. The current input contract has no representation that proves first-usable/version provenance, so prospective operation is intentionally unavailable until a verified adapter exists. No new attestation flag or invented commit timestamp was introduced. This enforces the existing no-lookahead constraint instead of choosing a new meaning of availability. The updated synthetic prospective tests passed in the 59-test targeted run and 174-test full suite; this proves refusal behavior, not real-world source provenance.

The same worker reproduced a late issue being scored. [The existing architecture, append step](../architecture-s3-s7.md), and `PLAN.md` already require issuance before the target local date starts. The model now enforces that documented boundary directly, with `issue_time_not_before_target_date`, including New York DST boundaries. This is not the deferred 7 AM rule.

### The alert helper is not a real NWS integration

The [rulings worker, lines 9–13](evidence-2026-10-31-sol/worker-rulings-report.txt), correctly identified an integration gap. A fresh bounded source search across `src/grid_pipeline` and `scripts` finds no production caller of `annotate_alert_interval`; tests are its callers. Graph traces did not recover even known source calls, so the absence conclusion relies on direct source search as well as reading the relevant modules, not a zero-edge graph result alone.

The pre-review three synthetic tests cover overlap, midnight, DST, and a short interval. New tests cover clipping, no overlap, naive endpoints, empty or reversed intervals, and reversed requested date ranges. All ten cases in `test_stress_inputs.py`, including the separate raw-history regression, passed in the current host run. None establishes raw NWS payload → resolved interval → date annotations → `Features.alerts`, alert-version availability at issuance, or actual alert receipts. The synthetic real-target annotation only verifies numeric invariance.

`nws_alerts.sql` exposes `effective`, `onset`, `expires`, and `ends` but does not choose interval endpoints. Endpoint precedence and missing-endpoint behavior remain unresolved, so no adapter was improvised. Alerts remain outside the stress level.

The target-weather path is also absent. The current cleaned NWS daily view groups nighttime lows by the period's **start** date. It is not a valid direct supplier of D's morning low under the settled morning-end-date convention. Existing `nws.fetch` pins Reisterstown LWX/100,98, whereas v1 names BWI LWX/107,85. These existing S2 inputs were not silently repurposed or rewritten. A version-bound BWI period-level feature adapter, correct high/low alignment, and real-shape integration coverage are acceptance blockers.

### Calendar bug versus actual definition changes

The [rulings worker, line 7](evidence-2026-10-31-sol/worker-rulings-report.txt), found a direct false positive. For target February 7, the inclusive 43-day window is January 17 through February 28 in leap and non-leap years. It contains no February 29 and crosses no year boundary. Changing `first <= February28 <= last` to `first <= February28 < last` removes only this erroneous endpoint refusal. New tests cover targets in 2024, 2025, 2026, and 2028, with exact included and excluded dates.

The original official probe contains one such false refusal in each year 2019–2026. Those eight measured old outcomes are extracted in [previous-february-7-refusals.json](evidence-2026-10-31-sol/worker-review/previous-february-7-refusals.json). The actual current probe changed exactly these eight target outcomes: 2019-02-07 is insufficient-fit, 2024-02-07 and 2026-02-07 are watch, and the other five are calm. No other target outcome changed. See [changed-target-outcomes.json](evidence-2026-10-31-sol/worker-review/changed-target-outcomes.json). These are measured results, not deductions substituted for execution.

The worker's broader suggestion to remove all New Year refusals was **not adopted**. The existing definition documents explicitly leave year-boundary and leap-window construction open. Choosing historical-year anchors, wrap membership, or leap-day handling would alter meaning. Those guards and the `DefinitionGap` exception remain pending a ruling. The near-zero tolerance and analog z-score reference-population questions also remain untouched.

### Official probe versus the conditional worker replay

The [data worker, lines 1–9 and 19–31](evidence-2026-10-31-sol/worker-data-report.txt), explicitly labels its reconstruction conditional. It manually sets first-recorded flags from retained JSON membership, without assigning availability timestamps or proving committed database membership. It reports 1,820 classified, 357 fit-history failures, and 656 calendar exceptions. With flags unset it reports zero classified, 2,177 threshold-history failures, and 656 calendar exceptions. These are worker-reported conditional sensitivity results, not official database probe outcomes or prospective forecasts.

The separate official `external-run-fixed/probe.json` came from the actual read-only DuckDB loader and committed raw metadata, executed by Hermes. It independently measured the same retrospective counts before this revision. Agreement does not prove historical publication or first-commit availability. The current official rerun is the distinct `external-run-worker-review/probe.json` described below. Both official probes explicitly set freshness flags true to study calculation eligibility. That assumption is not a historical freshness measurement. The current diagnostic supplies no issue timestamp or first-recorded timestamp for the settled target weather, so the workers' old timestamp-pairing criticism does not apply to either official retrospective run.

### Completed current-code host rerun

Hermes executed the requested handoff:

```powershell
powershell -NoProfile -File C:\Users\ajbig\Documents\grid-project\scripts\verify_s3c_sol.ps1 -EvidenceDirectory docs/s3c/evidence-2026-10-31-sol/external-run-worker-review
```

The runner targeted `tests/test_stress.py`, `tests/test_stress_rulings.py`, `tests/test_stress_inputs.py`, and `tests/test_s3c_diagnosis.py`, followed by the full suite and the official original-cohort probe. All three exit codes are 0. This rerun was required because `stress.py`, its tests, input tests/docstring, and the runner changed after the earlier success. No extra execution is pending against the current source. Source changes stop at the direct bugs above. No commits.

| Current evidence | File |
| --- | --- |
| Exact actual command lines | [commands.txt](evidence-2026-10-31-sol/external-run-worker-review/commands.txt) |
| 59 targeted tests, full stdout | [targeted.stdout.txt](evidence-2026-10-31-sol/external-run-worker-review/targeted.stdout.txt) |
| 174 tests, full suite stdout | [full-suite.stdout.txt](evidence-2026-10-31-sol/external-run-worker-review/full-suite.stdout.txt) |
| Full suite stderr, empty | [full-suite.stderr.txt](evidence-2026-10-31-sol/external-run-worker-review/full-suite.stderr.txt) |
| Official probe stdout | [probe.stdout.txt](evidence-2026-10-31-sol/external-run-worker-review/probe.stdout.txt) |
| Official probe stderr, empty | [probe.stderr.txt](evidence-2026-10-31-sol/external-run-worker-review/probe.stderr.txt) |
| Every current target, receipt, gate, and source audit | [probe.json](evidence-2026-10-31-sol/external-run-worker-review/probe.json) |
| Independent accounting checks, zero issues | [current-independent-probe-check.json](evidence-2026-10-31-sol/worker-review/current-independent-probe-check.json) |
| Nine source/test hashes unchanged during run and current | [current-source-preservation.json](evidence-2026-10-31-sol/worker-review/current-source-preservation.json) |

Actual full-suite summary:

```text
================= 174 passed, 1 warning in 222.42s (0:03:42) ==================
```

The warning was `RuntimeWarning: dbt concurrent send_bytes() failure: retrying` in `test_nws_dbt_rejects_invalid_forecast_fields[temperature-NaN]`. The retry succeeded. No tests failed or were skipped. The independent audit checks all 2,833 unique dates, target and history gate conservation, sample floors, strictly prior unique analog dates, unchanged source databases, and exact changed-outcome scope.

### Current official probe results

The real 2025-07-01 integration still returns `SCORED / calm`, 130,741.70325439323 MW, local hour ending 18, with 150 threshold days, 107 fitting/analog candidates, and ten selected analogs. Numeric claims are unchanged by a separately labeled synthetic annotation. It remains an observed-weather retrospective result with `publication_availability: unverified` and no issue timestamp.

| Year | Original targets | Classified | Insufficient fitting history | Calendar exceptions |
| --- | ---: | ---: | ---: | ---: |
| 2019 | 361 | 0 | 279 | 82 |
| 2020 | 356 | 193 | 79 | 84 |
| 2021 | 363 | 279 | 0 | 84 |
| 2022 | 363 | 280 | 0 | 83 |
| 2023 | 364 | 280 | 0 | 84 |
| 2024 | 364 | 280 | 0 | 84 |
| 2025 | 365 | 281 | 0 | 84 |
| 2026 | 297 | 234 | 0 | 63 |
| **Total** | **2,833** | **1,827** | **358** | **648** |

Current labels are 1,412 calm, 330 watch, 71 strained, and 14 severe. Threshold samples range from 20 to 150 days. Fit and candidate pools range from five to 108 before sample refusal; classified candidate pools range from 28 to 108, with ten analogs each and no analog-floor rejection.

| Current target gate, in order | Entered | Passed | Rejected |
| --- | ---: | ---: | ---: |
| Freshness flags, assumed true for this probe | 2,833 | 2,833 | 0 |
| Target temperatures present | 2,833 | 2,833 | 0 |
| Calendar definition | 2,833 | 2,185 | 648 |
| Threshold stratum >=20 | 2,185 | 2,185 | 0 |
| Fitting stratum >=20 | 2,185 | 1,827 | 358 |
| Analog floor >=5 | 1,827 | 1,827 | 0 |
| Classified | 1,827 | 1,827 | 0 |

Current historical gates sum target-history pairs over the 2,185 calendar-evaluable targets, not distinct history days:

| History/analog gate | Entered pairs | Passed pairs | Rejected pairs |
| --- | ---: | ---: | ---: |
| Strictly before D | 6,246,915 | 3,179,090 | 3,067,825 |
| History years | 3,179,090 | 2,221,005 | 958,085 |
| Demand complete | 2,221,005 | 2,201,007 | 19,998 |
| Finite load | 2,201,007 | 2,201,007 | 0 |
| First-recorded archive attestation | 2,201,007 | 2,201,007 | 0 |
| Finite high and low | 2,201,007 | 2,201,007 | 0 |
| Retrospective availability, explicitly unverified | 2,201,007 | 2,201,007 | 0 |
| Unique date | 2,201,007 | 2,201,007 | 0 |
| Seasonal window | 2,201,007 | 253,945 | 1,947,062 |
| Same day type | 253,945 | 149,833 | 104,112 |
| Valid analog peak-hour label | 149,833 | 149,833 | 0 |
| Nearest-ten selection after fit floor | 144,957 | 18,270 | 126,687 |

Fit refusal removes 4,876 candidate pairs before nearest-ten selection. Unselected neighbors are not missing-data failures. Repeated seasonal/day-type entries in the analog receipt must not be added to history exclusions twice. Real fallback counts are 190 heat-hinge minimum refusals and 759 cold-hinge minimum refusals. No real case uses a numerical singularity fallback or fewer-than-ten analogs.

The source inventory, DST/completeness counts, and necessary-condition availability result are unchanged: zero of 4,011,528 prior complete pairs were even indexed before the target date ended. The true commit might be later still, so treating indexing time as a lower bound cannot establish availability. Prospective measurements remain `NOT RUN`; current code refuses unsupported prospective claims. The 648 remaining exceptions retain `calendar boundary and leap-day selection is unspecified`. New Year and leap handling still require the exact decisions below.

Current suspect verdicts, in the requested order:

| Order | Current verdict |
| --- | --- |
| (a) First recorded/known at | Confirmed provenance gap. Index time may precede commit. Prospective mode now fails closed and never claims `verified_at_issuance`. |
| (b) Geography | PJM demand is correctly selected for the current plan; 168 BGE hours cannot replace its 68,594-hour history. BWI as a regional weather proxy remains unvalidated for forecast error. |
| (c) Alerts/receipts | No external numeric dependency. Real NWS annotation/feature integration remains absent, and the previously unsafe verification label is disabled. |
| (d) Analog collapse | No analog-floor rejection among 1,827 classified targets; candidate pools are 28–108. The 358 no-calls fail the earlier fitting floor. |
| (e) Calendar/completeness/DST | Eight February 7 false refusals are fixed. 648 calendar exceptions remain under unresolved conventions. Existing complete DST dates can classify; DST is not a universal failure. |

## Pre-review official evidence and commands

The pre-review run used the existing project venv, Python 3.14.7 and pytest 9.2.0. Hermes executed the prepared runner outside the restricted Codex sandbox. The lead inspected the raw outputs and independently checked all per-date receipt accounting with PowerShell. Every measured count in the following historical sections is from that earlier run, not the amended source above.

| Evidence | Path |
| --- | --- |
| Actual final commands | [commands.txt](evidence-2026-10-31-sol/external-run-fixed/commands.txt) |
| Full final test stdout | [full-suite.stdout.txt](evidence-2026-10-31-sol/external-run-fixed/full-suite.stdout.txt) |
| Full final test stderr, empty | [full-suite.stderr.txt](evidence-2026-10-31-sol/external-run-fixed/full-suite.stderr.txt) |
| Full-suite exit code, 0 | [full-suite.exit-code.txt](evidence-2026-10-31-sol/external-run-fixed/full-suite.exit-code.txt) |
| Targeted regression, six passed in 1.15 seconds | [targeted.stdout.txt](evidence-2026-10-31-sol/external-run-fixed/targeted.stdout.txt) |
| Full real probe stdout | [probe.stdout.txt](evidence-2026-10-31-sol/external-run-fixed/probe.stdout.txt) |
| Full real probe stderr, empty | [probe.stderr.txt](evidence-2026-10-31-sol/external-run-fixed/probe.stderr.txt) |
| Probe exit code, 0 | [probe.exit-code.txt](evidence-2026-10-31-sol/external-run-fixed/probe.exit-code.txt) |
| Every target outcome, receipt, gate, source inventory, and provenance bound | [probe.json](evidence-2026-10-31-sol/external-run-fixed/probe.json) |
| Extracted counts and real integration | [final-probe-summary.json](evidence-2026-10-31-sol/final-probe-summary.json) |
| Independent receipt checks, passed | [independent-probe-check.json](evidence-2026-10-31-sol/independent-probe-check.json) |
| Independent yearly totals | [yearly-probe-check.json](evidence-2026-10-31-sol/yearly-probe-check.json) |
| All nine measured source and test files unchanged during final run | [fixed-run-source-preservation.json](evidence-2026-10-31-sol/fixed-run-source-preservation.json) |

The final raw pytest summary is:

```text
================= 174 passed, 1 warning in 222.42s (0:03:42) =================
```

The single warning was `RuntimeWarning: dbt concurrent send_bytes() failure: retrying`, in `test_nws_dbt_rejects_invalid_forecast_fields[temperature-NaN]`. The retry succeeded. No tests were skipped, failed, or reduced in scope. This is a current execution, not the earlier 132-test result.

The external handoff command was:

```powershell
powershell -NoProfile -File C:\Users\ajbig\Documents\grid-project\scripts\verify_s3c_sol.ps1 -EvidenceDirectory docs/s3c/evidence-2026-10-31-sol/external-run-worker-review
```

The runner recorded and executed these commands from `C:/Users/ajbig/Documents/grid-project`, with native stdout and stderr saved separately:

```powershell
& 'C:\Users\ajbig\Documents\grid-project\.venv\Scripts\python.exe' -m pytest -ra tests/test_stress.py tests/test_stress_rulings.py tests/test_stress_inputs.py tests/test_s3c_diagnosis.py --basetemp 'C:\Users\ajbig\Documents\grid-project\docs\s3c\evidence-2026-10-31-sol\external-run-worker-review/targeted-temp'
& 'C:\Users\ajbig\Documents\grid-project\.venv\Scripts\python.exe' -m pytest -ra --basetemp 'C:\Users\ajbig\Documents\grid-project\docs\s3c\evidence-2026-10-31-sol\external-run-worker-review/pytest-temp'
& 'C:\Users\ajbig\Documents\grid-project\.venv\Scripts\python.exe' scripts/diagnose_s3c.py 'C:/Users/ajbig/AppData/Local/Temp/grid-s3c-20261030/history-complete/grid.duckdb' --output 'C:\Users\ajbig\Documents\grid-project\docs\s3c\evidence-2026-10-31-sol\external-run-worker-review/probe.json'
```

The independent audit re-counted all 2,833 unique dates and outcomes, checked sequential gate conservation, sample floors, unique and strictly prior analog dates, retrospective receipts without invented issue times, integration-level comparisons, alert invariance, and unchanged database hashes. It used explicit PowerShell shell commands. The saved [audit-probe.ps1](evidence-2026-10-31-sol/audit-probe.ps1) records the accounting logic. Loading that file was blocked by the shell's execution policy; no policy was changed. The equivalent explicit checks completed with zero accounting errors.

## Diagnosis and implementation

The interrupted session had already implemented the production `HistoryDay`, `Features`, `Forecast`, and `ForecastReceipt` types, a calculation path in `stress.forecast`, a first-recorded input loader, and ruling tests. Those files were untracked, so their starting contents were copied under [initial](evidence-2026-10-31-sol/initial). The old documentation describing unconditional refusal was stale relative to this partial code.

The first external full suite actually ran and found **159 passed, one failed, two warnings in 234.10 seconds**. The real probe failed in the same loader before its target loop. Its unparenthesized DuckDB JSON predicates combined extraction with `AND`, causing a conversion failure rather than selecting the intended source rows.

The production fix parenthesizes the `respondent`, `type`, and `STATION` extractions in [stress_inputs.py](../../src/grid_pipeline/stress_inputs.py). It changes three predicates and preserves geography and revision selection. The existing first-recorded regression then passed, followed by the full suite and real probe. See [stress-input-loader.diff](evidence-2026-10-31-sol/stress-input-loader.diff).

The diagnosis script previously assigned a hypothetical 21:17 UTC issue time to each historical date and labeled those calls prospective operation. I removed that simulation. The final probe calls the real `forecast()` with observed calendar-day target temperatures and first-recorded fitting history. It labels retrospective publication availability `unverified` and prospective results `NOT RUN`.

Changed files are:

| File | Change |
| --- | --- |
| [src/grid_pipeline/stress.py](../../src/grid_pipeline/stress.py) | Worker review: refuse unsupported prospective claims and late issues; remove the February 7 endpoint false refusal. Verified in the current host run. |
| [src/grid_pipeline/stress_inputs.py](../../src/grid_pipeline/stress_inputs.py) | Parenthesize the three failing raw JSON filters. |
| [scripts/diagnose_s3c.py](../../scripts/diagnose_s3c.py) | Preserve the original cohort; call the real model; record sequential gates, per-date receipts, ordered source audits, and hashes; remove hypothetical historical issue times; require a real complete-date classification; serialize infinite condition diagnostics as strings in strict JSON. |
| [scripts/verify_s3c_sol.ps1](../../scripts/verify_s3c_sol.ps1) | New external verification runner with targeted tests, full suite, real probe, raw logs, and source hashes. |
| [tests/test_stress.py](../../tests/test_stress.py) | Worker review: exact seasonal membership for four February 7 target years. |
| [tests/test_stress_rulings.py](../../tests/test_stress_rulings.py) | Worker review: timestamps alone do not establish availability; no late prospective claims across ordinary and DST dates. |
| [tests/test_stress_inputs.py](../../tests/test_stress_inputs.py) | Pre-review overlap cases plus clipping, no-overlap, and invalid-interval checks. All ten current cases passed. |
| [tests/test_s3c_diagnosis.py](../../tests/test_s3c_diagnosis.py) | Two synthetic checks of local-date availability bounds and strict JSON diagnostics. |
| This report and its evidence directory | Preserve the starting state, failures, completed results, source fingerprints, and independent checks. |

The public model types and TOML definition remain unchanged. `stress.py` now includes the worker-review safety and calendar fixes described above. No alternate forecast implementation or substitute dataset supplied the pre-review measured results. Synthetic tests and the synthetic alert-invariance annotation are explicitly labeled.

## Real complete-date integration

The integration uses the original real mart target for **2025-07-01**, with **91 F high and 74 F calendar-day low**, and real first-recorded history from the two raw warehouses. It uses observed hindsight weather, not a historical NWS issuance.

| Field | Actual result |
| --- | --- |
| Status and level | `SCORED`, `calm` |
| Predicted daily peak | 130,741.70325439323 MW |
| Predicted peak hour ending, local | 18 |
| Frozen p75, p90, p97 thresholds | 133,441.0; 143,203.9; 150,440.77000000002 MW |
| Threshold days | 150 |
| Same-day-type fitting days | 107 |
| Analog candidates and selected | 107 candidates, ten selected |
| Regression | Intercept 87,838.92500450257 and heat coefficient 1,650.1068557650253 |
| Hinge fallback | `cold_hinge_fewer_than_10_nonzero_days` |
| Initial and final condition number | 87.93289768175437 |
| Issue time and availability | `issued_at: null`; `publication_availability: unverified` |
| Synthetic alert-invariance check | Numeric claims identical with and without the synthetic annotation |

The exact definition SHA-256 is `63cb57268398ee62525499c64ecbf4c7694f2d5960eccf2a0eb2f3f3059fbfca`. The full forecast, receipt, and selected analog dates are in the probe's `modes.retrospective.integration` object. Every selected analog predates the target.

## Modes and first-recorded provenance

**Retrospective reconstruction.** The original mart supplies observed TMAX(D) and TMIN(D), joined on the calendar-day spine. Fitting uses dates strictly before D and the earliest retained raw values. This is an observed-weather eligibility reconstruction. It is not validation of historical issued forecasts or forecast skill.

**Prospective operation.** Current code refuses numerical claims without verified issue-time provenance, even when caller timestamps are timezone-aware and precede issuance. Its receipt remains `unverified`. The pre-review official probe never ran prospective mode and did not invent evidence or backdated receipts. The 7 AM ET and D-2 decisions remain next-step context.

The loader selects the earliest `raw.batches.loaded_at` for each retained PJM hour and BWI date from committed batches, then reuses the existing dbt cleaning and daily aggregation. Missing or invalid first temperatures stay missing even when a later revision supplies a value. `loaded_at` is local archive evidence, not the provider's original publication time or proof that no earlier unretained revision existed. `observed_at` and settled cleaned views do not fill that provenance gap.

The actual retained load timestamps span **2026-10-29 03:31:12.786993 through 10:55:55.803599 UTC**. Retained temperature timestamps span **2026-10-29 13:09:13.056009 through 13:09:29.233985 UTC**. Both archives were recorded after the last probe target, 2026-10-24. There are no missing `loaded_at` values in the committed source batches inspected.

The necessary-condition audit considered **4,011,528 prior complete date pairs** across all original targets. **Zero pairs** had both sources recorded before the target local date ended. **Zero targets** had even one pair passing that loose bound. The exclusive end of a target local date is an audit bound, not an issuance cutoff or a manufactured issue timestamp. Passing the bound would still not prove availability at a real issuance. Failing it shows that this retained archive cannot establish an earlier as-of forecast.

The first-snapshot reconstruction contains 2,859 dates and 2,836 demand-complete dates. Its peak-MW and high/low values show no differences from the supplied settled mart in the fields compared. That does not prove absence of revisions before this archive existed. Settled actuals remain distinct from first-recorded fitting inputs.

The load quality model uses neighboring hours. The loader conservatively includes those neighbors' recorded times in availability. Retrospective mode does not thereby establish issue-time causality: the last interval of a prior date can depend on the next date's first interval for its quality flag. The report does not claim a causal historical publication pipeline.

## Pre-review suspect verdict snapshot

| Order | Verdict | Evidence |
| --- | --- | --- |
| (a) First-recorded and known-at availability | **Confirmed historical provenance blocker.** It does not force the labeled retrospective reconstruction to reject every date. | Earliest retained load and temperature times are after all probe targets. Zero of 4,011,528 prior date pairs pass even the loose target-date-end availability bound. No issue times were invented. |
| (b) BGE study geography versus deep PJM history | **BGE is too shallow for a multiyear study. The current plan deliberately requires PJM-wide calls with Maryland weather.** A BGE-specific claim would require a new scope decision and deeper data. | Fresh raw inventory has 68,594 distinct PJM demand hours, 2019-01-01 00:00 through 2026-10-29 02:00 UTC, versus only 168 BGE hours, 2026-10-20 00:00 through 2026-10-26 23:00 UTC. `PLAN.md` retires the BGE charging advisor. The loader and mart select PJM demand with BWI weather. BGE was not blended into the model. |
| (c) Alerts and receipts dependency | **Eliminated as a numeric forecast blocker.** Missing historical issuances still block prospective validation. | The ledger inventory contains no forecast receipts. The real function still classifies. It constructs its own return receipt and only annotates supplied alerts. The real-date synthetic alert check leaves every numeric claim unchanged. |
| (d) Analog pool collapse | **Eliminated as a universal explanation.** The observed early-history refusal is the fitting-stratum floor. | All 1,820 eligible targets pass the analog floor. Their candidate pools range from 28 through 108 days, and all select ten. The 357 fit rejections are 278 dates in 2019 and 79 weekend dates in 2020. No target is rejected for insufficient analogs. |
| (e) Date, completeness, and DST | **Calendar ambiguity remains a real definition blocker. DST does not cause universal refusal.** | There are 656 calendar refusals. Among 15 DST dates, nine are demand-complete and six incomplete. Complete 25-hour dates 2021-11-07, 2024-11-03, and 2025-11-02 classify as calm. The three complete dates without temperatures lie outside the original target cohort. |

The ordered evidence is also stored in `probe.json` under `suspects_in_order`. Source inventory confirms 16 committed PJM batches, one BGE batch, and eight NCEI batches with 2,854 daily temperature rows. The bounded ledger inventory is not proof about receipts that might exist outside the supplied repository.

## Original cohort and measured outcomes (pre-review run; current worker-review run: 1,827 classified, 358 fit, 648 calendar)

The source remains the original scratch mart, opened read-only. The selected target cohort has the exact original yearly counts and 2,833 unique dates, 2019-01-01 through 2026-10-24. Its sorted date-list SHA-256 is `755b973f0451066dc8552ee6879b65f10ac806bf85582adf3fece54c2397e09a`.

| Year | Original complete targets | Classified | Insufficient fitting history | Calendar DefinitionGap |
| --- | ---: | ---: | ---: | ---: |
| 2019 | 361 | 0 | 278 | 83 |
| 2020 | 356 | 192 | 79 | 85 |
| 2021 | 363 | 278 | 0 | 85 |
| 2022 | 363 | 279 | 0 | 84 |
| 2023 | 364 | 279 | 0 | 85 |
| 2024 | 364 | 279 | 0 | 85 |
| 2025 | 365 | 280 | 0 | 85 |
| 2026 | 297 | 233 | 0 | 64 |
| **Total** | **2,833** | **1,820** | **357** | **656** |

Classifications are **1,407 calm, 328 watch, 71 strained, and 14 severe**. These are model classifications under observed target weather, not measures of forecast accuracy. No MAE, hour-hit rate, precision, recall, or historical NWS forecast validation is claimed.

The 2020 fit rejections are 39 Saturdays and 40 Sundays. All weekday and weekend fitting uses the frozen 20-day floor. The old probe's 2,833 unconditional refusals remain preserved separately in [prior-history-probes.txt](evidence-2026-10-31-sol/prior-history-probes.txt); they were not reused as current results.

## Pre-review sequential gates and exclusions

Target-level rejections are exclusive at the first failed gate:

| Target gate | Entered | Passed | Rejected |
| --- | ---: | ---: | ---: |
| Freshness | 2,833 | 2,833 | 0 |
| Target high and low present | 2,833 | 2,833 | 0 |
| Calendar definition | 2,833 | 2,177 | 656 |
| Threshold stratum, >=20 | 2,177 | 2,177 | 0 |
| Same-day-type fitting stratum, >=20 | 2,177 | 1,820 | 357 |
| Analog floor, >=5 | 1,820 | 1,820 | 0 |
| Classified | 1,820 | 1,820 | 0 |

Historical row gates below sum **target-history pairs**, not distinct days. They cover the 2,177 targets whose calendar definition was available. The 656 calendar exceptions occur before history selection and therefore have no invented history counts.

| Historical row gate | Entered pairs | Passed pairs | Rejected pairs |
| --- | ---: | ---: | ---: |
| Strictly before target D | 6,224,043 | 3,168,558 | 3,055,485 |
| Last three complete years plus current year | 3,168,558 | 2,214,131 | 954,427 |
| Demand complete | 2,214,131 | 2,194,197 | 19,934 |
| Finite load | 2,194,197 | 2,194,197 | 0 |
| First-recorded attestation | 2,194,197 | 2,194,197 | 0 |
| Finite high and low | 2,194,197 | 2,194,197 | 0 |
| Retrospective availability, unverified | 2,194,197 | 2,194,197 | 0 |
| Unique date | 2,194,197 | 2,194,197 | 0 |
| Seasonal window | 2,194,197 | 253,003 | 1,941,194 |
| Same day type | 253,003 | 149,271 | 103,732 |
| Valid peak-hour label | 149,271 | 149,271 | 0 |

The retrospective availability row does not test issue-time timestamps. Its zero rejections must not be presented as proof of prospective availability. The separate necessary-condition audit above has zero available historical pairs.

Threshold samples range from 20 through 150 days. Fit and analog candidate samples range from five through 108 before target-level sample refusal. On classified targets, analog candidates range from 28 through 108. Fit rejection removes 4,861 candidate pairs before selection. The remaining 144,410 candidate pairs supply 18,200 selected analogs, exactly ten per classified target. The 126,210 other candidates are outside the nearest-ten selection, not missing-data exclusions. Seasonal and day-type entries duplicated in the analog receipt overlap the history table and must not be added twice.

Actual calculation fallbacks were `heat_hinge_fewer_than_10_nonzero_days` on 185 classified dates and `cold_hinge_fewer_than_10_nonzero_days` on 759. No real target required the near-zero-variance, ill-conditioned, intercept-only, or fewer-than-ten-analogs fallback in this probe. Those branches are exercised by synthetic ruling tests.

The original mart has 2,859 dates, with expected-hour counts of 2,844 ordinary dates, eight 23-hour dates, and seven 25-hour dates. Demand is complete on 2,836 dates and incomplete on 23. Temperatures are present on 2,854 dates. The three demand-complete dates without temperatures are 2026-10-25, 2026-10-26, and 2026-10-27. They are excluded from the original target cohort, never imputed. Missing historical temperatures contribute zero rejections after the earlier gates in this specific cohort; this does not mean the entire mart has no missing temperatures. See [dst-probe-outcomes.json](evidence-2026-10-31-sol/dst-probe-outcomes.json) for every DST outcome.

## Frozen rulings and definition questions for Darren through Alder

The pre-review source implemented linear/type-7 `np.quantile`, z-scored Euclidean analog distance, ten-nearest selection, newest distance ties, earlier hour-mode ties, separate 20-day threshold and fit floors, a five-analog floor, missing-temperature exclusion, first-recorded prior-date fitting, and annotation-only alerts. Its 23 ruling tests passed against that recorded earlier version. The current run passed 27 ruling tests, all other stress/input tests, the full 174-test suite, and real integration.

**No definition changes were made. These questions remain explicit:**

1. **Calendar window.** How exactly does the +/-21-day window map across New Year and between leap and non-leap years? Define historical-year anchors and included dates for January 1 and for windows spanning February 29. Existing docs list this as unresolved. The earlier 656 exceptions included eight unambiguous February 7 false positives now fixed. The current official run measures 648 remaining exceptions. The preserved exception text is:

```text
calendar boundary and leap-day selection is unspecified
```

2. **Numerical convention in the interrupted implementation.** What defines near-zero hinge variance, and does the 1e10 condition threshold apply to the design matrix X or the normal-equation matrix X-transpose-X? The inherited code uses X and `std(column) <= max(1, max(abs(column))) / 1e10`, with a single-hinge condition check. No supplied document freezes that exact tolerance. I preserved and disclosed it rather than choosing another meaning. No real target used that fallback in either official probe. The [rulings worker, line 15](evidence-2026-10-31-sol/worker-rulings-report.txt), gives a numerical boundary reproduction. That literal reproduction was not independently rerun; the owning code and missing numerical definition were verified. It remains a definition question, not a newly proven numeric defect.
3. **NWS endpoint precedence for annotations.** Which start and end fields apply when `effective`, `onset`, `expires`, and `ends` differ? The any-overlap ruling settles local-date mapping once explicit endpoints exist. The inherited helper takes an explicit half-open interval and annotates all overlapped New York dates, including DST. It does not choose NWS endpoint precedence. This question blocks annotation validation only, never stress level.

4. **Analog normalization population.** Does the z-score scale come from all valid same-day-type fitting days or only the candidates that also have valid peak-hour labels? `_analogs` currently uses the latter. The [rulings worker, line 17](evidence-2026-10-31-sol/worker-rulings-report.txt), flags that the supplied frozen wording does not select a reference population. No change was made. The official data had no peak-hour exclusions, so this distinction did not affect its measured classifications.

5. **Input provenance acceptance.** What immutable evidence must bind a source/version's exact values to first usable commit or visibility before issuance? `loaded_at`, mutable `observed_at`, and caller boolean flags cannot answer that question. There is no safe historical backfill for an event that was not recorded. This is a provenance and adapter acceptance requirement, not a request to change the no-lookahead rule. Prospective operation remains closed until it is met. What version-bound BWI forecast and NWS alert inputs can be supplied for an end-to-end check?

Historical availability is a separate evidence limitation, not permission to invent a definition or timestamps. The 7 AM ET issuance cutoff and D-2 latest completed peak were left untouched. There is no new alert bump, temperature imputation, seasonal mapping, availability substitution, or retrospective claim masquerading as an issued forecast.

## Failures, gaps, and recovered execution errors

The initial sandbox commands actually attempted were:

```powershell
git status --short
rg --files -g AGENTS.md -g pyproject.toml -g README.md -g '*s3c*' -g '*S3C*' -g '*forecast*' -g '*stress*' -g '*probe*' -g '*ruling*' -g '*lock*'
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pytest -ra --basetemp docs/s3c/evidence-2026-10-31-sol/pytest-temp
.\.venv\Scripts\python.exe scripts/diagnose_s3c.py 'C:/Users/ajbig/AppData/Local/Temp/grid-s3c-20261030/history-complete/grid.duckdb' --output docs/s3c/evidence-2026-10-31-sol/probe.json
```

Git reported `fatal: detected dubious ownership in repository at 'C:/Users/ajbig/Documents/grid-project'`. Subsequent inspection used only `git -c safe.directory=C:/Users/ajbig/Documents/grid-project ...`; global configuration was not changed. The shell reported `rg : The term 'rg' is not recognized as the name of a cmdlet, function, script file, or operable program.` Searches used PowerShell instead.

All three local venv launch attempts exited 1 before Python started, with this error verbatim:

```text
error: uv trampoline failed to spawn Python child process

  Caused by: permission denied (os error 5)
```

Raw launch evidence is preserved in [runtime-check.txt](evidence-2026-10-31-sol/runtime-check.txt), [local suite stderr](evidence-2026-10-31-sol/full-suite.stderr.txt), and [local probe stderr](evidence-2026-10-31-sol/probe.stderr.txt). The session has approval policy `never` and no escalated execution route. Hermes's external runner resolved the runtime blocker without changing dependencies, test scope, or data.

The first external probe error, before the three-predicate fix, was:

```text
_duckdb.ConversionException: Conversion Error: Failed to cast value to numerical: {"period":"2019-03-27T07","respondent":"PJM","resp... when casting from source column payload

LINE 6:                         AS loaded_at
                               ^
```

The synthetic regression exposed the same conversion failure with its synthetic temperature payload. The complete failure, traceback, and first full suite are retained in [first external suite stdout](evidence-2026-10-31-sol/external-run/full-suite.stdout.txt) and [first external probe stderr](evidence-2026-10-31-sol/external-run/probe.stderr.txt). The final run has both exit codes 0. No argparse usage error occurred in either external run.

Loading the optional independent-audit file also reported:

```text
File C:\Users\ajbig\Documents\grid-project\docs\s3c\evidence-2026-10-31-sol\audit-probe.ps1 cannot be loaded
because running scripts is disabled on this system.
```

The accounting was then checked through explicit PowerShell commands, with no execution-policy change. A preflight fingerprint request used the nonexistent name `history-complete/verified.duckdb`; it was corrected to the existing `history-complete/grid.duckdb` before any probe. No new source mart was manufactured.

## Preservation and worker-report status

The initial state had eight modified tracked files and many untracked files from the interrupted session. See [initial-git-status.txt](evidence-2026-10-31-sol/initial-git-status.txt) and the initial snapshots. The pre-review audit preserved all 53 then-unrelated files. Three of those files are now explicitly changed for this worker review: `stress.py`, `test_stress.py`, and `test_stress_rulings.py`. All **50 remaining pre-existing unrelated files** remain unchanged by SHA-256. See [worktree-preservation-check.json](evidence-2026-10-31-sol/worktree-preservation-check.json).

All three databases retained their original hashes before and after verification:

| Database | SHA-256 |
| --- | --- |
| `data/s1-live/grid.duckdb` | `0AE80A9A1939B78FFCF471F9998FBFC9A51749B039713DBC2ABFF7022D8337C3` |
| `data/s3a-verification/grid.duckdb` | `FFFC2AEEF64CE06DD09F5EA2E4739A1BB7FDEFD6B28DFF1E66779EC8F4F091B1` |
| Original scratch `history-complete/grid.duckdb` | `CCAE32773857298E6CD0E61312C467C9F32748FEA62CE89B46CB125003CE367C` |

The probe itself verifies before and after hashes. The lead independently checked current hashes against the saved results. No reset, discard, commit, push, dependency installation, source database write, or other-session control occurred. A long-running read command from this session was stopped. The definition TOML was not edited.

Structural exploration used the installed `codebase-memory` skill and `index_status`, `search_graph`, `trace_path`, `get_code_snippet`, and `check_index_coverage`. Coverage reported changed metadata and partial SQL parsing. Relevant Python and SQL files were read directly, including reported SQL ranges. Graph results alone did not determine the diagnosis.

**Both mirrored read-only gpt-6.1-terra MAX reports are now used**, as detailed and cited in the worker-review section. The earlier claim that no mirrors were available was inaccurate and has been removed. Original cache access failures remain preserved in [worker-rulings-access.txt](evidence-2026-10-31-sol/worker-rulings-access.txt) and [worker-data-access.txt](evidence-2026-10-31-sol/worker-data-access.txt), but do not describe the availability of the mirrored files. The conditional worker replay remains separate from the official raw-database probe.

The current worker-review source passed the requested targeted tests, full suite, and official retrospective probe with recorded matching hashes. No execution handoff remains outstanding for this revision. Calendar and numerical definitions require Darren's ruling through Alder. Immutable availability provenance and real NWS feature/annotation integration remain acceptance blockers. Prospective claims remain disabled. S3c is not declared accepted or published.

---

**Superseded in part, Nov 5, 2026 (appended; the text above is a dated record and is not rewritten).** Line 28 above ("`PLAN.md` already require issuance before the target local date starts ... `issue_time_not_before_target_date`") states the next-day boundary that **Darren's ruling, Nov 5, 2026: SAME-DAY — the 07:00 job forecasts today's peak; freshness judged on completed history through target − 2** replaced. The model no longer rejects issuance on the target date; it rejects issuance after the 07:00 America/New_York cutoff on the target day (`issue_time_after_target_day_cutoff`) or after the start of the forecast's peak hour (`issue_time_after_peak`). `issue_time_not_before_target_date` is retired. The DST handling noted there is kept, and "This is not the deferred 7 AM rule" no longer holds: the 07:00 cutoff is now the rule. Record: `docs/s4/W2-SAMEDAY-RUN-2026-11-05.md`.
