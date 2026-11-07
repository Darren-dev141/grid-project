-- Each immutable response is an issuance observation, including upstream revisions.
with documents as (
    select r.digest, b.loaded_at as fetched_at_utc,
        {{ try_cast(json_text('r.payload', 'properties.updateTime'), 'timestamptz') }} as issued_at_utc,
        {{ try_cast(json_text('r.payload', 'properties.generatedAt'), 'timestamptz') }} as generated_at_utc,
        r.payload
    from {{ source('raw', 'records') }} r
    join {{ source('raw', 'batches') }} b using (source, dataset, digest)
    where r.source = 'nws' and r.dataset = 'forecast' and b.committed
), periods as (
    select d.digest, d.fetched_at_utc, d.issued_at_utc, d.generated_at_utc,
        {{ try_cast(json_text('p.value', 'number'), 'integer') }} as period_number,
        {{ json_text('p.value', 'name') }} as period_name,
        {{ try_cast(json_text('p.value', 'startTime'), 'timestamptz') }} as start_time_utc,
        {{ try_cast(json_text('p.value', 'endTime'), 'timestamptz') }} as end_time_utc,
        {{ try_cast(json_text('p.value', 'isDaytime'), 'boolean') }} as is_daytime,
        {{ try_cast(json_text('p.value', 'temperature'), 'double') }} as temperature_f,
        {{ json_text('p.value', 'temperatureUnit') }} as temperature_unit,
        {{ json_text('p.value', 'shortForecast') }} as short_forecast
    from documents d, lateral {{ json_array_elements('d.payload', 'properties.periods') }}
)
select {{ sha256_hex("cast(timezone('UTC', issued_at_utc) as varchar) || '|' ||
              cast(timezone('UTC', generated_at_utc) as varchar) || '|' ||
              cast(timezone('UTC', fetched_at_utc) as varchar) || '|' || digest") }} as issuance_id,
    *, cast(timezone('America/New_York', start_time_utc) as date) as local_date
from periods
