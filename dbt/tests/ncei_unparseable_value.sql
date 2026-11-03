select * from {{ ref('ncei_bwi_daily_temps') }} where quality = 'invalid'
