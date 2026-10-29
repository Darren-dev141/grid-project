# Grid Project

Local energy-data pipeline for a future BGE charging-window tool. The plan of
record is in [PLAN.md](PLAN.md). Layer 1 is in progress. A real two-day EIA PJM
generation sample has been ingested and validated using EIA's public demonstration
key. PJM prices and the complete dashboard remain unverified; no résumé milestone
is earned yet. See [live EIA evidence](docs/evidence/eia-live-2026-10-28.json).

## Run locally

```powershell
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.venv/Scripts/python.exe -m pytest -q
```

Replay a saved provider JSON response:

```powershell
.venv/Scripts/grid.exe eia electricity/rto/fuel-type-data response.json
```

The command preserves the exact response under `data/raw` and indexes records
in `data/grid.duckdb`. Identical replay adds no rows. This command does not fetch
remote data. Do not supply files containing credentials.

See [architecture](docs/layer-1.md) and [API registration](docs/api-setup.md).
The test suite also runs the real dbt DAG against isolated synthetic warehouses,
including revision selection, missing mix, negative prices, and failing quality
checks. Test data is not a current grid observation.

## Build dbt views

After replaying provider responses, set the absolute warehouse path and pass the
BGE node ID verified from PJM metadata. Replace the placeholder before running:

```powershell
$env:GRID_DATABASE = (Resolve-Path data/grid.duckdb).Path
.venv/Scripts/dbt.exe build --project-dir dbt --profiles-dir dbt --vars '{bge_pnode_id: VERIFIED_NODE_ID}'
```

Use dataset names `rt_hrl_lmps` for PJM and
`electricity/rto/fuel-type-data` for EIA when replaying. Other dataset names remain
in raw storage and are excluded from these models. No default BGE ID is supplied.
dbt telemetry is disabled in project flags.

Next: live API contracts and paginated fetching, incremental checkpoints,
live dbt validation and freshness checks, then Power BI exports and dashboard
verification. See [progress evidence](docs/progress.md).

## Fetch a bounded interval

`grid-fetch` uses `EIA_API_KEY` or `PJM_API_KEY` from the local environment. Keys
are never command arguments. Register free keys for regular operation; EIA's
generation endpoint has passed a bounded live sample using its public DEMO_KEY.
PJM endpoint compatibility remains unverified. Reinstall the editable package after updating it.

```powershell
.venv/Scripts/grid-fetch.exe eia --start 2026-10-01T00:00Z --end 2026-10-02T00:00Z
.venv/Scripts/grid-fetch.exe pjm --start 2026-10-01T00:00Z --end 2026-10-02T00:00Z --bge-node VERIFIED_NODE_ID
```

Intervals are UTC, start-inclusive/end-exclusive, at most 31 days. The same
warehouse stores separate stream checkpoints for EIA PJM generation and each PJM
price node. Extend `--end` to load newer data; the default 48-hour overlap refetches
recent observations. Advance `--start` as needed to keep each request within 31
days, but never beyond the previous completed end. It is the lower bound on
overlap, so retaining it through the overlap window allows correction fetching.
Already completed intervals are a no-op. Historical backfills use another `--root`
until a dedicated backfill/merge workflow is implemented.

Run one ingestion job at a time, then `dbt build`. A checkpoint advances only
after every page is validated and indexed. Empty datasets, changed totals,
repeated pages, out-of-scope rows and failed requests leave it unchanged. HTTP
429/server failures and transport failures retry at most four total attempts.
No-data failures are conservative; they require investigation rather than quietly
skipping an interval. A completed checkpoint proves a page scan, not hourly data
coverage or freshness. Do not publish serving data after a failed ingestion/build.

Fetched batches remain hidden from cleaned models until a successful load commits
their visibility and observation time with the checkpoint. Successful refetches
can restore an earlier provider value without inserting duplicate raw records.
On older warehouses, replay any saved response once before rebuilding dbt to
apply the additive batch-metadata migration; this inserts no duplicate records.

## Publish a Power BI snapshot

```powershell
.venv/Scripts/grid-publish.exe --bge-node VERIFIED_NODE_ID --data-kind public_unverified
```

Use `--data-kind synthetic` for fixtures. The command builds and tests dbt against
an isolated database copy, writes CSV and verification metadata to a unique
snapshot folder, then atomically updates `data/powerbi/current.json`. Failed
validation leaves the previous publication intact. Publications are historical
analysis exports, not charging recommendations. Serialize ingestion/publication.

Before serving a publication as current, check it:

```powershell
.venv/Scripts/grid-freshness.exe --max-lag-hours 36
```

It prints per-source status (`fresh`, `stale`, `missing`, `future`) and exits 1
unless both price and complete fuel mix are fresh. The 36-hour default is
provisional; EIA fuel mix lagged about 22 hours in one live sample.

[Power BI setup](powerbi/README.md) includes an import query, DAX measures and
acceptance criteria. Desktop import and report visual verification remain pending.

[LocalJev setup status](docs/localjev.md) tracks the local candidate for the
requested Jev workflow.

## Validate generation independently

EIA generation can be validated without a PJM key or a guessed BGE node:

```powershell
$env:GRID_DATABASE = (Resolve-Path data/live-eia-demo/grid.duckdb).Path
.venv/Scripts/dbt.exe build --project-dir dbt --profiles-dir dbt --select eia_pjm_hourly_generation
```

The live sample used `[2026-10-26T00:00Z, 2026-10-28T00:00Z)` and `--page-size 100`
for the overlapping second load. Source bytes and the warehouse are in ignored
`data/live-eia-demo`; tracked evidence contains hashes, counts and dbt invocation
identity. EIA's public demo access is for bounded evaluation; obtain a free key
for scheduled operation. The combined Power BI publisher still requires prices.
