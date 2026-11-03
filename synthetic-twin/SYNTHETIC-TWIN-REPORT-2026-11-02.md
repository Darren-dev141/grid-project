Restated problem: the grid pipeline (forecaster, stress index, S3c issuance) is validated only against real data with messy provenance, so its skill is partly anecdote; this twin generates a synthetic feed whose ground truth is known by construction, runs the unmodified pipeline against it, and scores the pipeline against the truth manifest.

# Synthetic Twin Report — 2026-11-02

## Generator design + parameters
- Seed: 20261102 (recorded in truth_manifest.json).
- Span: 2025-01-01 .. 2026-10-31 (daily, hourly UTC, 24 h/day; DST handled via America/New_York).
- Series: base load with daily+weekly seasonality (95 GW baseline profile), weather-driven component (synthetic TMAX/TMIN with annual cycle), interchange-like series (interchange_series.csv, not consumed by pipeline).
- Feed shape: EIA-930 style — `electricity/rto/region-data` PJM hourly demand rows and `daily-summaries` NCEI station USW00093721 rows, ingested into DuckDB raw.batches/raw.records.
- Injected events: 2 heat waves (Sep 15 2026 12:00 ET 48 h +18% load; Oct 5 2026 10:00 ET 72 h +15% load), plant outage Sep 28 2026 06:00 ET 12 h 1800 MW, stale gap Oct 20-22 2026 (feed frozen 7 days).
- Parameters: base_load_mw=95000, weather_sensitivity=0.004, noise_std_mw=1200, temp_noise_std_f=3.0.

## Manifest summary
- Evaluation window: 2026-09-01 .. 2026-10-30 (60 days).
- Heat-wave stress days: 7 (Sep 15-16, Oct 5-7 plus partials).
- Stale gap: 2026-10-20 .. 2026-10-22.
- Files: data/load.duckdb, data/temperature.duckdb, feed_load.json, feed_temperature.json, interchange_series.csv, truth_manifest.json.

## Pre-committed readouts
1. Forecaster hits/misses/false alarms vs manifest.
2. Stress-index in-window vs out-of-window separation.
3. Issuance stale-day = fail-closed (yes/no).
4. Issuance clean-day = normal (yes/no).

## Results
### Forecaster (60 target days)
- Hits (elevated inside heat-wave windows): 6
- Misses (not elevated inside heat-wave windows): 1
- False alarms (elevated outside heat-wave windows): 19
- True negatives: 34
- No-calls due to insufficient fit history: 16 (all outside windows)

### Stress index distributions
- In-window (n=7): calm 1, watch 4, strained 2; predicted peak mean 97,405 MW; actual peak mean 110,686 MW.
- Out-of-window (n=53): calm 18, watch 18, strained 1, UNSCORED:insufficient_fit_history 16; predicted peak mean 97,273 MW; actual peak mean 93,947 MW.

### Issuance
- Stale-gap day 2026-10-21: reason = stale_load -> fail-closed YES.
- Clean day 2026-10-25: reason = unverified_issue_time_availability -> normal path YES (not a stale-data reason).

## Failure notes
- Forecaster shows poor separation: 19 false alarms outside injected stress windows, indicating the v1 analog/heat-hinge model over-calls watch/strained on routine days. Only 1 miss inside windows.
- 16 target days (all outside windows) return UNSCORED:insufficient_fit_history due to sparse 2-year history; this depresses denominator but is an observed pipeline behavior, not tuned.
- Plant-outage event is recorded in manifest but the pipeline consumes demand+weather only; no generation-based stress signal exists to validate, so it is reported as out of scope for these readouts.

## Skills used
- None (direct file edits, terminal, and unmodified pipeline imports).
