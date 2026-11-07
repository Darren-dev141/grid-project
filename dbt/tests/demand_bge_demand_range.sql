select hour_utc, demand_mwh
from {{ ref('eia_bge_hourly_demand') }}
where not {{ is_finite('demand_mwh') }} or demand_mwh < 0
