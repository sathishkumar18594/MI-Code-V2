"""Build point-in-time sector eligibility from the supplied Nifty 500 ledger."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.universe_service import UniverseService


config = yaml.safe_load(Path("config/sector_portfolio.yaml").read_text())
service = UniverseService()
for sleeve in config["sleeves"]:
    universe = sleeve["universe"]
    history = service.build_sector_history_from_parent(universe)
    print(f"{universe}: {len(history)} snapshots, latest members={len(history.iloc[-1]['symbols'].split(','))}")
