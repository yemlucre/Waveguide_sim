"""Compatibility imports; the single maintained BPM implementation is in the package."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from waveguide_sim.bpm import *  # noqa: F401,F403
