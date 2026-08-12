import pandas as pd

from application.app_context import AppContext

from models.trade import Trade
from models.sell_reason import SellReason

from models.portfolio import Portfolio
from models.portfolio_state import PortfolioState
from models.portfolio_position import (
    PortfolioPosition,
)
from services.portfolio_accounting_service import (
    PortfolioAccountingService,
)

from services.execution_price_service import ExecutionPriceService
from services.transaction_cost_service import TransactionCostService


class PortfolioManager:

    def __init__(
        self,
        context: AppContext,
    ):

        self.context = context

        strategy = context.config["strategy"]

        self.portfolio_size = (
            strategy["portfolio_size"]
        )

        self.sell_rank_percent = (
            strategy.get(
                "sell_rank_percent",
                strategy.get(
                    "sell_threshold_percent",
                    10,
                ),
            )
        )
        portfolio = context.config["portfolio"]

        self.initial_capital = (
            portfolio["initial_capital"]
        )

        self.execution = ExecutionPriceService(context)
        self.transaction_cost = (
            TransactionCostService(context)
        )
        self.accounting = (
            PortfolioAccountingService()
        )
        hedge = context.config.get("market_hedge", {})
        self.hedge_enabled = hedge.get("enabled", False)
        self.hedge_symbol = hedge.get("symbol", "GOLDBEES")

    def update(
        self,
        state: PortfolioState,
        rankings,
        market_bullish: bool,
        rebalance_date,
        is_rebalance_day: bool = True,
        entry_rankings=None,
    ) -> PortfolioState:

        # An empty entry list means every stock failed an entry screen (for
        # example lower-circuit or liquidity).  Only fall back when the caller
        # did not supply screened rankings at all.
        screened_entry_rankings = (
            rankings if entry_rankings is None else entry_rankings
        )

        # Ensure initial capital is set only for the first investment.
        if state.portfolio is None:
            state.cash = self.initial_capital

        if not market_bullish:
            return self._handle_market_exit(
                state,
                rebalance_date,
            )

        if self._is_hedge_portfolio(state.portfolio):
            portfolio = self._liquidate_portfolio(state.portfolio, rebalance_date)
            state = PortfolioState(portfolio=portfolio, invested=False, cash=portfolio.cash)

        if not state.invested:
            return self._handle_first_investment(
                state,
                screened_entry_rankings,
                rebalance_date,
            )

        return self._handle_existing_portfolio(
            state,
            rankings,
            rebalance_date,
            is_rebalance_day,
            screened_entry_rankings,
        )

    def _handle_market_exit(
        self,
        state: PortfolioState,
        rebalance_date,
    ) -> PortfolioState:

        if self._is_hedge_portfolio(state.portfolio):
            return state

        if state.portfolio is not None:
            portfolio = self._liquidate_portfolio(
                state.portfolio,
                rebalance_date,
            )
        else:
            portfolio = Portfolio(
                rebalance_date=rebalance_date,
                initial_capital=state.cash,
                cash=state.cash,
                available_cash=state.cash,
                total_value=state.cash,
                is_invested=False,
            )

        if self.hedge_enabled:
            portfolio = self._build_hedge_portfolio(portfolio, rebalance_date)

        return PortfolioState(portfolio=portfolio, invested=portfolio.is_invested, cash=portfolio.cash)

    def _is_hedge_portfolio(self, portfolio):
        return bool(
            self.hedge_enabled
            and portfolio is not None
            and portfolio.holdings
            and all(holding.symbol == self.hedge_symbol for holding in portfolio.holdings)
        )

    def _build_hedge_portfolio(self, portfolio, rebalance_date):
        execution = self.execution.execution_price(self.hedge_symbol, rebalance_date)
        allocation = portfolio.cash
        charges = self.transaction_cost.calculate_buy(allocation)
        market_value = max(0.0, allocation - charges.total)
        holding = PortfolioPosition(
            symbol=self.hedge_symbol,
            entry_date=execution.date,
            entry_rank=0,
            entry_price=execution.price,
            quantity=market_value / execution.price if execution.price else 0.0,
            current_price=execution.price,
            weight=1.0,
            rank=0,
            score=0.0,
            cost_value=allocation,
            market_value=market_value,
        )
        return self._build_portfolio(portfolio, rebalance_date, [holding], 0.0)
    
    def _handle_first_investment(
        self,
        state: PortfolioState,
        rankings,
        rebalance_date,
    ) -> PortfolioState:

        portfolio = self.build_new_portfolio(
            rankings,
            rebalance_date,
            capital=state.cash,
            previous_portfolio=state.portfolio,
        )

        return PortfolioState(
            portfolio=portfolio,
            invested=True,
            cash=0.0,
        )
    
    def _handle_existing_portfolio(
        self,
        state: PortfolioState,
        rankings,
        rebalance_date,
        is_rebalance_day,
        entry_rankings,
    ) -> PortfolioState:
        if is_rebalance_day:
            portfolio = self.rebalance_existing_portfolio(
                state.portfolio,
                rankings,
                entry_rankings,
                rebalance_date,
            )
        else:
            portfolio = self._process_daily_portfolio(
                state.portfolio,
                rankings,
                rebalance_date,
            )

        return PortfolioState(
            portfolio=portfolio,
            invested=True,
            cash=0.0,
        )

    def _process_daily_portfolio(
        self,
        portfolio,
        rankings,
        rebalance_date,
    ):
        """Mark holdings to market without applying rank exits.

        Rank is a monthly portfolio-construction signal. Between scheduled
        rebalances, ranks may be refreshed for reporting, but a holding is not
        sold merely because its daily rank crossed the exit threshold.
        Market-regime exits are handled earlier in ``update`` and remain daily.
        """
        rank_lookup = {
            ranking.stock.symbol: ranking
            for ranking in rankings
        }
        kept_holdings = []
        for position in portfolio.holdings:
            self._apply_corporate_actions(position, rebalance_date)
            self._mark_to_market(position, rebalance_date)
            ranking = rank_lookup.get(position.symbol)
            if ranking is not None:
                position.rank = ranking.rank
                position.score = ranking.stock.score
            position.weight = 0.0
            kept_holdings.append(position)

        self._update_weights(kept_holdings)
        return self._build_portfolio(
            portfolio,
            rebalance_date,
            kept_holdings,
            portfolio.cash,
            0.0,
        )
    
    def _apply_corporate_actions(self, position, rebalance_date):
        """Convert holdings at verified share-exchange corporate actions."""
        if (
            position.symbol == "JBCHEPHARM"
            and rebalance_date >= pd.Timestamp("2026-07-17")
        ):
            # 100 J.B. Chemicals shares convert to 51 Torrent Pharma shares.
            position.symbol = "TORNTPHARM"
            position.quantity *= 0.51
            position.entry_price /= 0.51

    def _mark_to_market(self, position, rebalance_date):
        execution = self.execution.execution_price(
            position.symbol,
            rebalance_date,
        )

        position.current_price = execution.price
        position.market_value = (
            position.quantity * position.current_price
        )
        position.unrealized_pnl = (
            position.market_value - position.cost_value
        )

    def _keep_holding(self, position, ranking, kept_holdings, held_symbols):
        position.rank = ranking.rank
        position.score = ranking.stock.score
        position.weight = 0.0

        kept_holdings.append(position)
        held_symbols.add(position.symbol)

    def _sell_holding(
        self,
        portfolio,
        position,
        rebalance_date,
        reason=SellReason.RANK_EXIT,
        exit_rank=None,
    ):

        realized = (
            position.market_value
            - position.cost_value
        )

        trade_charges = (
            self.transaction_cost.calculate_sell(
                position.market_value
            )
        )

        net_realized = (
            realized
            - trade_charges.total
        )

        # Trade history is the source of truth for realized P&L.

        portfolio.trades.append(
            Trade(
                symbol=position.symbol,
                entry_date=position.entry_date,
                entry_rank=position.entry_rank,
                exit_date=rebalance_date,
                exit_rank=exit_rank,
                entry_price=position.entry_price,
                exit_price=position.current_price,
                quantity=position.quantity,
                cost_value=position.cost_value,
                proceeds=position.market_value,
                gross_realized_pnl=realized,
                return_pct=(
                    realized / position.cost_value
                    if position.cost_value > 0
                    else 0.0
                ),
                brokerage=trade_charges.brokerage,
                stt=trade_charges.stt,
                exchange_charge=trade_charges.exchange_charge,
                sebi_charge=trade_charges.sebi_charge,
                gst=trade_charges.gst,
                stamp_duty=trade_charges.stamp_duty,
                total_charges=trade_charges.total,
                net_realized_pnl=net_realized,
                holding_days=(
                    rebalance_date
                    - position.entry_date
                ).days,
                sell_reason=reason,
            )
        )

        return (
            position.market_value
            - trade_charges.total
        )

    def _buy_replacement(
        self,
        ranking,
        allocation,
        rebalance_date,
    ):
        execution = self.execution.execution_price(
            ranking.stock.symbol,
            rebalance_date,
        )

        buy_charges = (
            self.transaction_cost.calculate_buy(
                allocation
            )
        )

        investable_amount = max(
            0.0,
            allocation - buy_charges.total
        )

        quantity = (
            investable_amount / execution.price
            if execution.price > 0
            else 0.0
        )

        return PortfolioPosition(
            symbol=ranking.stock.symbol,
            entry_date=execution.date,
            entry_rank=ranking.rank,
            entry_price=execution.price,
            quantity=quantity,
            current_price=execution.price,
            weight=0.0,
            rank=ranking.rank,
            score=ranking.stock.score,
            cost_value=allocation,
            market_value=investable_amount,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
        )

    def _update_weights(self, holdings):
        if not holdings:
            return

        total_value = sum(
            h.market_value
            for h in holdings
        )

        if total_value <= 0:
            return

        for holding in holdings:
            holding.weight = (
                holding.market_value
                / total_value
            )

    def _build_portfolio(
        self,
        previous_portfolio,
        rebalance_date,
        holdings,
        available_cash,
        period_realized_pnl=0.0,
    ):
        portfolio = Portfolio(
            rebalance_date=rebalance_date,
            holdings=holdings,
            initial_capital=previous_portfolio.initial_capital,
            cash=available_cash,
            available_cash=available_cash,
            realized_pnl=previous_portfolio.realized_pnl,
            # period_realized_pnl is not a Portfolio constructor arg anymore
            is_invested=bool(holdings),
            trades=previous_portfolio.trades,
        )
        portfolio = self.accounting.rebuild(
            portfolio,
            self.portfolio_size,
        )
        # Preserve the realized P&L generated by this rebalance.
        portfolio.period_realized_pnl = period_realized_pnl
        return portfolio
        

    
    def _liquidate_portfolio(
        self,
        portfolio,
        rebalance_date,
    ):
        available_cash = portfolio.cash
        period_realized_pnl = 0.0
        for holding in portfolio.holdings:
            self._mark_to_market(
                holding,
                rebalance_date,
            )
            period_realized_pnl += (
                holding.market_value
                - holding.cost_value
                - self.transaction_cost.calculate_sell(
                    holding.market_value
                ).total
            )
            available_cash += self._sell_holding(
                portfolio,
                holding,
                rebalance_date,
                SellReason.MARKET_EXIT,
            )
        portfolio.holdings.clear()

        return self._build_portfolio(
            portfolio,
            rebalance_date,
            [],
            available_cash,
            period_realized_pnl,
        )

    def build_new_portfolio(
        self,
        rankings,
        rebalance_date,
        capital,
        previous_portfolio=None,
    ):
        selected = rankings[: self.portfolio_size]
        if not selected:
            return Portfolio(
                rebalance_date=rebalance_date,
                holdings=[],
                is_invested=False,
            )
        weight = 1 / len(selected)
        allocation = (
            capital
            / len(selected)
        )
        holdings = []
        for ranking in selected:
            execution = self.execution.execution_price(
                ranking.stock.symbol,
                rebalance_date,
            )
            buy_charges = (
                self.transaction_cost.calculate_buy(
                    allocation
                )
            )
            investable_amount = max(
                0.0,
                allocation - buy_charges.total
            )
            quantity = (
                investable_amount
                / execution.price
                if execution.price > 0
                else 0.0
            )
            holdings.append(
                PortfolioPosition(
                    symbol=ranking.stock.symbol,
                    entry_date=execution.date,
                    entry_rank=ranking.rank,
                    entry_price=execution.price,
                    quantity=quantity,
                    current_price=execution.price,
                    weight=weight,
                    rank=ranking.rank,
                    score=ranking.stock.score,
                    cost_value=allocation,
                    market_value=investable_amount,
                    realized_pnl=0.0,
                    unrealized_pnl=0.0,
                )
            )
        self._update_weights(holdings)
        portfolio = previous_portfolio or Portfolio(
            rebalance_date=rebalance_date,
            holdings=[],
            initial_capital=capital,
            cash=0.0,
            available_cash=0.0,
            is_invested=False,
            trades=[],
        )

        return self._build_portfolio(
            portfolio,
            rebalance_date,
            holdings,
            0.0,
        )

    def rebalance_existing_portfolio(
        self,
        portfolio,
        rankings,
        entry_rankings,
        rebalance_date,
    ):
        rank_lookup = {
            ranking.stock.symbol: ranking
            for ranking in rankings
        }
        universe_size = len(rankings)
        sell_rank = max(
            1,
            int(
                universe_size
                * self.sell_rank_percent
                / 100
            ),
        )
        available_cash = portfolio.cash
        opening_cash = available_cash
        debug_dates = {
            "2015-01-21",
            "2015-02-23",
            "2015-03-23",
        }
        # Process existing holdings
        (
            kept_holdings,
            held_symbols,
            available_cash,
            total_sell_proceeds,
            period_realized_pnl,
        ) = self._process_existing_holdings(
            portfolio,
            rank_lookup,
            sell_rank,
            rebalance_date,
            available_cash,
            debug_dates,
        )
        replacement_count = max(
            0,
            self.portfolio_size - len(kept_holdings),
        )
        total_buy_allocation = 0.0
        if replacement_count > 0:
            (
                kept_holdings,
                held_symbols,
                available_cash,
                total_buy_allocation,
            ) = self._fill_vacant_positions(
                entry_rankings,
                kept_holdings,
                held_symbols,
                available_cash,
                rebalance_date,
                debug_dates,
            )
        remaining_cash = available_cash
        self._update_weights(kept_holdings)
        if str(rebalance_date.date()) not in debug_dates:
            return self._build_portfolio(
                portfolio,
                rebalance_date,
                kept_holdings,
                remaining_cash,
                period_realized_pnl,
            )
        print("\n========== PORTFOLIO AFTER REBALANCE ==========")
        print(f"Date : {rebalance_date}")
        print(f"Opening Cash : {opening_cash:,.2f}")
        print(f"Sell Proceeds: {total_sell_proceeds:,.2f}")
        print(f"Buy Allocation: {total_buy_allocation:,.2f}")
        for h in kept_holdings:
            print(
                f"{h.symbol:12}"
                f" Qty={h.quantity:.4f}"
                f" Cost={h.cost_value:,.2f}"
                f" MV={h.market_value:,.2f}"
                f" UPNL={h.unrealized_pnl:,.2f}"
            )
        print(f"Cash      : {remaining_cash:,.2f}")
        print(f"Invested  : {sum(h.market_value for h in kept_holdings):,.2f}")
        print(f"Total     : {remaining_cash + sum(h.market_value for h in kept_holdings):,.2f}")
        expected_cash = opening_cash + total_sell_proceeds - total_buy_allocation
        print(f"Expected Cash : {expected_cash:,.2f}")
        print(f"Actual Cash   : {remaining_cash:,.2f}")
        print(f"Available Cash      : {available_cash:,.2f}")
        print(f"Replacement Count   : {replacement_count}")
        print(f"Remaining Cash      : {remaining_cash:,.2f}")
        print("==============================================\n")
        return self._build_portfolio(
            portfolio,
            rebalance_date,
            kept_holdings,
            remaining_cash,
            period_realized_pnl,
        )

    def _process_existing_holdings(
        self,
        portfolio,
        rank_lookup,
        sell_rank,
        rebalance_date,
        available_cash,
        debug_dates,
    ):
        kept_holdings = []
        held_symbols = set()
        total_sell_proceeds = 0.0
        period_realized_pnl = 0.0
        for position in portfolio.holdings:
            self._apply_corporate_actions(position, rebalance_date)
            self._mark_to_market(position, rebalance_date)
            ranking = rank_lookup.get(position.symbol)
            if ranking is None or ranking.rank > sell_rank:
                period_realized_pnl += (
                    position.market_value
                    - position.cost_value
                    - self.transaction_cost.calculate_sell(
                        position.market_value
                    ).total
                )
                proceeds = self._sell_holding(
                    portfolio,
                    position,
                    rebalance_date,
                    SellReason.RANK_EXIT,
                    exit_rank=(ranking.rank if ranking is not None else None),
                )
                total_sell_proceeds += proceeds
                available_cash += proceeds
                continue
            self._keep_holding(
                position,
                ranking,
                kept_holdings,
                held_symbols,
            )
            if str(rebalance_date.date()) in debug_dates:
                print(
                    f"KEEP {position.symbol} "
                    f"Cost={position.cost_value:,.2f} "
                    f"MV={position.market_value:,.2f} "
                    f"Rank={ranking.rank}"
                )
        return (
            kept_holdings,
            held_symbols,
            available_cash,
            total_sell_proceeds,
            period_realized_pnl,
        )

    def _fill_vacant_positions(
        self,
        rankings,
        kept_holdings,
        held_symbols,
        available_cash,
        rebalance_date,
        debug_dates,
    ):
        total_buy_allocation = 0.0

        for ranking in rankings:

            if len(kept_holdings) >= self.portfolio_size:
                break

            if ranking.stock.symbol in held_symbols:
                continue

            remaining_slots = (
                self.portfolio_size
                - len(kept_holdings)
            )

            if remaining_slots <= 0:
                break

            allocation = (
                available_cash
                / remaining_slots
            )

            position = self._buy_replacement(
                ranking,
                allocation,
                rebalance_date,
            )

            if str(rebalance_date.date()) in debug_dates:
                print(
                    f"BUY  {position.symbol} "
                    f"Allocation={allocation:,.2f} "
                    f"Cost={position.cost_value:,.2f} "
                    f"MV={position.market_value:,.2f}"
                )

            kept_holdings.append(position)
            held_symbols.add(position.symbol)

            total_buy_allocation += allocation
            available_cash -= allocation

        return (
            kept_holdings,
            held_symbols,
            available_cash,
            total_buy_allocation,
        )
