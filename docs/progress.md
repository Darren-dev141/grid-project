# Progress — October 28, 2026

Implemented local Python package and replay CLI, immutable raw response landing,
transactional DuckDB raw indexing, duplicate replay detection and revision retention.
Documented architecture, proposed cleaned/serving tables and API setup.

Verified with Python 3.14.7 and DuckDB 1.5.6:
` .venv/Scripts/python.exe -m pytest -q ` — **9 passed**.
Tests use synthetic data only; no production API compatibility claim.

Existing PLAN.md edits were preserved. No paid infrastructure provisioned.
API registration remains pending. EIA's registration form is reachable.
Jev's shell wrapper did not run properly under PowerShell; invoking its Python
module directly reported `Jev unavailable (no_key)`. No browser form was submitted.

Next work: restore Jev access for the requested browser workflow, complete free
registrations, verify live API contracts, implement fetching and incremental
checkpoints, then dbt models/tests and Power BI evidence. Layer 1 remains incomplete.

## dbt transformation milestone

Added a local dbt-duckdb project with cleaned BGE price and PJM regional generation
views and a joined serving view. BGE node selection is explicit; no production ID
has been selected. Added null, uniqueness, accepted-unit, finite-number, hour
alignment and renewable-share range tests.

Integration tests run real `dbt build` subprocesses in temporary warehouses:
revised fuel generation and price replace prior rows, unrelated nodes are excluded,
negative prices survive, missing/negative generation suppresses renewable share,
zero denominators stay null, nuclear stays out of the renewable numerator, and
price-only/generation-only hours survive. A separate deliberately invalid dataset
proves unit, null and non-finite checks fail. Initial run: **2 integration tests
passed**, including two successful builds and one expected failing quality build.

These are synthetic contract tests, not evidence of live provider compatibility,
freshness, complete incremental loading or a completed Tier 2 milestone. Next:
fetching/checkpoints, provider verification, live dbt validation and Power BI.

Final verification for this milestone: `.venv/Scripts/python.exe -m pytest -q`
reported **11 passed in 13.60s**. `git diff --check` passed. No API registration,
paid service provisioning or live data access was performed in this milestone.

## Incremental fetch milestone

Implemented environment-key API clients for EIA and PJM, UTC interval validation,
bounded pagination, retries, raw response landing and per-stream DuckDB
checkpoints. All pages must validate before indexing starts; failures do not
advance checkpoints. Repeated pages, changing totals, empty responses, wrong
geography, out-of-range timestamps, redirects and echoed keys are rejected.

Added 21 mocked HTTP tests covering both providers, offsets, inclusive/exclusive
boundary conversion, failed-page recovery, bounded retries, revision overlap and
safe errors. Tests exposed a four-hour local-time shift in checkpoint reads;
setting the DuckDB session to UTC fixed it. No authenticated requests were made.
Endpoint shapes and query semantics remain provisional until live verification.

Final verification: full suite **32 passed in 15.08s**; installed `grid-fetch
--help` and `git diff --check` passed. No paid infrastructure was provisioned.

## Power BI publication milestone

Implemented `grid-publish`: logical DuckDB snapshot, real dbt build/tests on that
copy, immutable CSV/manifest folders and atomic current-pointer publication.
Missing price or generation observations prevent publication. CSVs preserve nulls,
UTC keys and New York local hours/offsets, and label synthetic versus unverified
public data. Added Power Query import, DAX measures and report acceptance notes.
No PBIX or visual report verification is claimed.

Two export tests passed, proving DST fall-back keeps both 1 AM observations,
negative prices and null shares survive, source DB views remain untouched, and a
failed quality build cannot replace the last published CSV or pointer. An initial
Windows file-lock failure was fixed by using DuckDB logical database copy.

Investigated the user's LocalJev link: upstream 19 tests and TypeScript checks
passed; local Ollama is available. Bridge startup was rejected by automatic
approval review ("blocked by policy"), so inference is not verified. See
`docs/localjev.md` and the user-run foreground script. No paid services added.

