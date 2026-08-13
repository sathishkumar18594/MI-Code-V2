from datetime import datetime

import pandas as pd

from application.app_context import AppContext
from indicators.indicator_pipeline import (
    IndicatorPipeline,
)
from mappers.stock_snapshot_mapper import (
    StockSnapshotMapper,
)
from models.ranking import Ranking
from services.scoring_service import (
    ScoringService,
)
from services.liquidity_service import (
    LiquidityService,
)
from services.circuit_risk_service import CircuitRiskService
from services.market_cap_service import MarketCapService


class RankingService:

    def __init__(
        self,
        context: AppContext,
    ):

        self.context = context

        self.repository = (
            context.price_repository
        )

        self.pipeline = (
            IndicatorPipeline(
                context
            )
        )

        self.scoring_service = (
            ScoringService(
                context
            )
        )
        self.liquidity_service = (
            LiquidityService(
                context
            )
        )
        self.circuit_risk_service = CircuitRiskService(context)
        self.market_cap_service = MarketCapService(context)

        self.cache = {}
        self.entry_cache = {}
        self.dataframes = {}
        self.quiet = False
        self.rank_before_filters = False
        self.apply_market_cap_filter = True
    def _build_dataframe_cache(
        self,
        symbols: list[str],
    ):
        self.dataframes.clear()
        for symbol in symbols:
            if not self.repository.exists(symbol):
                self._log_unavailable(symbol)
                continue
            df = self.repository.load(symbol)
            print(
                f"[LOAD] {symbol} rows={len(df)} last_date={df['Date'].max()}"
            )
            df = self.pipeline.execute(df)
            df = self.circuit_risk_service.add_risk_columns(df)
            # A multi-sector backtest holds hundreds of read-only indicator
            # frames.  Float32 is ample for prices, ratios and scores while
            # materially reducing the shared cache footprint.
            float_columns = df.select_dtypes(include=["float64"]).columns
            if len(float_columns):
                df[float_columns] = df[float_columns].astype("float32")
            self.dataframes[symbol] = df

    def _collect_rows(
        self,
        symbols: list[str],
        trading_date: datetime,
        use_dataframe_cache: bool,
    ):
        rows = []
        if use_dataframe_cache:
            for symbol in symbols:
                df = self.dataframes.get(symbol)
                if df is None:
                    continue
                # Binary search on the sorted Date column.
                idx = df["Date"].searchsorted(trading_date, side="right") - 1
                if idx < 0:
                    if not self.quiet:
                        print(f"[NO DATA] {symbol} before {trading_date.date()}")
                    continue
                history = df.iloc[:idx + 1]

                latest = history.iloc[-1].copy()
                latest["symbol"] = symbol
                latest["average_daily_traded_value"] = (
                    self.liquidity_service
                    .average_daily_traded_value(history)
                )
                latest["market_cap_crore"] = (
                    self.market_cap_service.market_cap_as_of(
                        symbol,
                        trading_date,
                    )
                )
                latest["industry"] = self.market_cap_service.industry_as_of(
                    symbol, trading_date
                )
                rows.append(latest)
        else:
            for symbol in symbols:
                if not self.repository.exists(symbol):
                    self._log_unavailable(symbol)
                    continue

                df = self.repository.load(symbol)
                print(
                    f"[LOAD] {symbol} rows={len(df)} last_date={df['Date'].max()}"
                )

                df = self.pipeline.execute(df)
                df = self.circuit_risk_service.add_risk_columns(df)

                df = df[
                    df["Date"] <= trading_date
                ]

                if df.empty:
                    print(
                        f"[NO DATA] {symbol} before {trading_date.date()}"
                    )
                    continue

                latest = df.iloc[-1].copy()

                latest["symbol"] = symbol
                latest["average_daily_traded_value"] = (
                    self.liquidity_service
                    .average_daily_traded_value(df)
                )
                latest["market_cap_crore"] = (
                    self.market_cap_service.market_cap_as_of(
                        symbol,
                        trading_date,
                    )
                )
                latest["industry"] = self.market_cap_service.industry_as_of(
                    symbol, trading_date
                )

                rows.append(latest)

        return rows

    def _log_unavailable(self, symbol: str):
        if hasattr(self.repository, "availability"):
            details = self.repository.availability(symbol)
            print(
                f"[EXCLUDED] {symbol} status={details['status']} "
                f"isin={details['isin'] or '-'}"
            )
            return
        print(f"[MISSING] {symbol}")

    def _build_rankings(
        self,
        rows,
        apply_circuit_filter=False,
        trading_date=None,
    ) -> list[Ranking]:
        if not rows:
            return []

        universe = pd.DataFrame(rows)

        if self.rank_before_filters:
            # Establish the point-in-time rank across the full sector
            # universe. Entry screens may remove rows but never renumber them.
            universe = self.scoring_service.calculate(universe)
            universe = universe.sort_values("score", ascending=False).reset_index(drop=True)
            universe["_overall_rank"] = range(1, len(universe) + 1)
            if apply_circuit_filter:
                universe = self.liquidity_service.filter(universe)
                universe = self.circuit_risk_service.filter(universe)
                if self.apply_market_cap_filter:
                    universe = self.market_cap_service.filter(
                        universe,
                        as_of_date=trading_date,
                    )
            pre_scored = True
        else:
            pre_scored = False

        if not pre_scored:
            universe = self.liquidity_service.filter(universe)

        if apply_circuit_filter and not pre_scored:
            universe = self.circuit_risk_service.filter(universe)
            if self.apply_market_cap_filter:
                universe = self.market_cap_service.filter(
                    universe,
                    as_of_date=trading_date,
                )

        if not pre_scored:
            universe = self.scoring_service.calculate(universe)

        universe = (
            universe
            .sort_values(
                by="score",
                ascending=False,
            )
            .reset_index(drop=True)
        )

        rankings = []

        for index, (_, row) in enumerate(
            universe.iterrows(),
            start=1,
        ):

            snapshot = (
                StockSnapshotMapper.from_series(
                    row
                )
            )

            factor_values = (
                self.scoring_service.get_factor_values(
                    row
                )
            )
            factor_values["market_cap_crore"] = row.get("market_cap_crore")
            factor_values["industry"] = row.get("industry")
            rankings.append(
                Ranking(
                    rank=int(row["_overall_rank"]) if "_overall_rank" in row else index,
                    stock=snapshot,
                    score=row["score"],
                    factor_values=factor_values,
                )
            )

        return rankings

    def rank(
        self,
        symbols: list[str],
        rebalance_date: datetime,
    ) -> list[Ranking]:

        rows = self._collect_rows(
            symbols=symbols,
            trading_date=rebalance_date,
            use_dataframe_cache=False,
        )
        return self._build_rankings(rows, trading_date=rebalance_date)

    def build_cache(
        self,
        symbols: list[str],
        trading_dates: list[datetime],
        symbols_by_date: dict | None = None,
        dataframe_cache: dict | None = None,
        lazy: bool = False,
        rank_before_filters: bool = False,
        apply_market_cap_filter: bool = True,
    ):
        self.cache.clear()
        self.entry_cache.clear()
        self.symbols_by_date = symbols_by_date or {}
        self.lazy = lazy
        self.rank_before_filters = rank_before_filters
        self.apply_market_cap_filter = apply_market_cap_filter
        self.quiet = lazy
        if dataframe_cache is None:
            self._build_dataframe_cache(symbols)
        else:
            # Multi-universe sleeves overlap substantially.  The pipeline
            # output is read-only, so every sleeve can safely share it.
            self.dataframes = dataframe_cache
        if self.lazy:
            return
        for trading_date in trading_dates:
            date_symbols = (
                symbols_by_date.get(trading_date, symbols)
                if symbols_by_date is not None
                else symbols
            )
            rows = self._collect_rows(
                symbols=date_symbols,
                trading_date=trading_date,
                use_dataframe_cache=True,
            )
            self.cache[trading_date] = self._build_rankings(
                rows,
                trading_date=trading_date,
            )
            self.entry_cache[trading_date] = self._build_rankings(
                rows,
                apply_circuit_filter=True,
                trading_date=trading_date,
            )

    def get_rankings(
        self,
        trading_date: datetime,
    ) -> list[Ranking]:
        if getattr(self, "lazy", False):
            rows = self._collect_rows(
                symbols=self.symbols_by_date.get(trading_date, []),
                trading_date=trading_date,
                use_dataframe_cache=True,
            )
            return self._build_rankings(rows, trading_date=trading_date)
        return self.cache.get(trading_date, [])

    def get_entry_rankings(self, trading_date):
        if getattr(self, "lazy", False):
            rows = self._collect_rows(
                symbols=self.symbols_by_date.get(trading_date, []),
                trading_date=trading_date,
                use_dataframe_cache=True,
            )
            return self._build_rankings(
                rows,
                apply_circuit_filter=True,
                trading_date=trading_date,
            )
        return self.entry_cache.get(trading_date, [])
