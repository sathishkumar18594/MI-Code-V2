from datetime import timedelta

import pandas as pd

from config.config_loader import ConfigLoader
from utils.logger import logger


class IndexService:

    def __init__(
        self,
        provider,
        repository,
        validator,
    ):

        self.provider = provider
        self.repository = repository
        self.validator = validator

        config = ConfigLoader.load()

        market_filter = config[
            "universe"
        ][
            "market_filter"
        ]

        self.index_name = (
            market_filter[
                "index"
            ][
                "name"
            ]
        )

        self.symbol = (
            market_filter[
                "index"
            ][
                "symbol"
            ]
        )

    def update(self):

        if not self.repository.exists(self.index_name):

            logger.info(
                f"Downloading complete history for {self.index_name}"
            )

            df = self.provider.download(
                symbol=self.symbol,
                start="2010-01-01",
            )

        else:

            last_date = self.repository.last_date(
                self.index_name
            )

            today = pd.Timestamp.today().normalize()

            if last_date >= today:

                logger.info(
                    f"{self.index_name} already up to date."
                )

                return

            start_date = (
                last_date + timedelta(days=1)
            ).strftime("%Y-%m-%d")

            logger.info(
                f"Updating {self.index_name} from {start_date}"
            )

            df = self.provider.download(
                symbol=self.symbol,
                start=start_date,
            )

        if df.empty:

            logger.info(
                f"{self.index_name} already up to date."
            )

            return

        self.validator.validate(df)

        self.repository.save(
            self.index_name,
            df,
        )

    def last_trading_day(self):

        return self.repository.last_date(
            self.index_name
        )