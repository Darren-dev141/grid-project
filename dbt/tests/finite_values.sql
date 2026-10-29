select hour_utc from {{ ref('pjm_bge_hourly_price') }}
where not isfinite(price_usd_per_mwh)
