# Grid Project

Local energy-data pipeline for a future BGE charging-window tool. The plan of
record is in [PLAN.md](PLAN.md). Layer 1 is in progress; no live energy data has
been ingested and no résumé milestone is earned yet.

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
Next: live API contracts and paginated fetching, incremental checkpoints, dbt
models and data-quality checks, then Power BI exports and dashboard verification.
