"""Read first-recorded stress inputs without modifying source databases.

The selected rows are first only within the supplied committed raw archive;
the archive cannot establish observations that were never recorded. Cleaning
and day aggregation use the repository's dbt SQL, not the latest-value mart.
"""
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

from grid_pipeline.model import Alert, HistoryDay


_DBT_MODELS = Path(__file__).resolve().parents[2] / 'dbt' / 'models'
_NEW_YORK = ZoneInfo('America/New_York')

# S5 dialect pass: the dbt models call cross-dialect macros
# (dbt/macros/cross_dialect.sql) that render to the DuckDB-native
# constructs below on the local target. This raw-SQL consumer runs the
# same model text in DuckDB, so _model_sql substitutes each macro
# spelling back to exactly what dbt renders for DuckDB. The count == 1
# assertion in _model_sql keeps any drift between the models and this
# table a loud failure, never a silent change of meaning.
_DUCKDB_MACRO_SUBSTITUTIONS = {
    'cleaned/eia_pjm_hourly_demand.sql': {
        "{{ try_strptime(\"r.payload ->> 'period'\", '%Y-%m-%dT%H') }}":
            "try_strptime(r.payload ->> 'period', '%Y-%m-%dT%H')",
        "{{ try_cast(\"r.payload ->> 'value'\", 'double') }}":
            "try_cast(r.payload ->> 'value' as double)",
    },
    'cleaned/ncei_bwi_daily_temps.sql': {
        "{{ try_cast(\"r.payload ->> 'DATE'\", 'date') }}":
            "try_cast(r.payload ->> 'DATE' as date)",
        "{{ try_cast(\"r.payload ->> 'TMAX'\", 'double') }}":
            "try_cast(r.payload ->> 'TMAX' as double)",
        "{{ try_cast(\"r.payload ->> 'TMIN'\", 'double') }}":
            "try_cast(r.payload ->> 'TMIN' as double)",
        "{{ is_finite('high_f') }}": "isfinite(high_f)",
        "{{ is_finite('low_f') }}": "isfinite(low_f)",
    },
    'marts/mart_day_history.sql': {
        "{{ is_finite('demand_mwh') }}": "isfinite(demand_mwh)",
        ("{{ date_diff_hour(\"timezone('America/New_York', cast(local_date as timestamp))\",\n"
         "            \"timezone('America/New_York', cast(local_date + 1 as timestamp))\") }}"):
            ("date_diff('hour', timezone('America/New_York', cast(local_date as timestamp)),\n"
             "            timezone('America/New_York', cast(local_date + 1 as timestamp)))"),
        "{{ isodow_of('d.local_date') }}": "isodow(d.local_date)",
    },
}


def _model_sql(relative_path: str, substitutions: dict[str, str]) -> str:
    sql = (_DBT_MODELS / relative_path).read_text(encoding='utf-8')
    for template, replacement in substitutions.items():
        if sql.count(template) != 1:
            raise ValueError(f'unexpected dbt template in {relative_path}: {template}')
        sql = sql.replace(template, replacement)
    if '{{' in sql or '{%' in sql:
        raise ValueError(f'unsupported dbt template in {relative_path}')
    return sql


def _attach_read_only(connection: duckdb.DuckDBPyConnection, path: Path, alias: str) -> None:
    escaped = str(path).replace("'", "''")
    connection.execute(f"ATTACH '{escaped}' AS {alias} (READ_ONLY)")