Full verification after publication changes: **34 passed in 24.95s**. The installed
`grid-publish --help`, PowerShell startup-script syntax and `git diff --check`
passed. Power Query/DAX execution in Power BI Desktop is still unverified.

## First live EIA verification — October 28, 2026

EIA metadata returned HTTP 200 using its public DEMO_KEY and confirmed hourly UTC
frequency, the respondent/fueltype facets and megawatthours. No personal key was
registered. Ingested October 26, then extended through October 27 with a 48-hour
overlap and 100-row pages. The second request traversed four pages.

Evidence: five immutable raw responses, 576 raw indexed records including the
overlap, and 384 cleaned records covering 48 hours × eight fuel codes. Verified
all raw SHA-256 digests and exact replay inserting zero rows. The checkpoint ends
at October 28 00:00 UTC. Live dbt generation build and all nine associated tests
pass. Detailed counts/hashes are in `evidence/eia-live-2026-10-28.json`.

Live verification exposed generation-only selection being coupled to price-node
configuration and tests. Price-node validation now runs at execution rather than
parse time; finite-value and hour-alignment tests are separate per source. A new
integration regression proves generation-only builds without a BGE ID. Moved dbt
telemetry configuration to current project flags to remove a deprecation warning.

One full-suite attempt hit an upstream dbt/Python 3.14 Windows thread-pool shutdown
error (`concurrent send_bytes() calls are not supported`), preventing its result
artifact from being written. This is distinct from a data-quality failure; the
test now reports the underlying subprocess output if the artifact is absent.
No runtime fix for that intermittent shutdown error is claimed.

Final rerun: **35 passed in 28.97s**. `git diff --check` and the installed fetch
command's `--page-size` help passed. Live generation dbt: **1 model + 9 tests passed**.

Still missing: personal API registrations, PJM live price ingestion, verified BGE
node, operational freshness/revision coverage, combined live serving validation,
Power BI report, web MVP, alerts and real users. The full goal remains active.

## Fetch visibility and correction handling

PJM website/API connection attempts failed in this environment; LocalJev's loopback
readiness endpoint also refused the connection. No new bridge launch was attempted.

Fixed two local correctness gaps: fetched pages are staged until the complete run
succeeds, and successful refetches record observation time even for previously
seen bytes. Batch visibility, observation timestamps and checkpoints now commit
together. Cleaned models ignore staged batches and use latest successful fetch
time for revision ordering; offline replays do not promote historical bytes.

Added regressions for interrupted second-page indexing/recovery and an upstream
value changing from 10 to 20 and back to 10. The latter also proves an uncommitted
999-value batch cannot leak into the cleaned model.

Migrated the stored live EIA sample without new network calls: all five raw hashes
remain valid, all 576 raw rows remain, and replay inserts zero rows. Upgrading
legacy batches preserves their first-load ordering; no historical observation
timestamps are invented.

Verification: **37 tests passed in 34.65s**; stored live EIA generation model plus
all nine tests passed again, with 384 cleaned rows unchanged. `git diff --check`
passed. No paid services provisioned; full project completion is still unproven.

## Freshness gate — October 29, 2026

Run moved from Codex to Claude Code after a provider usage limit. Built test-first:
publish manifests now record the last hour with a price and the last hour with a
complete fuel mix. `grid-freshness` reads the current publication and reports each
source as fresh, stale, missing or future (an hour ending after now, the signature
of a timezone bug). It exits 1 unless both sources are fresh. Six new tests, each
watched failing first; the stale test was also checked against a broken comparison.

Live measurement: EIA's newest PJM fuel-mix hour was 03:00 UTC October 28 at 01:47
UTC October 29, about 22 hours behind. One sample; lag spread unknown.

PJM diagnosis: the API answers HTTP 401 without a key when reached by IP. ProtonVPN's
resolver times out on `*.pjm.com`. Jev remains unavailable: its wrapper calls the
Windows Store `python` stub and LocalJev is not listening on port 18080.

