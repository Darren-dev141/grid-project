with parsed as (
    select
        try_strptime(r.payload ->> 'period', '%Y-%m-%dT%H') as hour_utc,
        r.payload ->> 'respondent' as respondent,
        r.payload ->> 'type' as row_type,
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
        and r.dataset = 'electricity/rto/region-data'
        and b.committed
), ranked as (
    select *, row_number() over (
        partition by hour_utc
        order by observed_at desc, digest desc, row_number desc
    ) as revision_rank
    from parsed
    where respondent = 'PJM'
        and row_type = 'D'
), latest as (
    select * from ranked where revision_rank = 1
)
-- Values stay as reported; quality flags provider errors. Peak PJM load is about
-- 165 GW, so over 200,000 MWh is impossible. A one-hour jump more than 10% above both
-- adjacent hours, or 15% below both, is an error: across 2019-2026 normal hours stay
-- within 3.4% of a neighbour while the errors sit 15-43% above or 41% below.
-- ponytail: thresholds fixed from that profile; amend with evidence, never silently.
select l.hour_utc, l.respondent, l.demand_mwh, l.units,
    case when l.demand_mwh is null and l.reported_value is not null then 'invalid'
         when l.demand_mwh is null then 'missing'
         when l.demand_mwh > 200000 then 'implausible'
         when prev.demand_mwh is not null and next.demand_mwh is not null
           and (l.demand_mwh > 1.10 * greatest(prev.demand_mwh, next.demand_mwh)
             or l.demand_mwh < 0.85 * least(prev.demand_mwh, next.demand_mwh)) then 'implausible'
         else 'ok' end as quality,
    'PJM balancing authority' as geography,
    l.loaded_at, l.observed_at, l.digest
from latest l
left join latest prev on prev.hour_utc = l.hour_utc - interval 1 hour
left join latest next on next.hour_utc = l.hour_utc + interval 1 hour
