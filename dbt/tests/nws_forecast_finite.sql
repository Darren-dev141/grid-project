select * from {{ ref('nws_forecast_periods') }}
where not isfinite(temperature_f)
