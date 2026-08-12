import pandas as pd
import yfinance as yf

from config.settings import EXCHANGE_SUFFIX
from utils.logger import logger


class YahooProvider:

    def download(
        self,
        symbol: str,
        start: str,
    ) -> pd.DataFrame:

        #
        # Stocks need .NS
        # Indices (starting with ^) do NOT
        #
        yahoo_symbol = (
            symbol
            if symbol.startswith("^")
            else f"{symbol}{EXCHANGE_SUFFIX}"
        )

        logger.info(
            f"Downloading {yahoo_symbol}"
        )

        df = yf.download(
            tickers=yahoo_symbol,
            start=start,
            auto_adjust=False,
            progress=False,
        )

        if df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        return df