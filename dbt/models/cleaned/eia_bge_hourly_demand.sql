with parsed as (
    select
        try_strptime(r.payload ->> 'period', '%Y-%m-%dT%H') as hour_utc,
        r.payload ->> 'subba' as subba,
        r.payload ->> 'parent' as parent,
        r.payload ->> 'value' as reported_value,
        try_cast(r.payload ->> 'value' as double) as demand_mwh,
        r.payload ->> 'value-units' as units,
        b.loaded_at,
        coalesce(b.observed_at, b.loaded_at) as observed_at,
        r.digest,
        r.row_number
    from {{ source('raw', 'records') }} r
    join {{ source('raw', 'batches') }} b using (source, dataset, digest)
    where r.source = 'eia'
        and r.dataset = 'electricity/rto/region-sub-ba-data'
        and b.committed
), ranked as (
    select *, row_number() over (
        partition by hour_utc
        order by observed_at desc, digest desc, row_number desc
    ) as revision_rank
    from parsed
    where parent = 'PJM' and subba = 'BC'
)
-- ponytail: no plausibility cap until live BGE history has been profiled.
select hour_utc, subba, parent, demand_mwh, units,
    case when demand_mwh is null and reported_value is not null then 'invalid'
         when demand_mwh is null then 'missing' else 'ok' end as quality,
    'BGE zone (trailing local context, about 2 days behind; not used for RTO scoring)' as geography,
    loaded_at, observed_at, digest
from ranked
where revision_rank = 1
