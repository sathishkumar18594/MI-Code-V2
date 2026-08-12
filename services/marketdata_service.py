from datetime import timedelta
from utils.logger import logger

import pandas as pd


class MarketDataService:

    def __init__(
        self,
        provider,
        repository,
        validator
    ):
        self.provider = provider
        self.repository = repository
        self.validator = validator
        self._today = pd.Timestamp.today().normalize()

    def download_history(

        self,

        symbol: str

    ) -> pd.DataFrame | None:

        # First download

        if not self.repository.exists(symbol):

            logger.info(f"[FULL] Downloading complete history for {symbol}")

            df = self.provider.download(

                symbol=symbol,

                start="2010-01-01"

            )

        else:

            last_date = self.repository.last_date(symbol)

            last_date = pd.Timestamp(last_date).normalize()
            today = self._today

            # Already updated

            if last_date >= today:

                logger.info(

                    f"[SKIP] {symbol} already up to date."

                )

                return None

            start_date = (

                last_date + timedelta(days=1)

            ).strftime("%Y-%m-%d")

            logger.info(

                f"[UPDATE] Updating {symbol} from {start_date}"

            )

            df = self.provider.download(

                symbol=symbol,

                start=start_date

            )

        if df.empty:

            logger.info(

                f"[SKIP] No new data for {symbol}"

            )

            return None

        price_columns = ["Open", "High", "Low", "Close"]
        invalid_prices = (df[price_columns] <= 0).any(axis=1)
        if invalid_prices.any():
            dropped = int(invalid_prices.sum())
            logger.warning(
                f"[CLEAN] Dropping {dropped} invalid OHLC rows for {symbol}"
            )
            df = df.loc[~invalid_prices].copy()

        if df.empty:
            logger.warning(f"[SKIP] No valid OHLC rows for {symbol}")
            return None

        self.validator.validate(df)

        self.repository.save(

            symbol,

            df

        )

        logger.info(

            f"[SUCCESS] {symbol}"

        )

        return df

    def update_symbol(
        self,
        symbol: str
    ):

        try:

            self.download_history(symbol)

        except Exception as ex:

            logger.error(f"[ERROR] {symbol} : {ex}")

    def update_all(
        self,
        universe
    ):

        total = len(universe)
        if isinstance(universe, pd.DataFrame):
            symbols = universe["Symbol"]
        else:
            symbols = universe

        logger.info(f"\nUpdating {total} symbols...\n")

        for index, symbol in enumerate(
            symbols,
            start=1
        ):

            if index % 25 == 0 or index == total:
                logger.info(f"[{index}/{total}] symbols processed")

            self.update_symbol(symbol)

        logger.info("\nMarket data update completed.")
