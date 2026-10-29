# S2: Reisterstown NWS ingestion

## How would you explain the pipeline in an interview?

This adds a second independent public source to the Maryland grid-stress brief.
NWS supplies weather forecasts and heat/cold alerts; it is not a grid measurement,
and this point forecast is not a load-weighted PJM weather index. Everything runs
locally with Python, DuckDB and dbt, at $0 and without an API key.

```powershell
$env:NWS_USER_AGENT='grid-project/0.1 (github.com/Darren-dev141/grid-project)'
.venv/Scripts/grid-weather.exe --root data/nws-live
$env:GRID_DATABASE=(Resolve-Path data/nws-live/grid.duckdb).Path
.venv/Scripts/dbt.exe build --project-dir dbt --profiles-dir dbt --select 'nws_*'
```

The CLI verifies `/points/39.4696,-76.8294` against the pinned LWX office,
gridX 100, gridY 98. It then fetches `/gridpoints/LWX/100,98/forecast` and
`/alerts/active?point=39.4696,-76.8294`. These coordinates were resolved live;
each subsequent load verifies them because NWS grid assignments can change.
The identifying User-Agent comes from the environment, never an embedded email.
Every request sends `Accept: application/geo+json`.

## Why this data shape?

All received response bodies, including errors and point resolution, land untouched
in `root/raw/nws/<sha256>.json`. Landing precedes JSON parsing and indexing. Point
responses are evidence only. Forecasts index one complete document, preserving
`properties.updateTime`, `generatedAt` and `periods`; alerts index each GeoJSON
feature. An empty alert response still creates a raw batch, distinguishing a
successful empty observation from a missing load. All alert types remain in raw.
The two datasets are `forecast` and `alerts` in the existing raw tables.

`nws_forecast_periods` expands the approximately 12-hour periods. It retains
UTC instants (`TIMESTAMPTZ`), issue and generation times, first index time,
response digest, period number, temperature in Fahrenheit, and local date.
DuckDB clients should use `SET TimeZone='UTC'` to display UTC strings; instants
are timezone-aware regardless of display settings. dbt's profile already does so.
`nws_forecast_daily` aggregates highs from daytime periods and lows from nighttime
periods by `America/New_York` start date. The low for a date means the night
starting on that date, not necessarily the meteorological midnight-to-midnight
minimum. A night crossing midnight stays on its starting date. DST uses the IANA
timezone, not a fixed UTC offset. Missing highs/lows remain NULL, with period
counts available to identify partial days. No hourly endpoint is needed for this
scope, avoiding an extra request and a second aggregation definition.

Every distinct response survives. `issuance_id` incorporates updateTime,
generatedAt, first index time and digest. Same-issuance corrections remain distinct.
The fetch timestamp is `raw.batches.loaded_at`, recorded immediately after receipt
and validation; it approximates receipt, rather than measuring the network's exact
completion instant. Byte-identical loads insert nothing and preserve their original
timestamp: this is an issuance-observation store, not a log of every polling attempt.
`nws_forecast_latest` selects a whole issuance ordered by updateTime, generatedAt,
fetch time and digest, so a late-arriving stale response cannot win by arrival alone.
History never uses this convenience view as its source. Only committed batches
appear in cleaned models.

`nws_alerts` retains heat/cold alert observations and their identity, event, timing,
severity, headline and description. Its whitelist is Heat Advisory; Extreme Heat
Watch/Warning; Excessive Heat Watch/Warning; Cold Weather Advisory; Extreme Cold
Watch/Warning; Wind Chill Advisory/Watch/Warning. These names are configured from
the requested current and historical terminology, **not verified by the live
response**: no active alerts were returned. New event naming needs an explicit
whitelist update. This is alert history, not a current-active view; disappearance
from later snapshots does not delete history. An empty snapshot is visible in
raw.batches, not as a fabricated alert row.

## What tradeoffs and failure modes did you handle?

- Missing/blank User-Agent fails before network activity. No key is accepted or needed.
- Network errors, 429 and 5xx have at most three attempts with 1/2-second backoff.
  Any Retry-After header ends this run with a safe request to retry later; it is
  never ignored in favor of an earlier retry. Other HTTP errors fail immediately.
  Requests have a 30-second timeout and redirects are disabled.
