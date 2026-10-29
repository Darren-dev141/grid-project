-- Provider gaps and spikes are kept and reported, never silently dropped or fixed.
{{ config(severity='warn') }}
select 'pjm' as series, hour_utc, demand_mwh, quality
from {{ ref('eia_pjm_hourly_demand') }} where quality <> 'ok'
union all
select 'bge', hour_utc, demand_mwh, quality
from {{ ref('eia_bge_hourly_demand') }} where quality <> 'ok'
