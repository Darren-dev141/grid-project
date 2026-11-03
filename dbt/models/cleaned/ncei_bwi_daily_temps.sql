-- NCEI's reported observation date, not the NWS night-start convention.
with parsed as (
    select try_cast(r.payload ->> 'DATE' as date) as local_date,
        r.payload ->> 'STATION' as station,
        r.payload ->> 'TMAX' as reported_high,
        r.payload ->> 'TMIN' as reported_low,
        try_cast(r.payload ->> 'TMAX' as double) as high_f,
        try_cast(r.payload ->> 'TMIN' as double) as low_f,
        r.payload ->> 'TMAX_ATTRIBUTES' as high_attributes,
        r.payload ->> 'TMIN_ATTRIBUTES' as low_attributes,
        b.loaded_at, coalesce(b.observed_at, b.loaded_at) as observed_at,
        r.digest, r.row_number
    from {{ source('raw', 'records') }} r
    join {{ source('raw', 'batches') }} b using (source, dataset, digest)
    where r.source = 'ncei' and r.dataset = 'daily-summaries' and b.committed
), ranked as (
    select *, row_number() over (
        partition by station, local_date
        order by observed_at desc, digest desc, row_number desc
    ) as revision_rank from parsed
)
select local_date, station, high_f, low_f, high_attributes, low_attributes,
    case when (high_f is null and reported_high is not null)
           or (low_f is null and reported_low is not null) then 'invalid'
         when high_f is null or low_f is null then 'missing'
         when not isfinite(high_f) or not isfinite(low_f)
           or high_f not between -100 and 140 or low_f not between -100 and 140
           or low_f > high_f then 'implausible'
         when coalesce(split_part(high_attributes, ',', 2), '') != ''
           or coalesce(split_part(low_attributes, ',', 2), '') != '' then 'flagged'
         else 'ok' end as quality,
    loaded_at, observed_at, digest
from ranked where revision_rank = 1
