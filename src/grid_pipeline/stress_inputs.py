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
        demand_sql = _model_sql('cleaned/eia_pjm_hourly_demand.sql', raw_refs)
        temperature_sql = _model_sql('cleaned/ncei_bwi_daily_temps.sql', raw_refs)
        mart_sql = _model_sql('marts/mart_day_history.sql', {
            "{{ ref('eia_pjm_hourly_demand') }}": 'clean_demand',
            "{{ ref('ncei_bwi_daily_temps') }}": 'clean_temperature',
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


def annotate_alert_interval(start: datetime, end: datetime, text: str,
                            first_date: date, last_date: date) -> tuple[Alert, ...]:
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
