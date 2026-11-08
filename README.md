# Beat the Grid

A daily PJM-wide grid stress brief for Maryland. The live page is
[https://beat-the-grid.vercel.app](https://beat-the-grid.vercel.app).

The page states one call for a local day: forecast peak demand, the hour that
peak falls in, and a stress level (`calm`, `watch`, `strained`, or `severe`).
When load or weather is too old to support a call, the page names that reason
and prints the real freshness dates from the warehouse.

## Architecture

EIA-930, NCEI, and NWS land as raw JSON in a DuckDB file. dbt builds the
cleaned views and `marts.mart_day_history`. `stress-index-v1` forecasts from
first-recorded history. `python -m grid_pipeline.brief` writes `site/index.html`
and `site/comment.md`. Vercel serves the `site/` directory (`vercel.json`
sets `outputDirectory` to `site`, with no build step). A push to `main`
publishes the page. `.github/workflows/ci.yml` runs the tests.

| Source | What it supplies | Access |
| --- | --- | --- |
| EIA-930 | PJM hourly demand, BGE zone demand, PJM generation by fuel | `EIA_API_KEY` |
| NCEI | BWI daily high and low (`USW00093721`), the temperature history | keyless |
| NWS | BWI forecast for the target day's high and morning low | keyless; `NWS_USER_AGENT` required |

Demand on the brief is EIA's public series (`electricity/rto/region-data`),
fetched as `pjm-demand`. The stress definition is
`ledger/definitions/stress-index-v1.toml`: three years of history, a seasonal
window, weather hinges, and analog days. Load counts as fresh only when the
latest completed peak, the target date minus two days, is in that history.
The design write-up is [docs/architecture-s3-s7.md](docs/architecture-s3-s7.md).

`dbt/models/cleaned/pjm_bge_hourly_price.sql` still reads PJM Data Miner
real-time LMP rows (`rt_hrl_lmps`) for a verified `bge_pnode_id`. The public
brief build excludes that model, and the page shows demand in MW. The scheduled
Supabase target is in `dbt/profiles.yml` and `.github/workflows/daily.yml`.

## Verified receipts

Recorded on the 2019–2026 EIA demand history:

- 68,594 hours checked, with 116 missing and 15 implausible.
- The peak-load forecaster's error on a frozen 665-day test: 4,982 MW, versus 5,909 MW for repeating yesterday and 10,626 MW for the same day last week.

## Setup

Python 3.11 or newer. Put keys in the environment. A free EIA key is registered
at [eia.gov/opendata](https://www.eia.gov/opendata/register.php). `DEMO_KEY`
is public and rate-limited.

### bash

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export EIA_API_KEY='your-eia-key'
export NWS_USER_AGENT='grid-project/0.1 (github.com/Darren-dev141/grid-project)'
export DBT_SEND_ANONYMOUS_USAGE_STATS=false

python -m pytest -q

grid-backfill pjm-demand --start 2023-01-01T00:00Z --end 2026-11-09T00:00Z --window-days 180 --root data
grid-temps --root data --start 2023-01-01 --end 2026-11-09
grid-weather-bwi --root data

export GRID_DATABASE="$PWD/data/grid.duckdb"
dbt build --project-dir dbt --profiles-dir dbt --exclude 'pjm_bge_hourly_price+'
python -m grid_pipeline.brief --database "$GRID_DATABASE" --ledger ledger --out site
```

`grid-fetch` loads one dataset for at most 31 days (`pjm-demand`, `bge-demand`,
or `fuel-mix`). `grid-backfill` repeats that in windows. Intervals are UTC,
inclusive of the start hour and exclusive of the end hour.

### PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e '.[dev]'
$env:EIA_API_KEY = 'your-eia-key'
$env:NWS_USER_AGENT = 'grid-project/0.1 (github.com/Darren-dev141/grid-project)'
$env:DBT_SEND_ANONYMOUS_USAGE_STATS = 'false'

python -m pytest -q

grid-backfill pjm-demand --start 2023-01-01T00:00Z --end 2026-11-09T00:00Z --window-days 180 --root data
grid-temps --root data --start 2023-01-01 --end 2026-11-09
grid-weather-bwi --root data

$env:GRID_DATABASE = (Resolve-Path data/grid.duckdb).Path
dbt build --project-dir dbt --profiles-dir dbt --exclude 'pjm_bge_hourly_price+'
python -m grid_pipeline.brief --database $env:GRID_DATABASE --ledger ledger --out site
```

`--target-date YYYY-MM-DD` overrides the brief's default, which is today in
America/New_York. Raw files and the DuckDB warehouse stay under `data/` and
are gitignored. The committed page is `site/`.
