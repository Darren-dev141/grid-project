-- A non-null value that does not parse as a number means the provider format changed.
select 'pjm' as series, hour_utc from {{ ref('eia_pjm_hourly_demand') }} where quality = 'invalid'
union all
select 'bge', hour_utc from {{ ref('eia_bge_hourly_demand') }} where quality = 'invalid'