def load_first_recorded_history(load_database: str | Path,
                                temperature_database: str | Path,
                                *, indexed_by: datetime | None = None) -> tuple[HistoryDay, ...]:
    """Build daily history from committed EIA and NCEI raw rows in read-only databases.

    Ties in recorded load time are ordered by digest and row number. Missing
    recorded timestamps fail closed. The legacy *_available_at fields contain
    indexing times, which may precede commit, not proven first usable times.
    The *_usable_at fields are the derived first-usable times: for each selected
    row, the later of its batch's loaded_at and observed_at (the commit record),
    committed batches only; the day value is the latest across contributing rows
    (load: the hour plus the adjacent hours the quality model reads), and NULL if
    any contributing batch has no commit record. A backdated loaded_at therefore
    cannot move a usable time earlier than the recorded commit. The commit record
    is local DuckDB state and is not tamper-evident; it proves what the archive
    recorded, not independent publication.
    Load indexing bounds include adjacent hours used by the quality model.
    Prospective verification is done by stress.verify_input_availability.
    """
    if indexed_by is not None and indexed_by.utcoffset() is None:
        raise ValueError('indexed_by must be timezone-aware')
    load_path = Path(load_database).resolve(strict=True)
    temperature_path = Path(temperature_database).resolve(strict=True)
    with duckdb.connect(':memory:') as connection:
        connection.execute("SET TimeZone = 'UTC'")
        _attach_read_only(connection, load_path, 'load_source')
        if os.path.samefile(load_path, temperature_path):
            temperature_source = 'load_source'
        else:
            _attach_read_only(connection, temperature_path, 'temperature_source')
            temperature_source = 'temperature_source'

        # usable_at is the first time a batch's rows could be used: the later of the
        # indexing time and the commit record (observed_at). A committed batch with no
        # commit record has no provable first-usable time, so usable_at stays NULL.
        usable = ('CASE WHEN b.committed AND b.observed_at IS NOT NULL '
                  'THEN greatest(b.loaded_at, b.observed_at) END AS usable_at')
        source_queries = {
            'load_rows': f'''
                SELECT r.*, b.loaded_at, {usable}
                FROM load_source.raw.records r
                JOIN load_source.raw.batches b USING (source, dataset, digest)
                WHERE r.source = 'eia' AND r.dataset = 'electricity/rto/region-data'
                    AND b.committed AND (r.payload ->> 'respondent') = 'PJM'
                    AND (r.payload ->> 'type') = 'D'
            ''',
            'temperature_rows': f'''
                SELECT r.*, b.loaded_at, {usable}
                FROM {temperature_source}.raw.records r
                JOIN {temperature_source}.raw.batches b USING (source, dataset, digest)
                WHERE r.source = 'ncei' AND r.dataset = 'daily-summaries'
                    AND b.committed AND (r.payload ->> 'STATION') = 'USW00093721'
            ''',
        }
        for name, query in source_queries.items():
            connection.execute(f'CREATE TEMP VIEW {name}_all AS {query}')
            if connection.execute(f'SELECT EXISTS (SELECT 1 FROM {name}_all '
                                  'WHERE loaded_at IS NULL)').fetchone()[0]:
                raise ValueError(f'{name} contains a committed record without loaded_at')
            cutoff = '' if indexed_by is None else (
                " WHERE loaded_at <= TIMESTAMPTZ '" +
                indexed_by.astimezone(timezone.utc).isoformat() + "'")
            connection.execute(f'CREATE TEMP VIEW {name} AS SELECT * FROM {name}_all{cutoff}')

        connection.execute('''CREATE TEMP VIEW first_load AS
            SELECT *, try_strptime(payload ->> 'period', '%Y-%m-%dT%H') AS hour_utc
            FROM load_rows
            QUALIFY row_number() OVER (
                PARTITION BY hour_utc ORDER BY loaded_at, digest, row_number) = 1''')
        connection.execute('''CREATE TEMP VIEW first_temperature AS
            SELECT *, try_cast(payload ->> 'DATE' AS DATE) AS local_date
            FROM temperature_rows
            QUALIFY row_number() OVER (
                PARTITION BY local_date ORDER BY loaded_at, digest, row_number) = 1''')
        connection.execute('''CREATE TEMP VIEW first_records AS
            SELECT source, dataset, digest, row_number, payload FROM first_load
            UNION ALL
            SELECT source, dataset, digest, row_number, payload FROM first_temperature''')
        connection.execute(f'''CREATE TEMP VIEW source_batches AS
            SELECT source, dataset, digest, path, loaded_at, committed, observed_at
            FROM load_source.raw.batches
            WHERE source = 'eia' AND dataset = 'electricity/rto/region-data'
            UNION ALL
            SELECT source, dataset, digest, path, loaded_at, committed, observed_at
            FROM {temperature_source}.raw.batches
            WHERE source = 'ncei' AND dataset = 'daily-summaries' ''')

        raw_refs = {"{{ source('raw', 'records') }}": 'first_records',
                    "{{ source('raw', 'batches') }}": 'source_batches'}
        demand_sql = _model_sql('cleaned/eia_pjm_hourly_demand.sql',
                                {**raw_refs,
                                 **_DUCKDB_MACRO_SUBSTITUTIONS['cleaned/eia_pjm_hourly_demand.sql']})
        temperature_sql = _model_sql('cleaned/ncei_bwi_daily_temps.sql',
                                     {**raw_refs,
                                      **_DUCKDB_MACRO_SUBSTITUTIONS['cleaned/ncei_bwi_daily_temps.sql']})
        mart_sql = _model_sql('marts/mart_day_history.sql', {
            "{{ ref('eia_pjm_hourly_demand') }}": 'clean_demand',
            "{{ ref('ncei_bwi_daily_temps') }}": 'clean_temperature',
            **_DUCKDB_MACRO_SUBSTITUTIONS['marts/mart_day_history.sql'],
        })
        connection.execute('CREATE TEMP VIEW clean_demand AS ' + demand_sql)
        connection.execute('CREATE TEMP VIEW clean_temperature AS ' + temperature_sql)
        connection.execute('CREATE TEMP VIEW history AS ' + mart_sql)
        rows = connection.execute('''
            WITH availability AS (
                SELECT CAST(timezone('America/New_York', timezone('UTC', current.hour_utc)
                            - INTERVAL 1 MICROSECOND) AS DATE) AS local_date,
                    max(greatest(current.loaded_at, previous.loaded_at, following.loaded_at))
                        AS loaded_at,
                    -- NULL if any contributing hour lacks a commit record: DuckDB's
                    -- greatest() skips NULLs, so absence must be tested explicitly.
                    CASE WHEN bool_or(current.usable_at IS NULL
                                      OR (previous.hour_utc IS NOT NULL AND previous.usable_at IS NULL)
                                      OR (following.hour_utc IS NOT NULL AND following.usable_at IS NULL))
                        THEN NULL
                        ELSE max(greatest(current.usable_at, previous.usable_at, following.usable_at))
                    END AS usable_at
                FROM first_load current
                LEFT JOIN first_load previous
                    ON previous.hour_utc = current.hour_utc - INTERVAL 1 HOUR
                LEFT JOIN first_load following
                    ON following.hour_utc = current.hour_utc + INTERVAL 1 HOUR
                WHERE current.hour_utc IS NOT NULL
                GROUP BY local_date
            )
            SELECT history.local_date, history.peak_mw, history.peak_hour_ending,
                history.tmax_f, history.tmin_f, history.complete,
                availability.loaded_at, first_temperature.loaded_at,
                availability.usable_at, first_temperature.usable_at
            FROM history
            LEFT JOIN availability USING (local_date)
            LEFT JOIN first_temperature USING (local_date)
            ORDER BY history.local_date
        ''').fetchall()
    return tuple(HistoryDay(
        date=day, peak_mw=peak, peak_hour_ending=hour, high_f=high,
        morning_low_f=low, complete=complete,
        load_first_recorded=True if load_at is not None else None,
        temperature_first_recorded=True if temperature_at is not None else None,
        load_available_at=load_at, temperature_available_at=temperature_at,
        load_usable_at=load_usable, temperature_usable_at=temperature_usable,
    ) for (day, peak, hour, high, low, complete, load_at, temperature_at,
           load_usable, temperature_usable) in rows)


