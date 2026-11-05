"""W2 design probe: where do 'issue before target day' and 'D-2 = target-2' meet?

Uses the worktree's stress.forecast on a minimal Features; prints only the
no-call reasons / gate arithmetic. No data, no network, no files written.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from grid_pipeline.model import Features
from grid_pipeline.stress import forecast, parse_definition
from grid_pipeline.ledger import read_definition

ET = ZoneInfo('America/New_York')
defn = parse_definition(read_definition(__import__('pathlib').Path('ledger/definitions/stress-index-v1.toml')))
issued = datetime(2026, 11, 5, 7, 0, tzinfo=ET)          # the 07:00 cron issuance, day D
print('issued_at (D) =', issued.isoformat())
print('ruling latest completed peak = D-2 =', issued.date() - timedelta(days=2))
for label, target in (('same-day target (D)', date(2026, 11, 5)),
                      ('next-day target (D+1)', date(2026, 11, 6))):
    f = Features(target_date=target, high_f=70.0, morning_low_f=50.0, history=(),
                 load_fresh=True, weather_fresh=True, mode='prospective',
                 issued_at=issued, weather_available_at=issued - timedelta(hours=1))
    r = forecast(f, defn)
    print(f'{label}: target={target}  target-2={target - timedelta(days=2)}  '
          f'ruling D-2 == target-2? {issued.date() - timedelta(days=2) == target - timedelta(days=2)}  '
          f'-> {r.status}/{r.no_call_reason}')
