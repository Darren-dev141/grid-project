-- A night is assigned to the local date on which its period starts.
select issuance_id, digest, issued_at_utc, generated_at_utc, fetched_at_utc, local_date,
    max(temperature_f) filter (where is_daytime) as high_f,
    min(temperature_f) filter (where not is_daytime) as low_f,
    count(*) filter (where is_daytime) as daytime_period_count,
    count(*) filter (where not is_daytime) as nighttime_period_count,
    min(start_time_utc) as first_period_start_utc,
    max(end_time_utc) as last_period_end_utc
from {{ ref('nws_forecast_periods') }}
group by issuance_id, digest, issued_at_utc, generated_at_utc, fetched_at_utc, local_date
