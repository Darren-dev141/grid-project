-- The legacy combined demand test also references BGE, outside this sub-DAG.
select hour_utc from {{ ref('eia_pjm_hourly_demand') }} where quality = 'invalid'
