select hour_utc from {{ ref('eia_pjm_hourly_generation') }}
where hour_utc <> date_trunc('hour', hour_utc)
