"""Run the RK4 package from this checkout: python simulate.py [--output NEW_DIR]."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'src'))

if __name__ == '__main__':
    from waveguide_sim.__main__ import main
    raise SystemExit(main())
