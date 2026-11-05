# S3c diagnosis, 2026-10-31

The corrected implementation passed the full suite: **160 passed, two warnings in 232.36 seconds**. The real `grid_pipeline.stress.forecast` probe completed the original **2,833 complete dates**: **1,820 classified**, **357 UNSCORED for insufficient fitting history**, and **656 calendar DefinitionGap refusals**. The real complete date 2025-07-01 returned `SCORED / calm`, not `DefinitionGap`.

This verifies the calculation path and retrospective eligibility. It does not establish historical issue-time availability or forecast performance. **S3c acceptance remains blocked by unresolved calendar definitions.** The supplied definition-change stop rule was preserved. Neither the 7 AM ET issuance cutoff nor D-2 latest completed peak was implemented.

## Evidence and commands

The final run used the existing project venv, Python 3.14.7 and pytest 9.2.0. Hermes executed the prepared runner outside the restricted Codex sandbox. The lead inspected the raw outputs and independently checked all per-date receipt accounting with PowerShell.

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
================= 160 passed, 2 warnings in 232.36s (0:03:52) =================
```

Both warnings were `RuntimeWarning: dbt concurrent send_bytes() failure: retrying`, in `test_nws_dbt_rejects_invalid_forecast_fields[temperature-NaN]` and `[isDaytime-None]`. The retries succeeded. No tests were skipped, failed, or reduced in scope. This is a current execution, not the earlier 132-test result.

The external handoff command was:

```powershell
powershell -NoProfile -File C:\Users\ajbig\Documents\grid-project\scripts\verify_s3c_sol.ps1 -EvidenceDirectory docs/s3c/evidence-2026-10-31-sol/external-run-fixed
```

The runner recorded and executed these commands from `C:/Users/ajbig/Documents/grid-project`, with native stdout and stderr saved separately:

```powershell
& 'C:\Users\ajbig\Documents\grid-project\.venv\Scripts\python.exe' -m pytest -ra tests/test_stress_inputs.py tests/test_s3c_diagnosis.py --basetemp 'C:\Users\ajbig\Documents\grid-project\docs\s3c\evidence-2026-10-31-sol\external-run-fixed/targeted-temp'
& 'C:\Users\ajbig\Documents\grid-project\.venv\Scripts\python.exe' -m pytest -ra --basetemp 'C:\Users\ajbig\Documents\grid-project\docs\s3c\evidence-2026-10-31-sol\external-run-fixed/pytest-temp'
& 'C:\Users\ajbig\Documents\grid-project\.venv\Scripts\python.exe' scripts/diagnose_s3c.py 'C:/Users/ajbig/AppData/Local/Temp/grid-s3c-20261030/history-complete/grid.duckdb' --output 'C:\Users\ajbig\Documents\grid-project\docs\s3c\evidence-2026-10-31-sol\external-run-fixed/probe.json'
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
| [src/grid_pipeline/stress_inputs.py](../../src/grid_pipeline/stress_inputs.py) | Parenthesize the three failing raw JSON filters. |
| [scripts/diagnose_s3c.py](../../scripts/diagnose_s3c.py) | Preserve the original cohort; call the real model; record sequential gates, per-date receipts, ordered source audits, and hashes; remove hypothetical historical issue times; require a real complete-date classification; serialize infinite condition diagnostics as strings in strict JSON. |
| [scripts/verify_s3c_sol.ps1](../../scripts/verify_s3c_sol.ps1) | New external verification runner with targeted tests, full suite, real probe, raw logs, and source hashes. |
| [tests/test_stress_inputs.py](../../tests/test_stress_inputs.py) | Three synthetic alert-interval overlap cases spanning midnight, DST, and a one-second interval. |
| [tests/test_s3c_diagnosis.py](../../tests/test_s3c_diagnosis.py) | Two synthetic checks of local-date availability bounds and strict JSON diagnostics. |
| This report and its evidence directory | Preserve the starting state, failures, completed results, source fingerprints, and independent checks. |

The production algorithm in `stress.py`, the public model types, and the TOML definition were preserved. No alternate forecast implementation or substitute dataset supplied the measured results. Synthetic tests and the synthetic alert-invariance annotation are explicitly labeled.

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

