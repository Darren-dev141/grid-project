select hour_utc, demand_mwh
from {{ ref('eia_bge_hourly_demand') }}
where not isfinite(demand_mwh) or demand_mwh < 0