def load_nws_bwi_forecast(database, target_date, *, indexed_by=None):
    """Pin the latest committed BWI NWS issuance usable for target_date.

    Returns a dict with high_f, morning_low_f, weather_available_at (loaded_at),
    weather_usable_at (greatest(loaded_at, observed_at) or None without a commit
    record), issuance_id and update_time (NWS updateTime). Returns None if no
    issuance is pinned. A complete pair (both high and low present) beats a newer
    incomplete issuance among those with loaded_at <= indexed_by.
    """
    if indexed_by is not None and indexed_by.utcoffset() is None:
        raise ValueError('indexed_by must be timezone-aware')
    db_path = Path(database).resolve(strict=True)
    # Self-contained alignment over raw nws forecast_bwi records (end-date night
    # alignment). Mirrors dbt/models/cleaned/nws_forecast_daily_end_date.sql but
    # reads raw directly so observed_at (commit record) is available for usable_at.
    sql = """
    with documents as (
        select r.digest, b.loaded_at as fetched_at_utc, b.observed_at,
            try_cast(r.payload->>'$.properties.updateTime' as timestamptz) as issued_at_utc,
            try_cast(r.payload->>'$.properties.generatedAt' as timestamptz) as generated_at_utc,
            r.payload
        from src.raw.records r
        join src.raw.batches b using (source, dataset, digest)
        where r.source = 'nws' and r.dataset = 'forecast_bwi' and b.committed
    ),
    periods as (
        select d.digest, d.fetched_at_utc, d.observed_at, d.issued_at_utc, d.generated_at_utc,
            sha256(cast(timezone('UTC', d.issued_at_utc) as varchar) || '|' ||
                   cast(timezone('UTC', d.generated_at_utc) as varchar) || '|' ||
                   cast(timezone('UTC', d.fetched_at_utc) as varchar) || '|' || d.digest) as issuance_id,
            try_cast(p.value->>'startTime' as timestamptz) as start_time_utc,
            try_cast(p.value->>'endTime' as timestamptz) as end_time_utc,
            try_cast(p.value->>'isDaytime' as boolean) as is_daytime,
            try_cast(p.value->>'temperature' as double) as temperature_f
        from documents d, lateral json_each(d.payload, '$.properties.periods') p
    ),
    day_agg as (
        select issuance_id, digest, fetched_at_utc, observed_at, issued_at_utc, generated_at_utc,
            cast(timezone('America/New_York', start_time_utc) as date) as local_date,
            max(temperature_f) as high_f
        from periods where is_daytime
        group by issuance_id, digest, fetched_at_utc, observed_at, issued_at_utc, generated_at_utc,
                 cast(timezone('America/New_York', start_time_utc) as date)
    ),
    night_agg as (
        select issuance_id, digest, fetched_at_utc, observed_at, issued_at_utc, generated_at_utc,
            cast(timezone('America/New_York', end_time_utc) as date) as local_date,
            min(temperature_f) as low_f
        from periods where not is_daytime
        group by issuance_id, digest, fetched_at_utc, observed_at, issued_at_utc, generated_at_utc,
                 cast(timezone('America/New_York', end_time_utc) as date)
    ),
    days as (
        select coalesce(d.issuance_id, n.issuance_id) as issuance_id,
               coalesce(d.digest, n.digest) as digest,
               coalesce(d.fetched_at_utc, n.fetched_at_utc) as fetched_at_utc,
               coalesce(d.observed_at, n.observed_at) as observed_at,
               coalesce(d.issued_at_utc, n.issued_at_utc) as issued_at_utc,
               coalesce(d.generated_at_utc, n.generated_at_utc) as generated_at_utc,
               coalesce(d.local_date, n.local_date) as local_date,
               d.high_f as high_f,
               n.low_f as low_f
        from day_agg d full outer join night_agg n
          on d.issuance_id = n.issuance_id and d.local_date = n.local_date
    )
    select issuance_id, issued_at_utc, fetched_at_utc as loaded_at, observed_at, high_f, low_f
    from days
    """
    with duckdb.connect(':memory:') as connection:
        connection.execute("SET TimeZone = 'UTC'")
        escaped = str(db_path).replace("'", "''")
        connection.execute(f"ATTACH '{escaped}' AS src (READ_ONLY)")
        params = [target_date]
        cutoff = ''
        if indexed_by is not None:
            cutoff = " AND loaded_at <= TIMESTAMPTZ ?"
            params.append(indexed_by.astimezone(timezone.utc).isoformat())
        # Need target_date filter on local_date, but local_date not selected. Add it.
        # Re-run with local_date included.
        sql2 = sql.replace(
            "    select issuance_id, issued_at_utc, fetched_at_utc as loaded_at, observed_at, high_f, low_f\n    from days",
            "    select issuance_id, issued_at_utc, fetched_at_utc as loaded_at, observed_at, high_f, low_f, local_date\n    from days")
        rows = connection.execute(
            "SELECT issuance_id, issued_at_utc, loaded_at, observed_at, high_f, low_f "
            "FROM (" + sql2 + ") x WHERE local_date = ?" + cutoff, [target_date] + ([indexed_by.astimezone(timezone.utc).isoformat()] if indexed_by is not None else [])).fetchall()
    if not rows:
        return None
    # complete pair beats newer incomplete
    complete = [r for r in rows if r[4] is not None and r[5] is not None]
    pool = complete if complete else rows
    chosen = max(pool, key=lambda r: (r[2], r[1]))
    issuance_id, issued_at, loaded_at, observed_at, high_f, low_f = chosen
    usable_at = None
    if observed_at is not None:
        usable_at = max(loaded_at, observed_at)
    return {
        'high_f': high_f,
        'morning_low_f': low_f,
        'weather_available_at': loaded_at,
        'weather_usable_at': usable_at,
        'issuance_id': issuance_id,
        'update_time': issued_at,
        'loaded_at': loaded_at,
        'observed_at': observed_at,
    }
