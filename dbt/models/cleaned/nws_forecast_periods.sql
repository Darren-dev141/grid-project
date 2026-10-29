-- Each immutable response is an issuance observation, including upstream revisions.
with documents as (
    select r.digest, b.loaded_at as fetched_at_utc,
        try_cast(r.payload->>'$.properties.updateTime' as timestamptz) as issued_at_utc,
        try_cast(r.payload->>'$.properties.generatedAt' as timestamptz) as generated_at_utc,
        r.payload
    from {{ source('raw', 'records') }} r
    join {{ source('raw', 'batches') }} b using (source, dataset, digest)
    where r.source = 'nws' and r.dataset = 'forecast' and b.committed
), periods as (
    select d.digest, d.fetched_at_utc, d.issued_at_utc, d.generated_at_utc,
        try_cast(p.value->>'number' as integer) as period_number,
        p.value->>'name' as period_name,
        try_cast(p.value->>'startTime' as timestamptz) as start_time_utc,
        try_cast(p.value->>'endTime' as timestamptz) as end_time_utc,
        try_cast(p.value->>'isDaytime' as boolean) as is_daytime,
        try_cast(p.value->>'temperature' as double) as temperature_f,
        p.value->>'temperatureUnit' as temperature_unit,
        p.value->>'shortForecast' as short_forecast
    from documents d, lateral json_each(d.payload, '$.properties.periods') p
)
select sha256(cast(timezone('UTC', issued_at_utc) as varchar) || '|' ||
              cast(timezone('UTC', generated_at_utc) as varchar) || '|' ||
              cast(timezone('UTC', fetched_at_utc) as varchar) || '|' || digest) as issuance_id,
    *, cast(timezone('America/New_York', start_time_utc) as date) as local_date
from periods
