select r.digest, r.row_number, b.loaded_at as fetched_at_utc,
    coalesce({{ json_text('r.payload', 'properties.id') }}, {{ json_text('r.payload', 'id') }}) as alert_id,
    {{ json_text('r.payload', 'properties.event') }} as event,
    {{ try_cast(json_text('r.payload', 'properties.sent'), 'timestamptz') }} as sent_at_utc,
    {{ try_cast(json_text('r.payload', 'properties.effective'), 'timestamptz') }} as effective_at_utc,
    {{ try_cast(json_text('r.payload', 'properties.onset'), 'timestamptz') }} as onset_at_utc,
    {{ try_cast(json_text('r.payload', 'properties.expires'), 'timestamptz') }} as expires_at_utc,
    {{ try_cast(json_text('r.payload', 'properties.ends'), 'timestamptz') }} as ends_at_utc,
    {{ json_text('r.payload', 'properties.severity') }} as severity,
    {{ json_text('r.payload', 'properties.headline') }} as headline,
    {{ json_text('r.payload', 'properties.description') }} as description
from {{ source('raw', 'records') }} r
join {{ source('raw', 'batches') }} b using (source, dataset, digest)
where r.source = 'nws' and r.dataset = 'alerts' and b.committed
    and ({{ json_text('r.payload', 'properties.event') }}) in (
        'Heat Advisory', 'Extreme Heat Watch', 'Extreme Heat Warning',
        'Excessive Heat Watch', 'Excessive Heat Warning', 'Cold Weather Advisory',
        'Extreme Cold Watch', 'Extreme Cold Warning', 'Wind Chill Advisory',
        'Wind Chill Watch', 'Wind Chill Warning'
    )
