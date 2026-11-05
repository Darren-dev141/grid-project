-- Night lows are aligned to the local calendar date on which the night ENDS
-- (morning-end-date convention; see docs/s3b-day-history.md:58). Daytime
-- highs stay on their own start date. An issuance missing either value yields
-- a null high_f or low_f (incomplete pair).
with periods as (
    select * from {{ ref('nws_forecast_periods') }}
),
aligned as (
    select issuance_id, digest, issued_at_utc, generated_at_utc, fetched_at_utc,
        start_time_utc, end_time_utc,
        cast(timezone('America/New_York', start_time_utc) as date) as local_date,
        is_daytime, temperature_f
    from periods
    where is_daytime
    union all
    select issuance_id, digest, issued_at_utc, generated_at_utc, fetched_at_utc,
        start_time_utc, end_time_utc,
        cast(timezone('America/New_York', end_time_utc) as date) as local_date,
        is_daytime, temperature_f
    from periods
    where not is_daytime
)
select issuance_id, digest, issued_at_utc, generated_at_utc, fetched_at_utc,
    fetched_at_utc as loaded_at, local_date,
    max(temperature_f) filter (where is_daytime) as high_f,
    min(temperature_f) filter (where not is_daytime) as low_f,
    count(*) filter (where is_daytime) as daytime_period_count,
    count(*) filter (where not is_daytime) as nighttime_period_count,
    count(*) as period_count,
    min(start_time_utc) as first_period_start_utc,
    max(end_time_utc) as last_period_end_utc
from aligned
group by issuance_id, digest, issued_at_utc, generated_at_utc, fetched_at_utc, local_date
