"""Read-only: latest data day per source as the stress loader sees it, as of now."""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from grid_pipeline.stress_inputs import load_first_recorded_history
root = Path(r'C:/Users/ajbig/Documents/grid-project/data')
now = datetime.now(ZoneInfo('America/New_York'))
h = load_first_recorded_history(root / 's1-live' / 'grid.duckdb', root / 's3a-verification' / 'grid.duckdb', indexed_by=now)
tmp = [d for d in h if d.temperature_available_at is not None]
ld = [d for d in h if d.load_available_at is not None]
print('as of', now.isoformat())
print('latest day with temperature:', max(d.date for d in tmp), '| usable_at set on', sum(d.temperature_usable_at is not None for d in tmp), 'of', len(tmp))
print('latest day with load:', max(d.date for d in ld), '| usable_at set on', sum(d.load_usable_at is not None for d in ld), 'of', len(ld))
