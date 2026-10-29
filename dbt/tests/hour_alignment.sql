select hour_utc from {{ ref('pjm_bge_hourly_price') }}
where hour_utc <> date_trunc('hour', hour_utc)
