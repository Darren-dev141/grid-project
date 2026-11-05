#!/usr/bin/env bash
# W2 mutation check. Runs tests/test_stress_rulings.py against a scratch copy of the
# worktree (src, scripts, tests, ledger) with one deliberate break at a time, then
# restores the original files. Nothing in the repo is modified.
# Usage: SCR=<scratch copy dir> PY=<python> bash mutation-check.sh
set -u
cd "$SCR"
run() { PYTHONPATH=src "$PY" -m pytest tests/test_stress_rulings.py -q -p no:cacheprovider 2>&1 | tail -1 | tr -d '\r'; }
cp src/grid_pipeline/stress.py stress.orig
cp scripts/issue_stress.py issue.orig
restore() { cp stress.orig src/grid_pipeline/stress.py; cp issue.orig scripts/issue_stress.py; }

echo "M0 unmutated:                         $(run)"

sed -i "s/if _issued_after(features.issued_at, issuance_cutoff(features.target_date)):/if features.issued_at.astimezone(ZoneInfo('America\/New_York')).date() >= features.target_date:/" src/grid_pipeline/stress.py
echo "M1 old before-target-date gate:       $(run)"; restore

sed -i "s/if features.mode == 'prospective' and _issued_after(/if False and _issued_after(/" src/grid_pipeline/stress.py
echo "M2 peak-hour gate disabled:           $(run)"; restore

sed -i "s/return issued_at.astimezone(timezone.utc) > boundary.astimezone(timezone.utc)/return issued_at.astimezone(timezone.utc) >= boundary.astimezone(timezone.utc)/" src/grid_pipeline/stress.py
echo "M3 boundary made exclusive (>=):      $(run)"; restore

sed -i "s/load_fresh=load_is_fresh(history, latest_completed_peak),/load_fresh=target is not None and target.load_first_recorded is True,/" scripts/issue_stress.py
echo "M4 target-row freshness restored:     $(run)"; restore

echo "M5 restored:                          $(run)"
cmp stress.orig src/grid_pipeline/stress.py && cmp issue.orig scripts/issue_stress.py && echo "originals restored byte-for-byte"
