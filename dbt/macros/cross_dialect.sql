{#-
  Cross-dialect macros (S5 dialect pass, 2026-11-06).

  The models are single-source for both targets: `local` (DuckDB) and
  `supabase` (Postgres). Every macro here dispatches on the adapter:
  the DuckDB side emits the original DuckDB construct unchanged, the
  Postgres side emits either portable SQL or a call to an exception-safe
  plpgsql helper installed by the install_pg_helpers on-run-start hook
  (schema grid_dbt_helpers, postgres target only).

  Semantic bar for every macro: identical results on both engines for the
  same input, including NULL-on-unparseable (never an error) for the
  try_* family. See s5-deployment/dialect-pass-log.md for the per-macro
  parity argument and the named residual divergences (exotic string
  shapes outside the provider alphabet: hex / underscore-separated /
  non-ISO date strings).
-#}

{# ------------------------------------------------------------------ #}
{# try_cast(expr as T) — T in {double, date, timestamptz, integer,     #}
{# bigint, boolean}. Postgres has no try_cast; the helpers return NULL #}
{# on any cast failure and emulate DuckDB's double-mediated rounding   #}
{# for integer/bigint and its boolean literal set.                     #}
{# ------------------------------------------------------------------ #}
{% macro try_cast(expr, type) %}
  {{ adapter.dispatch('try_cast', 'grid_project')(expr, type) }}
{% endmacro %}

{% macro default__try_cast(expr, type) %}
  try_cast({{ expr }} as {{ type }})
{% endmacro %}

{% macro postgres__try_cast(expr, type) %}
  grid_dbt_helpers.try_cast_{{ type }}({{ expr }})
{% endmacro %}

{# ------------------------------------------------------------------ #}
{# json_text(expr, 'a.b.c') — text extraction at a dot path.           #}
{# DuckDB: expr ->> '$.a.b.c' (or ->> 'key' for a single key).         #}
{# Postgres (jsonb): expr #>> '{a,b,c}' (or ->> 'key').                #}
{# Both return text / NULL for a missing or JSON-null leaf.            #}
{# ------------------------------------------------------------------ #}
{% macro json_text(expr, path) %}
  {{ adapter.dispatch('json_text', 'grid_project')(expr, path) }}
{% endmacro %}

{% macro default__json_text(expr, path) %}
  {%- if '.' in path -%}
    {{ expr }} ->> '$.{{ path }}'
  {%- else -%}
    {{ expr }} ->> '{{ path }}'
  {%- endif -%}
{% endmacro %}

{% macro postgres__json_text(expr, path) %}
  {%- if '.' in path -%}
    {{ expr }} #>> '{ {{- path.split('.') | join(',') -}} }'
  {%- else -%}
    {{ expr }} ->> '{{ path }}'
  {%- endif -%}
{% endmacro %}

{# ------------------------------------------------------------------ #}
{# json_array_elements(expr, 'a.b') — lateral unnest of a JSON array   #}
{# at a dot path, aliased as p(value) so p.value ->> 'k' works via     #}
{# json_text on both engines (json_each on DuckDB,                     #}
{# jsonb_array_elements on Postgres).                                 #}
{# ------------------------------------------------------------------ #}
{% macro json_array_elements(expr, path) %}
  {{ adapter.dispatch('json_array_elements', 'grid_project')(expr, path) }}
{% endmacro %}

{% macro default__json_array_elements(expr, path) %}
  json_each({{ expr }}, '$.{{ path }}') as p(key, value)
{% endmacro %}

{% macro postgres__json_array_elements(expr, path) %}
  jsonb_array_elements({{ expr }} #> '{ {{- path.split('.') | join(',') -}} }') as p(value)
{% endmacro %}

{# ------------------------------------------------------------------ #}
{# try_strptime(expr, fmt) / try_strptime(expr, [fmt, ...])            #}
{# DuckDB try_strptime returns a naive TIMESTAMP, NULL on no match,    #}
{# trying list formats in order, and requires a full-string match.     #}
{# Postgres: grid_dbt_helpers.try_parse_timestamp checks a regex       #}
{# full-match per format (to_timestamp alone ignores trailing          #}
{# characters, which would diverge), then converts with                #}
{# to_timestamp(...)::timestamp — the ::timestamp cast drops the       #}
{# zone by converting to session-local wall time, which is exactly     #}
{# the parsed fields, so the result is the naive timestamp DuckDB      #}
{# returns, independent of the session TimeZone setting.               #}
{# Format strings are translated at compile time: %Y-%m-%dT%H ->       #}
{# YYYY-MM-DD"T"HH24 (literal letter runs are double-quoted, as         #}
{# to_timestamp requires).                                             #}
{# ------------------------------------------------------------------ #}
{% macro try_strptime(expr, formats) %}
  {{ adapter.dispatch('try_strptime', 'grid_project')(expr, formats) }}
{% endmacro %}

{% macro default__try_strptime(expr, formats) %}
  {%- set fmts = [formats] if formats is string else formats -%}
  try_strptime({{ expr }}, [{% for f in fmts %}'{{ f }}'{% if not loop.last %}, {% endif %}{% endfor %}])
{% endmacro %}

{% macro postgres__try_strptime(expr, formats) %}
  {%- set fmts = [formats] if formats is string else formats -%}
  grid_dbt_helpers.try_parse_timestamp(
    {{ expr }},
    array[{% for f in fmts %}'{{ pg_strptime_format(f) }}'{% if not loop.last %}, {% endif %}{% endfor %}],
    array[{% for f in fmts %}'{{ strptime_regex(f) }}'{% if not loop.last %}, {% endif %}{% endfor %}]
  )
{% endmacro %}

{# Translate one strptime format to a Postgres to_timestamp format. #}
{# Literal letter runs are double-quoted (to_timestamp requirement);    #}
{# other literal characters pass through. ns.skip consumes the second  #}
{# character of each two-char % token.                                 #}
{% macro pg_strptime_format(fmt) %}
  {%- set tokens = {'%Y': 'YYYY', '%m': 'MM', '%d': 'DD', '%H': 'HH24', '%M': 'MI', '%S': 'SS', '%%': '%'} -%}
  {%- set letters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ' -%}
  {%- set ns = namespace(out='', literal='', skip=false) -%}
  {%- for i in range(fmt | length) -%}
    {%- if ns.skip -%}
      {%- set ns.skip = false -%}
    {%- elif fmt[i:i+2] in tokens -%}
      {%- if ns.literal -%}
        {%- set ns.out = ns.out ~ '"' ~ ns.literal ~ '"' -%}
        {%- set ns.literal = '' -%}
      {%- endif -%}
      {%- set ns.out = ns.out ~ tokens[fmt[i:i+2]] -%}
      {%- set ns.skip = true -%}
    {%- elif fmt[i] in letters -%}
      {%- set ns.literal = ns.literal ~ fmt[i] -%}
    {%- else -%}
      {%- if ns.literal -%}
        {%- set ns.out = ns.out ~ '"' ~ ns.literal ~ '"' -%}
        {%- set ns.literal = '' -%}
      {%- endif -%}
      {%- set ns.out = ns.out ~ fmt[i] -%}
    {%- endif -%}
  {%- endfor -%}
  {%- if ns.literal -%}
    {%- set ns.out = ns.out ~ '"' ~ ns.literal ~ '"' -%}
  {%- endif -%}
  {{- ns.out -}}
{% endmacro %}

{# Translate one strptime format to a full-match regex (used as ^...$). #}
{% macro strptime_regex(fmt) %}
  {%- set tokens = {'%Y': '[0-9]{4}', '%m': '[0-9]{1,2}', '%d': '[0-9]{1,2}', '%H': '[0-9]{1,2}', '%M': '[0-9]{1,2}', '%S': '[0-9]{1,2}', '%%': '%'} -%}
  {%- set ns = namespace(out='', skip=false) -%}
  {%- for i in range(fmt | length) -%}
    {%- if ns.skip -%}
      {%- set ns.skip = false -%}
    {%- elif fmt[i:i+2] in tokens -%}
      {%- set ns.out = ns.out ~ tokens[fmt[i:i+2]] -%}
      {%- set ns.skip = true -%}
    {%- elif fmt[i] in '.*+?()[]{}^$|\\' -%}
      {%- set ns.out = ns.out ~ '\\' ~ fmt[i] -%}
    {%- else -%}
      {%- set ns.out = ns.out ~ fmt[i] -%}
    {%- endif -%}
  {%- endfor -%}
  {{- ns.out -}}
{% endmacro %}

{# ------------------------------------------------------------------ #}
{# is_finite(x) — DuckDB isfinite(); Postgres has no such function     #}
{# for double precision. NaN fails x = x; infinities compare equal     #}
{# to the 'Infinity' literals. NULL in -> NULL out on both engines.    #}
{# ------------------------------------------------------------------ #}
{% macro is_finite(expr) %}
  {{ adapter.dispatch('is_finite', 'grid_project')(expr) }}
{% endmacro %}

{% macro default__is_finite(expr) %}
  isfinite({{ expr }})
{% endmacro %}

{% macro postgres__is_finite(expr) %}
  ({{ expr }} = {{ expr }}
   and {{ expr }} <> 'Infinity'::double precision
   and {{ expr }} <> '-Infinity'::double precision)
{% endmacro %}

{# ------------------------------------------------------------------ #}
{# sha256_hex(x) — lowercase hex digest of the text's UTF-8 bytes.     #}
{# DuckDB sha256(varchar) already returns hex; Postgres sha256()       #}
{# returns bytea, so encode(..., 'hex').                               #}
{# ------------------------------------------------------------------ #}
{% macro sha256_hex(expr) %}
  {{ adapter.dispatch('sha256_hex', 'grid_project')(expr) }}
{% endmacro %}

{% macro default__sha256_hex(expr) %}
  sha256({{ expr }})
{% endmacro %}

{% macro postgres__sha256_hex(expr) %}
  encode(sha256(({{ expr }})::bytea), 'hex')
{% endmacro %}

{# ------------------------------------------------------------------ #}
{# date_diff_hour(a, b) — whole hours from a to b.                     #}
{# DuckDB date_diff('hour', a, b) counts hour boundaries; the epoch    #}
{# form counts whole elapsed hours. They agree whenever both           #}
{# arguments are hour-aligned, which holds at the only call site       #}
{# (local midnights produced by timezone(...) in mart_day_history,     #}
{# giving exact 23/24/25-hour days).                                   #}
{# ------------------------------------------------------------------ #}
{% macro date_diff_hour(start_expr, end_expr) %}
  {{ adapter.dispatch('date_diff_hour', 'grid_project')(start_expr, end_expr) }}
{% endmacro %}

{% macro default__date_diff_hour(start_expr, end_expr) %}
  date_diff('hour', {{ start_expr }}, {{ end_expr }})
{% endmacro %}

{% macro postgres__date_diff_hour(start_expr, end_expr) %}
  cast(extract(epoch from ({{ end_expr }} - {{ start_expr }})) / 3600 as bigint)
{% endmacro %}

{# ------------------------------------------------------------------ #}
{# isodow_of(d) — ISO day of week, Monday=1 .. Sunday=7.               #}
{# ------------------------------------------------------------------ #}
{% macro isodow_of(expr) %}
  {{ adapter.dispatch('isodow_of', 'grid_project')(expr) }}
{% endmacro %}

{% macro default__isodow_of(expr) %}
  isodow({{ expr }})
{% endmacro %}

{% macro postgres__isodow_of(expr) %}
  extract(isodow from {{ expr }})
{% endmacro %}

{# ------------------------------------------------------------------ #}
{# install_pg_helpers — on-run-start hook (dbt_project.yml).           #}
{# Postgres target only: installs the exception-safe plpgsql helpers   #}
{# the postgres__ macros call. Idempotent (CREATE OR REPLACE).         #}
{# DuckDB target: no-op.                                               #}
{# ------------------------------------------------------------------ #}
{% macro install_pg_helpers() %}
  {% if execute and target.type == 'postgres' %}
    {% call statement('install_pg_helpers', fetch_result=False) %}
      create schema if not exists grid_dbt_helpers;

      create or replace function grid_dbt_helpers.try_cast_double(p text)
      returns double precision language plpgsql immutable as $$
      begin
        if p is null then return null; end if;
        begin
          return p::double precision;
        exception when others then
          return null;
        end;
      end $$;

      create or replace function grid_dbt_helpers.try_cast_integer(p text)
      returns integer language plpgsql immutable as $$
      declare v numeric;
      begin
        if p is null then return null; end if;
        begin
          return p::integer;
        exception when others then
          -- DuckDB parses integer strings through a double and rounds
          -- (half away from zero): '42.0' -> 42, '42.5' -> 43, '1e5' -> 100000.
          -- round(numeric) is half-away-from-zero, matching DuckDB;
          -- round(double) would be banker's rounding and is NOT used.
          begin
            v := round(p::numeric);
            if v < -2147483648 or v > 2147483647 then return null; end if;
            return v::integer;
          exception when others then
            return null;
          end;
        end;
      end $$;

      create or replace function grid_dbt_helpers.try_cast_bigint(p text)
      returns bigint language plpgsql immutable as $$
      declare v numeric;
      begin
        if p is null then return null; end if;
        begin
          return p::bigint;
        exception when others then
          begin
            v := round(p::numeric);
            if v < -9223372036854775808 or v > 9223372036854775807 then return null; end if;
            return v::bigint;
          exception when others then
            return null;
          end;
        end;
      end $$;

      create or replace function grid_dbt_helpers.try_cast_date(p text)
      returns date language plpgsql immutable as $$
      begin
        if p is null then return null; end if;
        -- ISO shape guard: Postgres' native date parser also accepts
        -- MDY strings like '10/01/2026' (DateStyle-dependent) that
        -- DuckDB's try_cast rejects; restrict to the ISO alphabet both
        -- engines parse identically. Impossible dates (month 13,
        -- Feb 30) still fail the cast below and become NULL.
        if p !~ '^\s*[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}' then return null; end if;
        begin
          return p::date;
        exception when others then
          return null;
        end;
      end $$;

      create or replace function grid_dbt_helpers.try_cast_timestamptz(p text)
      returns timestamp with time zone language plpgsql immutable as $$
      begin
        if p is null then return null; end if;
        if p !~ '^\s*[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}' then return null; end if;
        begin
          return p::timestamp with time zone;
        exception when others then
          return null;
        end;
      end $$;

      create or replace function grid_dbt_helpers.try_cast_boolean(p text)
      returns boolean language plpgsql immutable as $$
      declare v text;
      begin
        if p is null then return null; end if;
        -- DuckDB's boolean literal set; Postgres additionally accepts
        -- 'on'/'off' and unique prefixes like 'tr', which DuckDB
        -- rejects, so whitelist first, then cast.
        v := lower(btrim(p));
        if v not in ('true', 'false', 't', 'f', 'y', 'n', 'yes', 'no', '1', '0') then
          return null;
        end if;
        return v::boolean;
      end $$;

      create or replace function grid_dbt_helpers.try_parse_timestamp(
        p text, p_fmts text[], p_res text[])
      returns timestamp language plpgsql immutable as $$
      declare i int; v timestamp;
      begin
        if p is null then return null; end if;
        for i in 1 .. array_length(p_fmts, 1) loop
          -- Full-match regex first: to_timestamp alone ignores trailing
          -- characters, DuckDB try_strptime does not.
          if p ~ ('^' || p_res[i] || '$') then
            begin
              v := to_timestamp(p, p_fmts[i])::timestamp;
              return v;
            exception when others then
              -- Shape matched but the value is impossible (month 13,
              -- Feb 30): fall through to the next format, as DuckDB does.
            end;
          end if;
        end loop;
        return null;
      end $$;
    {% endcall %}
  {% endif %}
  {{ return('') }}
{% endmacro %}
