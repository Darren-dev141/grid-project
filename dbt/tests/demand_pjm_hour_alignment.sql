select hour_utc
from {{ ref('eia_pjm_hourly_demand') }}
where extract(minute from hour_utc) <> 0
   or extract(second from hour_utc) <> 0
