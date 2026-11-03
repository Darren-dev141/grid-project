-- EIA timestamps end an hourly interval. Midnight belongs to the preceding day.
with demand as (
    select *,
        cast(timezone('America/New_York', timezone('UTC', hour_utc)
            - interval 1 microsecond) as date) as local_date,
        timezone('America/New_York', timezone('UTC', hour_utc)) as local_end,
        quality = 'ok' and isfinite(demand_mwh) and demand_mwh >= 0 as usable
    from {{ ref('eia_pjm_hourly_demand') }}
), temperatures as (
    select * from {{ ref('ncei_bwi_daily_temps') }}
    where station = 'USW00093721'
), dates as (
    select local_date from demand
    union all
    select local_date from temperatures
), bounds as (
    select min(local_date) as first_date, max(local_date) as last_date from dates
), calendar as (
    select cast(day as date) as local_date
    from bounds, lateral generate_series(first_date, last_date, interval 1 day) s(day)
), counts as (
    select local_date, count(*) as observed_hours,
        count(*) filter (where usable) as ok_hours
    from demand group by local_date
), peaks as (
    select local_date, demand_mwh as peak_mw, hour_utc as peak_hour_utc,
        case when extract(hour from local_end) = 0 then 24
             else extract(hour from local_end) end as peak_hour_ending
    from demand where usable
    qualify row_number() over (
        partition by local_date order by demand_mwh desc, hour_utc
    ) = 1
), days as (
    select local_date,
        date_diff('hour', timezone('America/New_York', cast(local_date as timestamp)),
            timezone('America/New_York', cast(local_date + 1 as timestamp))) as expected_hours
    from calendar
)
select d.local_date,
    case when isodow(d.local_date) in (6, 7) then 'weekend' else 'weekday' end as day_type,
    p.peak_mw, p.peak_hour_ending, p.peak_hour_utc,
    d.expected_hours, coalesce(c.observed_hours, 0) as observed_hours,
    coalesce(c.ok_hours, 0) as ok_hours,
    coalesce(c.ok_hours, 0) = d.expected_hours as complete,
    case when t.quality = 'ok' then t.high_f end as tmax_f,
    case when t.quality = 'ok' then t.low_f end as tmin_f,
    t.quality as temperature_quality
from days d
left join counts c using (local_date)
left join peaks p using (local_date)
left join temperatures t using (local_date)
