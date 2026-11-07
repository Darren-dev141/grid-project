select * from {{ ref('mart_day_history') }}
where ok_hours < 0 or observed_hours < ok_hours or observed_hours > expected_hours
    or complete != (ok_hours = expected_hours)
    or (ok_hours = 0 and (peak_mw is not null or peak_hour_ending is not null
        or peak_hour_utc is not null))
    or (ok_hours > 0 and (peak_mw is null or peak_hour_ending is null
        or peak_hour_utc is null))
    or peak_hour_ending not between 1 and 24
    or not {{ is_finite('peak_mw') }} or peak_mw < 0
    or (temperature_quality is distinct from 'ok' and (tmax_f is not null or tmin_f is not null))
    or (temperature_quality = 'ok' and (tmax_f is null or tmin_f is null or tmin_f > tmax_f))
