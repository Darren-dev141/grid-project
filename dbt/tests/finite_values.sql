select hour_utc from {{ ref('pjm_bge_hourly_price') }}
where not {{ is_finite('price_usd_per_mwh') }}
