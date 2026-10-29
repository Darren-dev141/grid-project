select r.digest, r.row_number, b.loaded_at as fetched_at_utc,
    coalesce(r.payload->>'$.properties.id', r.payload->>'$.id') as alert_id,
    r.payload->>'$.properties.event' as event,
    try_cast(r.payload->>'$.properties.sent' as timestamptz) as sent_at_utc,
    try_cast(r.payload->>'$.properties.effective' as timestamptz) as effective_at_utc,
    try_cast(r.payload->>'$.properties.onset' as timestamptz) as onset_at_utc,
    try_cast(r.payload->>'$.properties.expires' as timestamptz) as expires_at_utc,
    try_cast(r.payload->>'$.properties.ends' as timestamptz) as ends_at_utc,
    r.payload->>'$.properties.severity' as severity,
    r.payload->>'$.properties.headline' as headline,
    r.payload->>'$.properties.description' as description
from {{ source('raw', 'records') }} r
join {{ source('raw', 'batches') }} b using (source, dataset, digest)
where r.source = 'nws' and r.dataset = 'alerts' and b.committed
    and (r.payload->>'$.properties.event') in (
        'Heat Advisory', 'Extreme Heat Watch', 'Extreme Heat Warning',
        'Excessive Heat Watch', 'Excessive Heat Warning', 'Cold Weather Advisory',
        'Extreme Cold Watch', 'Extreme Cold Warning', 'Wind Chill Advisory',
        'Wind Chill Watch', 'Wind Chill Warning'
    )
