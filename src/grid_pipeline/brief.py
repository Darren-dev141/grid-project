"""Render the daily brief: ``site/index.html`` plus the issue-comment text.

This is step 8 of ``grid daily`` in ``docs/architecture-s3-s7.md``. The brief
renders exactly what the existing pipeline already produces — one forecast
(from ``stress.forecast`` over ``stress_inputs``) plus freshness facts — and
nothing else: no new claims, metrics, or dashboard scope.

Deviations from the architecture doc's idealised signatures, forced by the
code that actually exists today:

- There is no ``scoring`` module and no ``Report`` type; ``freshness.py`` is
  the legacy publish-snapshot checker. Freshness here is therefore the pair
  of booleans the forecast itself consumes (``Features.load_fresh`` /
  ``Features.weather_fresh``), derived with the same rules
  ``scripts/issue_stress.py`` uses: load is fresh when the latest completed
  peak (target - 2 days, per the Nov 5 same-day ruling) is present, complete,
  first-recorded and finite; weather is fresh when a pinned NWS BWI issuance
  for the target date carries a complete high/low pair.
- There is no ``features.load``; history and target weather come from
  ``stress_inputs.load_first_recorded_history`` and
  ``stress_inputs.load_nws_bwi_forecast``.
- The forecast is computed in ``retrospective`` mode (the mode
  ``scripts/diagnose_s3c.py`` uses for reconstruction). Prospective issuance
  stays with the issuance path and the ledger; this renderer never appends
  receipts and never invents issue-time provenance.

All ledger reads go through ``grid_pipeline.ledger`` (the only module allowed
to open ledger paths): the definition via ``ledger.read_definition`` and the
receipt listing via ``ledger.receipt_paths`` + ``ledger.read_content``.
The issue comment lists, for the brief's target date, each receipt's path
and full sha256 (architecture step 8).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import html
import json
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb

from grid_pipeline import ledger, md_geo
from grid_pipeline.model import Features, Forecast
from grid_pipeline.stress import forecast as stress_forecast, parse_definition
from grid_pipeline.stress_inputs import load_first_recorded_history, load_nws_bwi_forecast

ET = ZoneInfo('America/New_York')
GEOGRAPHY = 'PJM-wide call, Maryland weather'
DEFINITION_VERSION = 'stress-index-v1'


@dataclass(frozen=True)
class Brief:
    """Rendered brief: the page and the issue-comment text."""
    html: str
    comment_md: str


@dataclass(frozen=True)
class BriefFacts:
    """Freshness and data-as-of facts shown alongside the forecast."""
    load_fresh: bool
    weather_fresh: bool
    latest_completed_peak: date
    latest_completed_present: bool
    history_days: int
    history_last_date: date | None
    data_as_of: date | None
    load_last_hour_utc: datetime | None
    weather_update_time: datetime | None
    target_high_f: float | None
    target_morning_low_f: float | None


@dataclass(frozen=True)
class RenderedBrief:
    forecast: Forecast
    facts: BriefFacts
    brief: Brief
    index_path: Path
    comment_path: Path


def _fmt_mw(value: float | None) -> str:
    return '—' if value is None else f'{value:,.1f} MW'


def _fmt_time(value: datetime | None) -> str:
    return '—' if value is None else value.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def _receipt_listing(root: Path, target_date: date) -> list[tuple[str, str]]:
    """Receipts for ``target_date`` as (display path, full sha256), via ledger only."""
    listing = []
    forecasts_dir = root / 'forecasts'
    if not forecasts_dir.exists():
        return listing
    for path in ledger.receipt_paths(root):
        raw = ledger.read_content(path)
        try:
            payload = json.loads(raw)
        except ValueError:
            continue
        if payload.get('target_date') != target_date.isoformat():
            continue
        relative = path.relative_to(root).as_posix()
        display = f'{root.name}/{relative}' if root.name else relative
        listing.append((display, sha256(raw).hexdigest()))
    return listing


LEVEL_STYLE = {
    # Beat the Grid level palette, in God's Eye View's design language
    # (near-black glass, electric cyan accent, cockpit amber).
    'calm': ('#00d4ff', 0.30),
    'watch': ('#ffb800', 0.38),
    'strained': ('#ff7a1a', 0.46),
    'severe': ('#ff4545', 0.55),
}
NO_CALL_COLOR = '#5b6b73'


def _map_script(level: str | None) -> str:
    """Leaflet map: Maryland counties, BGE footprint lit at the call level.

    The call is PJM-wide; the lit counties are the BGE home territory at
    county resolution (md_geo). Zoom goes to street level so a reader can
    find their own neighborhood inside (or outside) the lit area.

    CARTO's dark basemap now serves an "API key required" tile without a
    key. OpenStreetMap tiles need no key; the tile pane is inverted so the
    page stays dark. Zoom sits on the right so it does not cover the call.
    """
    color, fill = LEVEL_STYLE.get(level or '', (NO_CALL_COLOR, 0.12))
    counties = json.dumps(md_geo.MD_COUNTIES, separators=(',', ':'))
    return f'''<script>
var renderer = L.svg();
var map = L.map('map', {{ scrollWheelZoom: true, minZoom: 7, maxZoom: 16, zoomControl: false, renderer: renderer }});
L.control.zoom({{ position: 'topright' }}).addTo(map);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  maxZoom: 19
}}).addTo(map);
// Give the SVG renderer clip bounds before any county polygon is projected.
// Adding polygons in the same turn as the first fitBounds leaves the renderer
// off-map and Leaflet throws in _clipPoints, so the counties never draw.
map.setView([39.05, -76.75], 8);
map.addLayer(renderer);
var counties = {counties};
var levelColor = '{color}', levelFill = {fill};
function countyStyle(feature) {{
  var bge = feature.properties.bge;
  if (bge === 'core') return {{ color: levelColor, weight: 1.4, fillColor: levelColor, fillOpacity: levelFill }};
  if (bge === 'partial') return {{ color: levelColor, weight: 1, fillColor: levelColor, fillOpacity: levelFill * 0.45 }};
  return {{ color: 'rgba(232,234,237,0.25)', weight: 0.7, fillColor: '#e8eaed', fillOpacity: 0.04 }};
}}
var glow = L.geoJSON(counties, {{ style: function(f) {{
  var s = countyStyle(f); if (f.properties.bge === 'none') return {{ opacity: 0, fillOpacity: 0 }};
  return {{ color: levelColor, weight: 7, opacity: 0.28, fillOpacity: 0 }};
}} }}).addTo(map);
var layer = L.geoJSON(counties, {{ style: countyStyle,
  onEachFeature: function(f, l) {{ l.bindTooltip(f.properties.name + (f.properties.bge === 'core' ? ' — BGE' : f.properties.bge === 'partial' ? ' — BGE (part)' : '')); }}
}}).addTo(map);
L.circleMarker([39.1774, -76.6684], {{ radius: 5, color: '#e8eaed', weight: 1.5, fillColor: '#00d4ff', fillOpacity: 0.9 }})
  .addTo(map).bindTooltip('BWI — weather point');
map.fitBounds(layer.getBounds().pad(0.04));
</script>'''


def render(forecast: Forecast, facts: BriefFacts,
           receipts: list[tuple[str, str]], *, generated_at: datetime) -> Brief:
    """Render one forecast plus its freshness facts. Pure: no IO."""
    esc = html.escape
    target = forecast.target_date.isoformat()
    generated = _fmt_time(generated_at)
    no_call = forecast.no_call_reason is not None
    if no_call:
        headline = 'No call'
        hero_html = (f'<p class="level">No call — {esc(forecast.no_call_reason)}</p>\n'
                     '<p class="noclaim">No peak demand, peak hour, or stress level is claimed for '
                     'this date.</p>')
        call_lines = [f'Call: **No call** — `{forecast.no_call_reason}`',
                      'Peak demand / peak hour / level: not claimed.']
        stats_html = ''
        bar_html = ''
    else:
        headline = f'Stress level: {forecast.level}'
        thresholds = forecast.thresholds_mw or (None, None, None)
        hero_html = f'<p class="level">Stress level: {esc(forecast.level or "")}</p>'
        stats_html = (
            '<div class="stats">\n'
            f'<div class="stat"><span class="stat-label">Peak demand</span>'
            f'<span class="stat-value">Peak demand: {esc(_fmt_mw(forecast.peak_mw))}</span></div>\n'
            f'<div class="stat"><span class="stat-label">Peak hour</span>'
            f'<span class="stat-value">Peak hour ending: {forecast.peak_hour_ending} (local)</span></div>\n'
            '</div>')
        call_lines = [f'Call: **{forecast.level}**',
                      f'Peak demand: {_fmt_mw(forecast.peak_mw)}',
                      f'Peak hour ending: {forecast.peak_hour_ending} (local)']
        bar_html = ''
        if None not in thresholds and forecast.peak_mw:
            watch, strained, severe = thresholds
            cap = severe * 1.15
            def pct(v):
                return max(0.0, min(100.0, v / cap * 100.0))
            bar_html = (
                '<div class="bar-wrap"><div class="bar">'
                f'<div class="seg seg-calm" style="width:{pct(watch):.1f}%"></div>'
                f'<div class="seg seg-watch" style="width:{pct(strained) - pct(watch):.1f}%"></div>'
                f'<div class="seg seg-strained" style="width:{pct(severe) - pct(strained):.1f}%"></div>'
                f'<div class="seg seg-severe" style="width:{100.0 - pct(severe):.1f}%"></div>'
                f'<div class="peak-marker" style="left:{pct(forecast.peak_mw):.1f}%"></div>'
                '</div>'
                f'<p class="thresholds">Thresholds: watch {_fmt_mw(watch)}, '
                f'strained {_fmt_mw(strained)}, severe {_fmt_mw(severe)}</p></div>')
    drivers = ''
    if facts.target_high_f is not None or facts.target_morning_low_f is not None:
        drivers = (f'<li>Forecast high: {facts.target_high_f} F; '
                   f'morning low: {facts.target_morning_low_f} F</li>\n')
    alerts_html = ''
    if forecast.alerts:
        items = '\n'.join(f'<li>{esc(text)}</li>' for text in forecast.alerts)
        alerts_html = f'<section class="panel"><h2>Alerts (annotation only)</h2>\n<ul>\n{items}\n</ul></section>\n'
    load_state = 'fresh' if facts.load_fresh else 'stale'
    weather_state = 'fresh' if facts.weather_fresh else 'stale'
    completed = ('present' if facts.latest_completed_present else 'missing')
    level_key = forecast.level if not no_call else None
    level_color = LEVEL_STYLE.get(level_key or '', (NO_CALL_COLOR, 0.12))[0]
    map_html = _map_script(level_key)
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Beat the Grid — {target}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root {{ --bg: #0a0a0f; --glass: rgba(12,12,20,0.72); --border: rgba(255,255,255,0.08);
  --accent: #00d4ff; --text: #e8eaed; --secondary: rgba(232,234,237,0.5); --dim: rgba(232,234,237,0.3);
  --level: {level_color}; --mono: 'JetBrains Mono','SF Mono','Fira Code',monospace;
  --sans: 'Inter',-apple-system,BlinkMacSystemFont,system-ui,sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font-family: var(--sans); line-height: 1.5; }}
.wrap {{ max-width: 68rem; margin: 0 auto; padding: 1.25rem 1rem 3rem; }}
header.hud {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.5rem 1.25rem; padding: 0.75rem 0 1rem; }}
.wordmark {{ font-family: var(--mono); font-weight: 600; font-size: 0.8rem; letter-spacing: 0.22em;
  text-transform: uppercase; color: var(--accent); text-shadow: 0 0 12px rgba(0,212,255,0.4); }}
h1 {{ font-size: 1.35rem; margin: 0; font-weight: 650; }}
.meta {{ color: var(--secondary); font-size: 0.9rem; }}
.map-panel {{ position: relative; border: 1px solid var(--border); border-radius: 16px; overflow: hidden;
  background: var(--glass); box-shadow: 0 0 42px color-mix(in srgb, var(--level) 22%, transparent); }}
#map {{ height: min(62vh, 560px); min-height: 340px; background: #0a0a0f; }}
.hero {{ position: absolute; top: 14px; left: 14px; z-index: 500; background: var(--glass);
  border: 1px solid var(--border); border-radius: 12px; padding: 0.7rem 1rem; backdrop-filter: blur(8px); }}
.hero .level {{ font-family: var(--mono); font-size: 1.25rem; font-weight: 700; margin: 0; color: var(--level);
  text-shadow: 0 0 14px color-mix(in srgb, var(--level) 55%, transparent); }}
.hero .noclaim {{ margin: 0.25rem 0 0; color: var(--secondary); font-size: 0.88rem; max-width: 22rem; }}
.map-caption {{ position: absolute; right: 14px; bottom: 14px; z-index: 500; max-width: 19rem;
  background: var(--glass); border: 1px solid var(--border); border-radius: 12px; padding: 0.55rem 0.8rem;
  color: var(--secondary); font-size: 0.8rem; backdrop-filter: blur(8px); }}
.leaflet-container {{ font-family: var(--sans); background: #0a0a0f; }}
.leaflet-tile-pane {{ filter: invert(100%) hue-rotate(180deg) brightness(0.9) contrast(0.95); }}
.leaflet-top.leaflet-right {{ margin-top: 8px; }}
.stats {{ display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 0.9rem; }}
.stat {{ flex: 1 1 12rem; background: var(--glass); border: 1px solid var(--border); border-radius: 12px; padding: 0.7rem 1rem; }}
.stat-label {{ display: block; font-family: var(--mono); font-size: 0.62rem; font-weight: 600;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--dim); }}
.stat-value {{ font-family: var(--mono); font-size: 1.02rem; }}
.bar-wrap {{ margin-top: 0.9rem; background: var(--glass); border: 1px solid var(--border); border-radius: 12px; padding: 0.8rem 1rem; }}
.bar {{ position: relative; display: flex; height: 10px; border-radius: 5px; overflow: visible; }}
.seg-calm {{ background: #00d4ff; border-radius: 5px 0 0 5px; }}
.seg-watch {{ background: #ffb800; }}
.seg-strained {{ background: #ff7a1a; }}
.seg-severe {{ background: #ff4545; border-radius: 0 5px 5px 0; }}
.peak-marker {{ position: absolute; top: -5px; width: 2px; height: 20px; background: #fff;
  box-shadow: 0 0 8px rgba(255,255,255,0.8); }}
.thresholds {{ margin: 0.5rem 0 0; color: var(--secondary); font-size: 0.85rem; font-family: var(--mono); }}
.panel {{ margin-top: 0.9rem; background: var(--glass); border: 1px solid var(--border); border-radius: 16px; padding: 0.9rem 1.1rem; }}
.panel h2 {{ font-family: var(--mono); font-size: 0.68rem; font-weight: 600; letter-spacing: 0.14em;
  text-transform: uppercase; color: var(--secondary); margin: 0 0 0.5rem; }}
.panel ul {{ margin: 0; padding-left: 1.1rem; }}
.pill {{ font-family: var(--mono); font-size: 0.82rem; }}
footer {{ margin-top: 1rem; color: var(--dim); font-size: 0.85rem; }}
.repo-link {{ margin-top: 0.5rem; font-size: 0.9rem; color: var(--secondary); }}
.repo-link a {{ color: var(--accent); }}
@media (max-width: 640px) {{ .map-caption {{ display: none; }} #map {{ min-height: 300px; }} }}
</style>
</head>
<body>
<div class="wrap">
<header class="hud">
<span class="wordmark">Beat the Grid</span>
<h1>Grid brief — {target}</h1>
<span class="meta">{GEOGRAPHY}. Definition: {esc(forecast.definition_version)}.</span>
</header>
<div class="map-panel">
<div id="map"></div>
<div class="hero">
{hero_html}
</div>
<div class="map-caption">Lit counties are the BGE home territory, glowing at today's call level — the call itself is PJM-wide. Zoom in to your neighborhood: if your county is lit, the call covers you. County lines are an approximation.</div>
</div>
{stats_html}
{bar_html}
{alerts_html}<section class="panel"><h2>Freshness</h2>
<ul>
<li class="pill">Load: {load_state} (latest completed peak {facts.latest_completed_peak.isoformat()}: {completed})</li>
<li class="pill">Weather: {weather_state} (pinned NWS BWI issuance: {_fmt_time(facts.weather_update_time)})</li>
{drivers}<li>History days loaded: {facts.history_days} (last: {facts.history_last_date or "—"})</li>
</ul>
</section>
<footer>Data as of: {facts.data_as_of or "—"} (last load hour: {_fmt_time(facts.load_last_hour_utc)}). Generated: {generated}.</footer>
<p class="repo-link">Code, receipts ledger, and method: <a href="https://github.com/Darren-dev141/grid-project">open on GitHub</a>.</p>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
{map_html}
</body>
</html>
'''
    comment_lines = [f'## Grid brief — {target}', '',
                     f'{GEOGRAPHY}. Definition: {forecast.definition_version}.',
                     *call_lines,
                     f'Freshness: load {load_state}, weather {weather_state}.',
                     f'Data as of: {facts.data_as_of or "—"}.',
                     '', f'### Receipts for {target}']
    if receipts:
        comment_lines += [f'- `{path}` — sha256: `{digest}`' for path, digest in receipts]
    else:
        comment_lines.append('No receipts in the ledger for this target date.')
    comment_lines.append('')
    return Brief(html=page, comment_md='\n'.join(comment_lines))


def _weather_field(weather, name):
    if weather is None:
        return None
    if isinstance(weather, dict):
        return weather.get(name)
    return getattr(weather, name, None)


def _warehouse_facts(database: Path) -> tuple[date | None, datetime | None]:
    """Data-as-of from the built dbt tables; (None, None) when not built."""
    data_as_of = None
    load_last_hour = None
    with duckdb.connect(str(database), read_only=True) as connection:
        try:
            row = connection.execute(
                'SELECT max(local_date) FROM marts.mart_day_history').fetchone()
            data_as_of = row[0] if row else None
        except duckdb.Error:
            pass
        try:
            row = connection.execute(
                'SELECT max(hour_utc) FROM cleaned.eia_pjm_hourly_demand').fetchone()
            load_last_hour = row[0] if row else None
        except duckdb.Error:
            pass
    return data_as_of, load_last_hour


def build_features(database: Path, target_date: date) -> tuple[Features, BriefFacts]:
    """Assemble forecast features and freshness facts from the warehouse."""
    history = load_first_recorded_history(database, database)
    weather = load_nws_bwi_forecast(database, target_date)
    high_f = _weather_field(weather, 'high_f')
    morning_low_f = _weather_field(weather, 'morning_low_f')
    update_time = _weather_field(weather, 'update_time')
    latest_completed = target_date - timedelta(days=2)
    latest_present = any(
        day.date == latest_completed and day.complete
        and day.load_first_recorded is True
        and day.peak_mw is not None and isfinite(day.peak_mw)
        for day in history)
    weather_fresh = (high_f is not None and morning_low_f is not None
                     and isfinite(high_f) and isfinite(morning_low_f))
    features = Features(target_date=target_date, high_f=high_f,
                        morning_low_f=morning_low_f, history=history,
                        load_fresh=latest_present, weather_fresh=weather_fresh,
                        alerts=(), mode='retrospective')
    mart_as_of, load_last_hour = _warehouse_facts(database)
    history_last = max((day.date for day in history), default=None)
    facts = BriefFacts(load_fresh=latest_present, weather_fresh=weather_fresh,
                       latest_completed_peak=latest_completed,
                       latest_completed_present=latest_present,
                       history_days=len(history), history_last_date=history_last,
                       data_as_of=mart_as_of or history_last,
                       load_last_hour_utc=load_last_hour,
                       weather_update_time=update_time,
                       target_high_f=high_f, target_morning_low_f=morning_low_f)
    return features, facts


def render_brief(database: Path, root: Path, out_dir: Path, *,
                 target_date: date | None = None,
                 generated_at: datetime | None = None) -> RenderedBrief:
    """Compute the forecast for ``target_date`` and write the brief files.

    ``root`` is the ledger root (the directory holding ``definitions/`` and
    ``forecasts/``). Writes ``index.html`` and ``comment.md`` under
    ``out_dir``. Defaults the target to today in America/New_York.
    """
    database = Path(database)
    root = Path(root)
    out_dir = Path(out_dir)
    generated = generated_at or datetime.now(timezone.utc)
    target = target_date or generated.astimezone(ET).date()
    definition = parse_definition(ledger.read_definition(
        root / 'definitions' / (DEFINITION_VERSION + '.toml')))
    features, facts = build_features(database, target)
    result = stress_forecast(features, definition)
    receipts = _receipt_listing(root, target)
    brief = render(result, facts, receipts, generated_at=generated)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / 'index.html'
    comment_path = out_dir / 'comment.md'
    index_path.write_text(brief.html, encoding='utf-8')
    comment_path.write_text(brief.comment_md, encoding='utf-8')
    return RenderedBrief(forecast=result, facts=facts, brief=brief,
                         index_path=index_path, comment_path=comment_path)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True,
                        help='Built DuckDB warehouse (raw + cleaned/marts).')
    parser.add_argument('--ledger', type=Path, required=True,
                        help='Ledger root (holds definitions/ and forecasts/).')
    parser.add_argument('--out', type=Path, default=Path('site'),
                        help='Output directory for index.html and comment.md.')
    parser.add_argument('--target-date', type=date.fromisoformat, default=None,
                        help='Target date (default: today, America/New_York).')
    args = parser.parse_args(argv)
    rendered = render_brief(args.database, args.ledger, args.out,
                            target_date=args.target_date)
    result = rendered.forecast
    summary = (f'no call ({result.no_call_reason})' if result.no_call_reason
               else f'level {result.level}')
    print(f'wrote {rendered.index_path} and {rendered.comment_path}: '
          f'target {result.target_date.isoformat()}, {summary}')


if __name__ == '__main__':
    main()
