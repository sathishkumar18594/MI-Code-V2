"""Download price history for the complete current sector-stock universe."""

import sys
import os
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from providers.yahoo_provider import YahooProvider
from repositories.parquet_repository import ParquetRepository
from services.marketdata_service import MarketDataService
from services.validation_service import ValidationService


config = yaml.safe_load(Path("config/sector_portfolio.yaml").read_text())
universe_files = [
    Path("data/universe") / f"{sleeve['universe']}.csv"
    for sleeve in config["sleeves"]
]
symbols = sorted({
    symbol.strip()
    for file in universe_files
    for symbol in pd.read_csv(file)["Symbol"].dropna().astype(str)
    if symbol.strip()
})

# Optional resumable batching for long first-time downloads.
offset = int(os.getenv("SECTOR_DOWNLOAD_OFFSET", "0"))
limit = int(os.getenv("SECTOR_DOWNLOAD_LIMIT", str(len(symbols))))
symbols = symbols[offset:offset + limit]
requested = os.getenv("SECTOR_SYMBOLS")
if requested:
    symbols = [symbol.strip() for symbol in requested.split(",") if symbol.strip()]

service = MarketDataService(
    provider=YahooProvider(),
    repository=ParquetRepository(root="data/prices"),
    validator=ValidationService(),
)
print(f"Downloading/updating {len(symbols)} sector stocks (offset={offset}).")
service.update_all(symbols)
