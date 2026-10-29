select issuance_id, period_number
from {{ ref('nws_forecast_periods') }}
group by issuance_id, period_number
having count(*) <> 1
