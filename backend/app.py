"""Startpunkt: `uv run backend/app.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from editor_app.main import run  # noqa: E402

run()
