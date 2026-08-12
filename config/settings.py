from pathlib import Path

# ==========================================
# Project Paths
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data_v2"

PRICE_DIR = DATA_DIR / "upstox" / "parquet_by_isin"

UNIVERSE_DIR = DATA_DIR / "universe"

LOG_DIR = PROJECT_ROOT / "logs"

# ==========================================
# Historical Data
# ==========================================

START_DATE = "2010-01-01"

# ==========================================
# Yahoo Finance
# ==========================================

EXCHANGE_SUFFIX = ".NS"

INDEX_SYMBOLS = {
    "nifty500": "^CRSLDX"
}

# ==========================================
# Strategy
# ==========================================

REBALANCE_DAY = 21

PORTFOLIO_SIZE = 15

# ==========================================
# Momentum
# ==========================================

RETURN_MONTHS = [9, 6, 3]

VOLATILITY_MONTHS = 3

# ==========================================
# Supertrend
# ==========================================

SUPERTREND_PERIOD = 1

SUPERTREND_MULTIPLIER = 2.5
