with parsed as (
    select
        try_strptime(r.payload ->> 'datetime_beginning_utc',
            ['%m/%d/%Y %H:%M:%S', '%m/%d/%Y %H:%M', '%Y-%m-%dT%H:%M:%S']) as hour_utc,
        try_cast(r.payload ->> 'pnode_id' as bigint) as pnode_id,
        try_cast(r.payload ->> 'total_lmp_rt' as double) as price_usd_per_mwh,
        b.loaded_at,
        coalesce(b.observed_at, b.loaded_at) as observed_at,
        r.digest,
        r.row_number
    from {{ source('raw', 'records') }} r
    join {{ source('raw', 'batches') }} b using (source, dataset, digest)
    where r.source = 'pjm' and r.dataset = 'rt_hrl_lmps' and b.committed
), ranked as (
    select *, row_number() over (
        partition by hour_utc, pnode_id
        order by observed_at desc, digest desc, row_number desc
    ) as revision_rank
    from parsed
    where pnode_id = {{ bge_node() }}
)
select hour_utc, pnode_id, price_usd_per_mwh,
    'BGE pricing node' as price_geography, loaded_at, observed_at, digest
from ranked where revision_rank = 1