**Prospective operation.** The current model requires an actual timezone-aware issue time, actual target-weather availability, and availability of both historical sources at that time. The probe does not invent such evidence or create backdated receipts. Prospective results are `NOT RUN`, rather than treating a hypothetical schedule as an actual issuance. The 7 AM ET and D-2 decisions remain next-step context.

The loader selects the earliest `raw.batches.loaded_at` for each retained PJM hour and BWI date from committed batches, then reuses the existing dbt cleaning and daily aggregation. Missing or invalid first temperatures stay missing even when a later revision supplies a value. `loaded_at` is local archive evidence, not the provider's original publication time or proof that no earlier unretained revision existed. `observed_at` and settled cleaned views do not fill that provenance gap.

The actual retained load timestamps span **2026-10-29 03:31:12.786993 through 10:55:55.803599 UTC**. Retained temperature timestamps span **2026-10-29 13:09:13.056009 through 13:09:29.233985 UTC**. Both archives were recorded after the last probe target, 2026-10-24. There are no missing `loaded_at` values in the committed source batches inspected.

The necessary-condition audit considered **4,011,528 prior complete date pairs** across all original targets. **Zero pairs** had both sources recorded before the target local date ended. **Zero targets** had even one pair passing that loose bound. The exclusive end of a target local date is an audit bound, not an issuance cutoff or a manufactured issue timestamp. Passing the bound would still not prove availability at a real issuance. Failing it shows that this retained archive cannot establish an earlier as-of forecast.

The first-snapshot reconstruction contains 2,859 dates and 2,836 demand-complete dates. Its peak-MW and high/low values show no differences from the supplied settled mart in the fields compared. That does not prove absence of revisions before this archive existed. Settled actuals remain distinct from first-recorded fitting inputs.

The load quality model uses neighboring hours. The loader conservatively includes those neighbors' recorded times in availability. Retrospective mode does not thereby establish issue-time causality: the last interval of a prior date can depend on the next date's first interval for its quality flag. The report does not claim a causal historical publication pipeline.

## The five suspects, in the required order

| Order | Verdict | Evidence |
| --- | --- | --- |
| (a) First-recorded and known-at availability | **Confirmed historical provenance blocker.** It does not force the labeled retrospective reconstruction to reject every date. | Earliest retained load and temperature times are after all probe targets. Zero of 4,011,528 prior date pairs pass even the loose target-date-end availability bound. No issue times were invented. |
| (b) BGE study geography versus deep PJM history | **BGE is too shallow for a multiyear study. The current plan deliberately requires PJM-wide calls with Maryland weather.** A BGE-specific claim would require a new scope decision and deeper data. | Fresh raw inventory has 68,594 distinct PJM demand hours, 2019-01-01 00:00 through 2026-10-29 02:00 UTC, versus only 168 BGE hours, 2026-10-20 00:00 through 2026-10-26 23:00 UTC. `PLAN.md` retires the BGE charging advisor. The loader and mart select PJM demand with BWI weather. BGE was not blended into the model. |
| (c) Alerts and receipts dependency | **Eliminated as a numeric forecast blocker.** Missing historical issuances still block prospective validation. | The ledger inventory contains no forecast receipts. The real function still classifies. It constructs its own return receipt and only annotates supplied alerts. The real-date synthetic alert check leaves every numeric claim unchanged. |
| (d) Analog pool collapse | **Eliminated as a universal explanation.** The observed early-history refusal is the fitting-stratum floor. | All 1,820 eligible targets pass the analog floor. Their candidate pools range from 28 through 108 days, and all select ten. The 357 fit rejections are 278 dates in 2019 and 79 weekend dates in 2020. No target is rejected for insufficient analogs. |
| (e) Date, completeness, and DST | **Calendar ambiguity remains a real definition blocker. DST does not cause universal refusal.** | There are 656 calendar refusals. Among 15 DST dates, nine are demand-complete and six incomplete. Complete 25-hour dates 2021-11-07, 2024-11-03, and 2025-11-02 classify as calm. The three complete dates without temperatures lie outside the original target cohort. |