Verification: full suite **43 passed in 42.04s**; `git diff --check` passed; the
installed `grid-freshness` exits 1 with a clear message when nothing is published.
Still missing: PJM key and DNS fix, live price ingestion, verified BGE node, Power BI
report, web MVP, alerts and real users.

## S1 and S2 — October 29, 2026

Plan v2 adopted: grid-stress brief, EIA-930 only for grid data, direct PJM retired.
Luna (S1) and Astra (S2) Codex workers in T3 all failed on the ChatGPT usage limit.
S1 was finished in this thread from the workers' partial worktrees: their tests
were applied first and failed (31 RED) against the old code, then the code made
them pass. S2 was completed by Codex Astra through the Codex CLI (commit 2601085 on
branch t3/nws-weather-ingestion) and reviewed here before being applied.

S1 delivered: EIA dataset registry (`fuel-mix`, `pjm-demand`, `bge-demand`), direct
PJM fetch removed, resumable `grid-backfill`, cleaned `eia_pjm_hourly_demand` and
`eia_bge_hourly_demand` (BGE labeled trailing, never joined to PJM-wide data).

Live S1 run: PJM demand backfill on DEMO_KEY loaded 3 of 16 windows, 12,960 rows
(2019-01-01 to 2020-06-24), zero missing hour rows, all raw hashes verified, then hit
the DEMO_KEY quota (limit 10, Retry-After 73,591 s). Real history exposed 23 null
hours around DST changes and two impossible spikes (417,669 and 215,682 MWh). The
build initially failed; cleaned models now flag `quality` instead of failing or
hiding (test-first). Live dbt: PASS=23 WARN=1 ERROR=0. Evidence:
`evidence/eia-demand-live-2026-10-29.json`.

S2 delivered (Codex): `grid-weather`, NWS raw landing, forecast periods/daily/latest
models keeping every issuance, heat/cold alerts. Live: gridpoint LWX/100,98, 7 days
of highs and lows, update-to-fetch lag 12,885 s, no active alerts (alert names not
verified live). Codex reported that a few supplementary checks lacked separate RED runs.

Verification: full suite **82 passed in 135.88s**, one retried dbt `send_bytes()`
flake reported as a warning; `git diff --check` clean. Nothing committed by Claude.

S1 finished on the personal EIA key (entered through T3's private secret card; found
in 0 files afterwards). The backfill resumed from its checkpoint and completed all
16 windows: 68,594 PJM demand hours, 2019-01-01 to 2026-10-29 02:00 UTC, equal to
EIA's own row total; all 16 raw hashes verified. First live `bge-demand` fetch:
168 hours, all ok. One hour is absent upstream (2023-11-06 05:00 UTC).

Full history exposed more errors: 116 null hours, values up to 2,147,480,000 MWh
(2021-10-19) and one-hour spikes under the 200,000 cap (192,229 MWh between 127,489
and 136,631). Measured: 99.99% of hours sit within 3.3% of the higher neighbour; the
errors sit 15.6-42.7% above, or 41% below. Added test-first: more than 10% above
both neighbours or 15% below both is implausible (needs both neighbours; a test
caught DuckDB `greatest()` ignoring NULLs). Live result: 68,463 ok, 116 missing,
15 implausible; highest ok hour 162,648 MWh (2026-07-02). dbt PASS=23 WARN=1 ERROR=0.

Independent review by a GPT-6 Luna subagent on high effort (read-only, against HEAD
1169c62): one medium finding, proven in a scratch run. A non-null non-numeric value
was cast to NULL and labeled `missing`, hiding a provider format change. Fixed
test-first (RED: build exited 0 for both series): such values are now `invalid` and
`demand_unparseable_value` fails the build. Everything else it checked was clean:
routes, stream names, backfill windows and resume, checkpoints, revision selection,
thresholds, BGE separation, and the live counts in the evidence file.

Final verification: **85 passed in 162.07s** (one retried dbt `send_bytes()` flake
reported as a warning); live demand build PASS=24 WARN=1 ERROR=0, 0 invalid rows;
`git diff --check` clean.
