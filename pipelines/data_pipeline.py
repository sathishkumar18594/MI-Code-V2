class DataPipeline:

    def __init__(
        self,
        universe_service,
        market_data_service,
        index_service
    ):

        self.universe_service = universe_service
        self.market_data_service = market_data_service
        self.index_service = index_service

    def run(
        self,
        universe_name
    ):

        universe_name = universe_name.lower()

        self.index_service.update()

        # Refresh first so any Nifty 500 additions are included immediately.
        # update_all downloads full history for symbols not yet in data/prices.
        universe = self.universe_service.refresh(
            universe_name
        )

        # Download former constituents too.  A backtest ranks the historical
        # Nifty 500 snapshot for each date, so downloading only today's list
        # leaves past constituent periods without price data.
        historical_symbols = self.universe_service.history_symbols(
            universe_name,
            start_date="1900-01-01",
            end_date="2100-01-01",
        )
        current_symbols = universe["Symbol"].dropna().astype(str).tolist()
        symbols_to_update = sorted(
            (set(current_symbols) | set(historical_symbols))
            - self.universe_service.HISTORICAL_DOWNLOAD_EXCLUSIONS
        )

        self.market_data_service.update_all(
            symbols_to_update
        )
        self.market_data_service.update_symbol("GOLDBEES")