The ordered evidence is also stored in `probe.json` under `suspects_in_order`. Source inventory confirms 16 committed PJM batches, one BGE batch, and eight NCEI batches with 2,854 daily temperature rows. The bounded ledger inventory is not proof about receipts that might exist outside the supplied repository.

## Original cohort and measured outcomes

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

## Sequential gates and exclusions

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

The existing source implements linear/type-7 `np.quantile`, z-scored Euclidean analog distance, ten-nearest selection, newest distance ties, earlier hour-mode ties, separate 20-day threshold and fit floors, a five-analog floor, missing-temperature exclusion, first-recorded prior-date fitting, and annotation-only alerts. All 23 frozen-ruling tests passed. The first-recorded raw-to-daily regression and real integration passed as well.

**No definition changes were made. These questions remain explicit:**

1. **Calendar window.** How exactly does the +/-21-day window map across New Year and between leap and non-leap years? Which dates are included when the window contains February 28 or February 29? Existing docs list this as unresolved. The conservative exception remains and accounts for 656 targets. Its exact runtime text is:

```text
calendar boundary and leap-day selection is unspecified
```

2. **Numerical convention in the interrupted implementation.** What defines near-zero hinge variance, and does the 1e10 condition threshold apply to the design matrix X or the normal-equation matrix X-transpose-X? The inherited code uses X and `std(column) <= max(1, max(abs(column))) / 1e10`, with a single-hinge condition check. No supplied document freezes that exact tolerance. I preserved and disclosed it rather than choosing another meaning. No real target used that fallback in this probe.
3. **NWS endpoint precedence for annotations.** Which start and end fields apply when `effective`, `onset`, `expires`, and `ends` differ? The any-overlap ruling settles local-date mapping once explicit endpoints exist. The inherited helper takes an explicit half-open interval and annotates all overlapped New York dates, including DST. It does not choose NWS endpoint precedence. This question blocks annotation validation only, never stress level.

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

The initial state had eight modified tracked files and many untracked files from the interrupted session. See [initial-git-status.txt](evidence-2026-10-31-sol/initial-git-status.txt) and the initial snapshots. All **53 pre-existing unrelated files** checked by SHA-256 remained unchanged. See [worktree-preservation-check.json](evidence-2026-10-31-sol/worktree-preservation-check.json).

All three databases retained their original hashes before and after verification:

| Database | SHA-256 |
| --- | --- |
| `data/s1-live/grid.duckdb` | `0AE80A9A1939B78FFCF471F9998FBFC9A51749B039713DBC2ABFF7022D8337C3` |
| `data/s3a-verification/grid.duckdb` | `FFFC2AEEF64CE06DD09F5EA2E4739A1BB7FDEFD6B28DFF1E66779EC8F4F091B1` |
| Original scratch `history-complete/grid.duckdb` | `CCAE32773857298E6CD0E61312C467C9F32748FEA62CE89B46CB125003CE367C` |

The probe itself verifies before and after hashes. The lead independently checked current hashes against the saved results. No reset, discard, commit, push, dependency installation, source database write, or other-session control occurred. A long-running read command from this session was stopped. The definition TOML was not edited.

Structural exploration used the installed `codebase-memory` skill and `index_status`, `search_graph`, `trace_path`, `get_code_snippet`, and `check_index_coverage`. Coverage reported changed metadata and partial SQL parsing. Relevant Python and SQL files were read directly, including reported SQL ranges. Graph results alone did not determine the diagnosis.

**Neither read-only Terra worker report was used.** Both supplied Hermes cache paths returned `Access is denied`, followed by `Cannot find path ... because it does not exist`. The access failure prevents determining whether the workers finished. Exact outputs are in [worker-rulings-access.txt](evidence-2026-10-31-sol/worker-rulings-access.txt) and [worker-data-access.txt](evidence-2026-10-31-sol/worker-data-access.txt). Hermes was asked to mirror completed reports into the readable evidence directory; none was available when this report was finalized. The findings above come from inspected source, actual test executions, the real model probe, and independent receipt checks.

The calculation path, full suite, real integration, and original-cohort probe are verified within the disclosed retrospective mode. Calendar definitions still require Darren's ruling through Alder, and historical issuance evidence remains unavailable. S3c is not declared accepted or published.