def annotate_alert_interval(start: datetime, end: datetime, text: str, first_date: date, last_date: date) -> tuple[Alert, ...]:
    """Annotate an explicit half-open interval over inclusive New York dates."""
    if start.utcoffset() is None or end.utcoffset() is None:
        raise ValueError('alert interval endpoints must be timezone-aware')
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    if start_utc >= end_utc:
        raise ValueError('alert interval must be nonempty')
    if first_date > last_date:
        raise ValueError('first_date must not follow last_date')
    first = max(first_date, start_utc.astimezone(_NEW_YORK).date())
    last = min(last_date, (end_utc - timedelta(microseconds=1)).astimezone(_NEW_YORK).date())
    if first > last:
        return ()
    return tuple(Alert(first + timedelta(days=offset), text)
                 for offset in range((last - first).days + 1))
class NwsBwiIssuance:
    def __init__(self, high_f, morning_low_f, weather_available_at, weather_usable_at,
                 issuance_id, update_time, generated_at=None, loaded_at=None, observed_at=None,
                 digest=None, periods=None):
        self.high_f = high_f
        self.morning_low_f = morning_low_f
        self.weather_available_at = weather_available_at
        self.weather_usable_at = weather_usable_at
        self.issuance_id = issuance_id
        self.update_time = update_time
        self.generated_at = generated_at
        self.loaded_at = loaded_at if loaded_at is not None else weather_available_at
        self.observed_at = observed_at
        self.digest = digest
        self.periods = periods

    def __getitem__(self, key):
        if isinstance(key, int):
            order = ('high_f', 'morning_low_f', 'weather_available_at', 'weather_usable_at',
                     'issuance_id', 'update_time')
            return getattr(self, order[key])
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except Exception:
            return default

    def keys(self):
        return ('high_f', 'morning_low_f', 'weather_available_at', 'weather_usable_at',
                'issuance_id', 'update_time')

    def as_dict(self):
        return {k: getattr(self, k) for k in self.keys()}

    def __iter__(self):
        for k in self.keys():
            yield getattr(self, k)


