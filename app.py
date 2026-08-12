from repositories.upstox_repository import UpstoxRepository
from services.universe_service import UniverseService
from config.config_loader import ConfigLoader
from providers.upstox_index_provider import sync_nifty500_index

index_path, index_rows_added = sync_nifty500_index()
print(f"Nifty 500 index ready: added {index_rows_added:,} new candles to {index_path}.")

# MI-Code V2 consumes the audited QM-Book-Code Upstox store in place.  Data
# acquisition is intentionally separated from the strategy run, preserving
# the source ISIN files as an immutable, reproducible input.
repository = UpstoxRepository()
universe = UniverseService().get_universe(ConfigLoader.get("universe", "name").lower())
available = [symbol for symbol in universe if repository.exists(symbol)]
print(f"Upstox data ready: {len(available):,}/{len(universe):,} current constituents have candle history.")
