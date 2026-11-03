# S3b daily observed history

S3b acceptance recorded Oct 30, 2026, citing Darren's verification: “I'm saying it's verified. You can go ahead.” This supersedes the runtime-limited status below. PLAN.md v3 remains the plan of record. This stage makes no forecasting claim.

## Shape and boundaries

`marts.mart_day_history` is a DuckDB dbt view with one row per local date in
America/New_York. It reads only `cleaned.eia_pjm_hourly_demand` and
`cleaned.ncei_bwi_daily_temps`. No BGE demand is joined. Existing raw ingestion
and cleaned revision selection remain the source of truth.

The view spans the first through last date found in either cleaned input. A date
spine preserves full-day gaps, including dates represented only by weather.
Empty inputs yield no rows. This favors visible missing history over an inner
join that hides gaps. It does not claim coverage before or after those bounds.

Columns are `local_date`, `day_type`, `peak_mw`, `peak_hour_ending`,
`peak_hour_utc`, `expected_hours`, `observed_hours`, `ok_hours`, `complete`,
`tmax_f`, `tmin_f`, and `temperature_quality`.

PJM peaks use cleaned quality `ok`, finite, nonnegative values. EIA reports
integrated hourly MWh, numerically equal to average MW across the one-hour
interval. Equal peaks choose the earliest UTC interval. `peak_hour_utc` retains
the original UTC timestamp, so repeated autumn clock hours remain identifiable.
Days with no usable demand have null peak fields. Incomplete days retain
provisional peaks; consumers must check `complete` before treating them as daily
actuals.

`complete` describes demand only. It compares usable hourly intervals with the
UTC distance between consecutive local midnights, exactly 23, 24, or 25 hours.
`observed_hours` includes non-ok rows, while `ok_hours` counts usable rows.
Neither weather availability nor a completed ingestion checkpoint makes demand
complete. `day_type` distinguishes weekdays and weekends, without a holiday model.

## Hour-ending dates

[EIA's time reporting documentation](https://www.eia.gov/electricity/930-content/about.html)
states that hourly timestamps use the hour-ending convention. The mart assigns
each interval to the local date immediately before its ending instant. An
interval ending at midnight therefore belongs to the preceding date and gets
hour label 24. All other labels use the local ending clock hour, from 1 through
23. The repeated fall hour has the same clock label twice, with distinct UTC
timestamps. This is a documented S3b interval-date decision, not a weather
alignment decision.

The proposal's eight local-midnight peaks are a historical observation under its
earlier grouping, not a verified count for this mart. The verification script
reports every hour-24 peak for review. Their values and neighboring intervals
were pending in the earlier session. Darren's Oct 30 verification supersedes that acceptance hold; no new midnight-peak measurement is claimed here.

## Observed temperatures

BWI station `USW00093721` is joined on NCEI's reported observation date. Only
quality `ok` supplies high and low; non-ok observations retain their quality but
yield null temperatures. An absent observation has null quality and temperatures.
This preserves the observed-day contract from S3a.

Darren settled the S3c convention on Oct 30, 2026. The calendar-day spine governs: observed TMIN(D) belongs to calendar date D, the tail of the night ending that morning. An NWS night-period low maps to the local calendar date of the morning it ends on. It is never joined to the date the night starts. This is the modeling convention, not a claim that every observed minimum occurs before dawn.

## Build and verify

`grid_pipeline.warehouse.build(database, select=['+mart_day_history'])` invokes
dbt with the running Python, disables telemetry for the child, and places logs
and target artifacts alongside the scratch warehouse. It retries only the known
Windows `send_bytes()` failure, at most three attempts; other failures raise.
It never installs dependencies or fetches data. Existing legacy test helpers
are unchanged; the new mart tests use this helper.

The scoped build uses cautious indirect test selection because the existing
combined demand tests also depend on BGE. A PJM-only unparseable-input test
preserves the format-change failure in this sub-DAG. The legacy price models
still require a verified node variable for a full-project build without a selection.
No placeholder node or key is supplied for S3b.

From a compatible project Python, run:

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/verify-s3b.py data/scratch/s3b-check-1
```

Use a new scratch directory each time. The script opens `data/s1-live/grid.duckdb`
and `data/s3a-verification/grid.duckdb` read-only, copies raw records and batch
metadata into scratch, and builds `+mart_day_history`. It prints and saves
`coverage.json` with row count, distinct-date count, date span, complete-demand
count, weather count, joined count, all gap dates and their full rows, DST rows,
and midnight peaks. It makes no network requests and never rebuilds a source store.

The synthetic integration checks cover a complete spring day, a complete fall
day with both repeated hours, midnight assignment, peak ties, a normal complete
day, a 24-hour day with only 23 usable hours, each DST day missing one interval,
a physically absent hour, malformed provider values, rejected
spikes, null demand, full-day gaps, flagged and absent temperatures, date joins,
unique dates, and empty history. dbt tests check the date key, day type, expected
hours, completeness, peak and temperature consistency, and malformed demand.

## Earlier session verification limits (superseded acceptance status)

The accessible Miniconda Python is 3.12.8. The project packages contain the
DuckDB `cp314` extension. Adding that site-packages directory lets pytest run
pure Python tests but cannot load DuckDB. The project Python trampoline fails
with permission denied, and the native Hermes Python path could not be invoked.
No permissions, configuration, packages, or sandbox settings were changed.

Five mocked warehouse-helper tests passed under Python 3.12. The full suite
stopped with ten collection errors for missing `_duckdb`. A direct dbt import
with the project packages stopped at missing `rpds.rpds`, another native
dependency. No dbt model or dbt test ran. Real row counts, span, gap dates,
midnight review, and synthetic SQL behavior remain unmeasured. S3b acceptance is now recorded by Darren's Oct 30, 2026 verification, quoted above. These runtime observations remain as the historical record of the earlier session, not a current acceptance hold.



