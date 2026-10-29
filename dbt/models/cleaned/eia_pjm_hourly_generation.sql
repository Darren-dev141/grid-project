with parsed as (
    select
        try_strptime(r.payload ->> 'period', '%Y-%m-%dT%H') as hour_utc,
        r.payload ->> 'respondent' as respondent,
        r.payload ->> 'fueltype' as fuel_type,
        try_cast(r.payload ->> 'value' as double) as generation_mwh,
        r.payload ->> 'value-units' as units,
        b.loaded_at, coalesce(b.observed_at, b.loaded_at) as observed_at,
        r.digest, r.row_number
    from {{ source('raw', 'records') }} r
    join {{ source('raw', 'batches') }} b using (source, dataset, digest)
    where r.source = 'eia' and r.dataset = 'electricity/rto/fuel-type-data'
        and b.committed
), ranked as (
    select *, row_number() over (
        partition by hour_utc, respondent, fuel_type
        order by observed_at desc, digest desc, row_number desc
    ) as revision_rank
    from parsed where respondent = 'PJM'
)
select hour_utc, respondent, fuel_type, generation_mwh, units,
    generation_mwh < 0 as negative_generation,
    loaded_at, observed_at, digest
from ranked where revision_rank = 1
