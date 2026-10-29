select hour_utc, respondent, fuel_type
from {{ ref('eia_pjm_hourly_generation') }}
group by all having count(*) > 1