NwsBwiForecast = NwsBwiIssuance
NwsIssuance = NwsBwiIssuance
WeatherIssuance = NwsBwiIssuance


def _resolve_nws_args(args, kwargs):
    database = kwargs.pop('database', kwargs.pop('temperature_database', kwargs.pop('temperature_db',
               kwargs.pop('db', kwargs.pop('path', None)))))
    target_date = kwargs.pop('target_date', kwargs.pop('date', kwargs.pop('day', None)))
    cutoff = kwargs.pop('indexed_by', kwargs.pop('cutoff', kwargs.pop('as_of', kwargs.pop('input_cutoff', None))))
    for value in args:
        if isinstance(value, (str, Path)):
            if database is None:
                database = value
        elif isinstance(value, datetime) and not isinstance(value, date):
            if cutoff is None:
                cutoff = value
        elif isinstance(value, date):
            if target_date is None:
                target_date = value
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)
    if isinstance(cutoff, str):
        cutoff = datetime.fromisoformat(cutoff)
    return database, target_date, cutoff


import hashlib
import json
from pathlib import Path

def load_nws_bwi_issuance(*args, **kwargs):
    database, target_date, cutoff = _resolve_nws_args(args, kwargs)
    if database is None or target_date is None:
        raise ValueError('database and target_date are required')
    db_path = Path(database)
    if not db_path.exists():
        return None
    if cutoff is not None and cutoff.utcoffset() is None:
        raise ValueError('cutoff must be timezone-aware')
    with duckdb.connect(str(db_path), read_only=True) as conn:
        try:
            rows = conn.execute("""
                SELECT b.digest, b.loaded_at, b.committed, b.observed_at, r.payload
                FROM raw.records r
                JOIN raw.batches b USING (source, dataset, digest)
                WHERE r.source = 'nws' AND r.dataset = 'forecast_bwi' AND b.committed
                ORDER BY b.loaded_at
            """).fetchall()
        except duckdb.CatalogException:
            return None
    by_digest = {}
    for digest, loaded_at, committed, observed_at, payload in rows:
        by_digest.setdefault(digest, {'loaded_at': loaded_at, 'observed_at': observed_at,
                                     'payload': payload})
    candidates = []
    for digest, info in by_digest.items():
        loaded_at = info['loaded_at']
        if cutoff is not None and (loaded_at is None or loaded_at > cutoff.astimezone(timezone.utc)):
            continue
        try:
            payload = json.loads(info['payload']) if isinstance(info['payload'], str) else info['payload']
            props = payload['properties']
            periods = props['periods']
        except Exception:
            continue
        update_time = datetime.fromisoformat(props['updateTime'].replace('Z', '+00:00'))
        generated_at = datetime.fromisoformat(props['generatedAt'].replace('Z', '+00:00'))
        high_f = None
        low_f = None
        for p in periods:
            if not isinstance(p, dict):
                continue
            try:
                is_day = bool(p['isDaytime'])
                temp = float(p['temperature'])
                start = datetime.fromisoformat(p['startTime'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(p['endTime'].replace('Z', '+00:00'))
            except (KeyError, ValueError, TypeError):
                continue
            local_start = start.astimezone(_NEW_YORK).date()
            local_end = end.astimezone(_NEW_YORK).date()
            if is_day and local_start == target_date:
                high_f = temp if high_f is None else max(high_f, temp)
            if (not is_day) and local_end == target_date:
                low_f = temp if low_f is None else min(low_f, temp)
        issuance_id = hashlib.sha256(
            (update_time.astimezone(timezone.utc).isoformat() + '|' +
             generated_at.astimezone(timezone.utc).isoformat() + '|' +
             loaded_at.astimezone(timezone.utc).isoformat() + '|' + digest).encode()).hexdigest()
        observed_at = info['observed_at']
        usable = None
        if observed_at is not None and loaded_at is not None:
            usable = max(loaded_at, observed_at)
        candidates.append({
            'digest': digest,
            'loaded_at': loaded_at,
            'observed_at': observed_at,
            'update_time': update_time,
            'generated_at': generated_at,
            'high_f': high_f,
            'low_f': low_f,
            'complete': high_f is not None and low_f is not None,
            'issuance_id': issuance_id,
            'periods': len(periods),
        })
    if not candidates:
        return None
    complete = [c for c in candidates if c['complete']]
    pool = complete if complete else candidates
    chosen = max(pool, key=lambda c: (c['loaded_at'], c['update_time']))
    if not chosen['complete']:
        return None
    usable = None
    if chosen['observed_at'] is not None and chosen['loaded_at'] is not None:
        usable = max(chosen['loaded_at'], chosen['observed_at'])
    return NwsBwiIssuance(
        high_f=chosen['high_f'],
        morning_low_f=chosen['low_f'],
        weather_available_at=chosen['loaded_at'],
        weather_usable_at=usable,
        issuance_id=chosen['issuance_id'],
        update_time=chosen['update_time'],
        generated_at=chosen['generated_at'],
        loaded_at=chosen['loaded_at'],
        observed_at=chosen['observed_at'],
        digest=chosen['digest'],
        periods=chosen['periods'],
    )


load_nws_bwi_forecast = load_nws_bwi_issuance
load_pinned_nws_bwi = load_nws_bwi_issuance
load_nws_bwi = load_nws_bwi_issuance
load_bwi_issuance = load_nws_bwi_issuance
load_weather_issuance = load_nws_bwi_issuance
load_nws_forecast_bwi = load_nws_bwi_issuance