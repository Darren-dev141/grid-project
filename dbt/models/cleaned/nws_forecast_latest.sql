with latest as (
    select issuance_id
    from {{ ref('nws_forecast_daily') }}
    order by issued_at_utc desc, generated_at_utc desc, fetched_at_utc desc, digest desc
    limit 1
)
select d.* from {{ ref('nws_forecast_daily') }} d
join latest using (issuance_id)
