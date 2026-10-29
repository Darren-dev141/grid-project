select hour_utc, fuel_type
from {{ ref('eia_pjm_hourly_generation') }}
where not isfinite(generation_mwh)
