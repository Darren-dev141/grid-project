import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
WM = Path(__file__).resolve().parents[1]     # world-model/
sys.path.insert(0, str(WM))
sys.path.insert(0, str(ROOT / "src"))
