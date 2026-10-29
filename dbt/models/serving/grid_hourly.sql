with mix as (
    select hour_utc,
        sum(generation_mwh) as reported_generation_mwh,
        sum(case when fuel_type in ('SUN', 'WAT', 'WND')
                 then generation_mwh else 0 end) as renewable_generation_mwh,
        count(*) as fuel_count,
        count(*) filter (where fuel_type in (
          {% for fuel in var('expected_fuels') %}'{{ fuel }}'{% if not loop.last %}, {% endif %}{% endfor %}
        )) = {{ var('expected_fuels') | length }}
        and count(*) = {{ var('expected_fuels') | length }}
        and bool_and(coalesce(isfinite(generation_mwh) and generation_mwh >= 0
                             and units = 'megawatthours', false)) as mix_complete,
        max(loaded_at) as generation_loaded_at
    from {{ ref('eia_pjm_hourly_generation') }}
    group by hour_utc
)
select coalesce(p.hour_utc, m.hour_utc) as hour_utc,
    p.pnode_id, p.price_usd_per_mwh,
    'BGE pricing node' as price_geography,
    'PJM balancing authority' as generation_geography,
    m.reported_generation_mwh, m.fuel_count,
    coalesce(m.mix_complete, false) as mix_complete,
    case when m.mix_complete and m.reported_generation_mwh > 0
        then m.renewable_generation_mwh / m.reported_generation_mwh
    end as renewable_share,
    p.loaded_at as price_loaded_at, m.generation_loaded_at
from {{ ref('pjm_bge_hourly_price') }} p
full outer join mix m using (hour_utc)