- Invalid JSON, incomplete envelopes or gridpoint mismatch fail safely. Bytes
  remain landed; malformed forecast/alert documents are not indexed. dbt separately
  rejects invalid timestamps, NULL required fields, unsupported units, nonfinite
  temperatures and duplicate issuance/period keys.
- Forecast and alerts commit independently. If alerts fail after a forecast succeeds,
  the CLI exits nonzero, but the successful forecast remains. Replay is safe. A
  future orchestrator should track source-specific freshness and distinguish failed
  alerts from an empty successful collection.
- No assertion promises weather accuracy, a fixed horizon, complete daily pairs,
  or a nonempty alert result. A daylight-only or nighttime-only edge day is valid.
- Storage changes are confined to accepting/extracting NWS; EIA/PJM extraction
  and transaction behavior remain unchanged. Existing raw source declarations are
  reused; sources.yml and the shared schema.yml are untouched.

## What did the live exercise demonstrate?

See [machine-readable evidence](evidence/nws-live-2026-10-29.json). The run used
four requests total: initial point resolution, then the CLI's point check,
forecast and alerts. Scratch bodies and DuckDB remain gitignored in data/nws-live.
The fetch occurred on October 29 UTC (October 28 in Maryland). It yielded 14
periods, 8 local dates (October 28 through November 4), 7 highs, 7 lows and 6
complete pairs. The NWS update was 2026-10-28T23:52:47Z; generation was
2026-10-29T02:37:21Z; first forecast indexing was 2026-10-29T03:27:32.061698Z.
Update-to-index lag was 12,885.061698 seconds (about 3h 35m). The live dbt build
passed four models and twenty data tests. No active alerts means this exercise
could not verify a live heat/cold feature; synthetic fixtures cover their shapes
and every configured event name.

## How was it tested?

Client tests use httpx.MockTransport; integration tests execute real dbt against
synthetic temporary DuckDB databases and select only nws_* (no price-node variable).
They exercise issuance revisions, local dates/DST, stale arrivals, latest selection,
partial days, pending batches, alert history/filtering and bad data failures.
The known Python 3.14/Windows send_bytes subprocess error is retried once only,
with a warning when encountered.

Observed RED messages before implementation:

| Behavior | Observed RED |
| --- | --- |
| NWS raw landing, extraction and replay | `ValueError: source must be eia or pjm` |
| Missing UA, fetch success/replay, bounded 5xx/network retries, point mismatch, malformed body, HTTP 403, CLI failure | `ModuleNotFoundError: No module named 'grid_pipeline.nws'` (module absent) |
| Reject incomplete forecast/alert rows before indexing | `Failed: DID NOT RAISE ValueError` (both cases) |
| Console script registration | `KeyError: 'grid-weather'` |
| Preserve 403/429/503 response bytes | `assert False` on raw-body existence (three cases) |
| Respect Retry-After | expected `later retry`, actual `NWS HTTP 429 after 3 attempts` |
| Forecast issuance history, local dates/DST, latest and pending exclusion | `Catalog Error: Table with name nws_forecast_periods does not exist!` |
| Heat/cold whitelist and alert revisions | `Catalog Error: Table with name nws_alerts does not exist!` |
| NaN, non-F units, malformed start time, NULL daytime flag | `assert 0 != 0` (dbt had no selected models/tests yet) |
| Stable issuance identity across DuckDB session timezones | Assertion showed different issuance hashes for UTC and America/New_York |

The later CLI-success, safe-storage-error, partial-day/fetch-tie and duplicate-period
checks were supplementary regression coverage: they passed on first execution,
so there is no independent RED for those branches. This is a deviation from the requested strict per-behavior TDD,
reported rather than claiming a RED that was not observed.

Final validation: `python -m pytest -q` completed with **69 passed in 88.74s**
(43 existing plus 26 NWS tests). The final run needed no subprocess retries.
Two development runs encountered the known Windows `concurrent send_bytes()`
error; each passed its single retry. Final live dbt validation passed all 24
selected nodes (4 models, 20 tests), and offline replay of the two saved live
bodies inserted zero rows. No additional network requests were used for replay.
