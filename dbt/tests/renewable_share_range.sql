select * from {{ ref('grid_hourly') }}
where renewable_share < 0 or renewable_share > 1
   or not {{ is_finite('renewable_share') }}
   or (not mix_complete and renewable_share is not null)
