select hour_utc
from {{ ref('eia_bge_hourly_demand') }}
where extract(minute from hour_utc) <> 0
   or extract(second from hour_utc) <> 0
