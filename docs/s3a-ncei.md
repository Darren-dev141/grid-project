# S3a: BWI observed temperature history

Implemented locally on October 29, 2026, using the architecture proposal's default
NCEI source. Runner selection and retirement of the v1 price path remain open.

## Contract and tradeoffs

`grid-temps` requests NOAA NCEI's keyless daily-summaries endpoint for BWI station
`USW00093721`, selecting TMAX and TMIN with `units=standard` (Fahrenheit) and
`includeAttributes=true`. The API returns a JSON array, unlike EIA's envelope.
The existing content-addressed raw store retains the exact response bytes,
including malformed and HTTP error responses. A bad envelope, foreign station,
duplicate date or out-of-range date cannot become an indexed batch.

The command uses start-inclusive, end-exclusive dates and converts the end to
NOAA's inclusive endDate. Requests are bounded to 366 days; annual windows cover
the historical range without an unbounded download. Re-run overlapping windows
to refresh corrections. There is deliberately no completed-through checkpoint:
recent missing days and older corrections must remain fetchable. A later daily
runner should request a recent overlap and periodically refresh older history.

Committed batches are selected by their latest observation time. A byte-identical
reload inserts no raw rows but updates that observation time, so an A -> B -> A
provider revision restores A correctly. First indexing time remains unchanged.
Pending batches are invisible to the cleaned view and can be resumed by replaying
the request. No existing raw file is overwritten.

The cleaned view keeps provider values and both attribute fields. Its quality
is `ok`, `missing`, `invalid`, `implausible` or `flagged`. Non-numeric reported
values fail dbt rather than silently becoming missing. Non-finite values,
temperatures outside conservative -100 to 140 F bounds, or low above high are
implausible. A nonempty NOAA quality flag (second comma-separated attribute)
marks a row flagged. Model fitting must select only ok rows.

NOAA's observation date is retained as supplied. This does not resolve S3c's
remaining alignment question: an observed daily minimum is not automatically
the low for the NWS night starting on the same date. The feature mart and index
must document their temperature alignment before a forecast is published.

## Run

Reinstall the editable package to register the new console command:

```powershell
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.venv/Scripts/grid-temps.exe --start 2026-10-01 --end 2026-10-29
# Module invocation also works without reinstalling:
.venv/Scripts/python.exe -m grid_pipeline.ncei --start 2026-10-01 --end 2026-10-29
$env:GRID_DATABASE = (Resolve-Path data/grid.duckdb).Path
.venv/Scripts/dbt.exe build --project-dir dbt --profiles-dir dbt --select 'ncei_*'
```

Saved NCEI responses requested with standard units can be indexed with
`grid ncei daily-summaries response.json`. Replay cannot infer the requested units
from a bare NOAA response; retain the request provenance with the saved response.

## Verification

The isolated live warehouse is `data/s3a-verification/grid.duckdb`; the primary
warehouse is untouched by this verification. Eight annual requests yielded
2,854 dates from 2019-01-01 through 2026-10-24, every row quality ok. Recent
observations lag five days on this run; this is not an upstream freshness promise.
The real dbt build passed eight tests and built one view. Request boundaries,
digests, counts and recent rows are in
[the live evidence](evidence/ncei-live-2026-10-29.json).

Offline tests cover request units and date boundaries, exact raw retention,
malformed/scope rejection, bounded retries, Retry-After deferral, identical
replay, A -> B -> A revisions, pending batch exclusion, quality flags, and a
non-numeric value failing the real dbt build.

Sources: [NCEI API documentation](https://www.ncei.noaa.gov/support/access-data-service-api-user-documentation),
[GHCN daily format](https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt).
This milestone supplies historical observations; it does not earn a forecasting
or application resume claim.
