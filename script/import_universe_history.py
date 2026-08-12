import sys
from pathlib import Path

# Allow this script to be run directly from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.universe_service import UniverseService


if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: python script/import_universe_history.py <universe> <source_csv>"
    )

UniverseService().import_history(sys.argv[1].lower(), sys.argv[2])
