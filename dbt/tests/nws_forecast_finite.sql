select * from {{ ref('nws_forecast_periods') }}
where not {{ is_finite('temperature_f') }}
