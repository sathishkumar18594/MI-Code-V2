"""Portfolio operations for the combined, independently managed index sleeves."""

from models.portfolio_position import PortfolioPosition
from models.portfolio_sleeve import PortfolioSleeve
from services.execution_price_service import ExecutionPriceService
from services.transaction_cost_service import TransactionCostService
import yaml
from pathlib import Path
import pandas as pd
import math


class MultiUniversePortfolioManager:
    def __init__(self, context, config=None):
        self.context = context
        self.execution = ExecutionPriceService(context)
        self.transaction_cost = TransactionCostService(context)
        self.hedge_symbol = context.config.get("market_hedge", {}).get("symbol", "GOLDBEES")
        self.config = config or yaml.safe_load(
            Path("config/multi_universe_portfolio.yaml").read_text()
        )
        self.hedge_enabled = self.config.get(
            "market_hedge", {}
        ).get("enabled", True)
        self.events = []
        self.decision_date = None

    def create_sleeves(self):
        return {
            item["universe"]: PortfolioSleeve(
                universe=item["universe"],
                capital=float(item["capital"]),
                portfolio_size=int(item["portfolio_size"]),
                cash=float(item["capital"]),
            )
            for item in self.config["sleeves"]
        }

    def mark_to_market(self, sleeve, date):
        for position in sleeve.holdings:
            self._apply_corporate_actions(position, date)
            prices = self.context.price_repository.load(position.symbol)
            prices = prices[prices["Date"] <= date]
            if prices.empty:
                continue
            position.current_price = float(prices.iloc[-1]["Close"])
            position.market_value = position.quantity * position.current_price
            position.unrealized_pnl = position.market_value - position.cost_value

    @staticmethod
    def _apply_corporate_actions(position, date):
        """Apply verified share-exchange actions before price lookup."""
        if position.symbol == "JBCHEPHARM" and pd.Timestamp(date) >= pd.Timestamp("2026-07-17"):
            # 100 J.B. Chemicals shares convert to 51 Torrent Pharma shares.
            position.symbol = "TORNTPHARM"
            position.quantity *= 0.51
            position.entry_price /= 0.51

    def liquidate(self, sleeve, date, reason):
        self.mark_to_market(sleeve, date)
        for position in sleeve.holdings:
            sleeve.cash += self._sell_position(sleeve, position, date, reason)
        sleeve.holdings.clear()

    def buy_rankings(self, sleeve, rankings, date, reason="MONTHLY_ENTRY", skip_unpriced=False):
        """Buy the supplied unique ranking entries using this sleeve's cash."""
        if not rankings or sleeve.cash <= 0:
            return
        allocation = sleeve.cash / len(rankings)
        sleeve.cash = 0.0
        for ranking in rankings:
            symbol = ranking.stock.symbol
            if symbol == "JBCHEPHARM" and pd.Timestamp(date) >= pd.Timestamp("2026-07-17"):
                symbol = "TORNTPHARM"
            try:
                execution = self.execution.execution_price(symbol, date)
            except ValueError:
                if skip_unpriced:
                    continue
                raise
            charges = self.transaction_cost.calculate_buy(allocation)
            invested = max(0.0, allocation - charges.total)
            sleeve.holdings.append(PortfolioPosition(
                symbol=symbol,
                entry_date=execution.date,
                entry_rank=ranking.rank,
                entry_price=execution.price,
                quantity=invested / execution.price if execution.price else 0.0,
                current_price=execution.price,
                weight=0.0,
                rank=ranking.rank,
                score=ranking.score,
                cost_value=allocation,
                market_value=invested,
            ))
            self._record_buy(
                sleeve, symbol, self.decision_date or date, execution.date,
                ranking.rank, ranking.score, execution.price,
                invested / execution.price if execution.price else 0.0,
                allocation, charges, reason,
            )
        self._update_weights(sleeve)

    def buy_hedge(self, sleeve, date):
        execution = self.execution.execution_price(self.hedge_symbol, date)
        allocation = sleeve.cash
        charges = self.transaction_cost.calculate_buy(allocation)
        invested = max(0.0, allocation - charges.total)
        sleeve.cash = 0.0
        sleeve.holdings = [PortfolioPosition(
            symbol=self.hedge_symbol,
            entry_date=execution.date,
            entry_rank=0,
            entry_price=execution.price,
            quantity=invested / execution.price if execution.price else 0.0,
            current_price=execution.price,
            weight=1.0,
            rank=0,
            score=0.0,
            cost_value=allocation,
            market_value=invested,
        )]
        self._record_buy(
            sleeve, self.hedge_symbol, self.decision_date or date, execution.date, 0, 0.0,
            execution.price, invested / execution.price if execution.price else 0.0,
            allocation, charges, "MARKET_BEARISH_HEDGE",
        )

    def update_sleeve(
        self,
        sleeve,
        market_bullish,
        rankings,
        entry_rankings,
        date,
        is_rebalance_day,
        reserved_symbols,
        signal_date=None,
        evaluate_ranks=True,
        allow_daily_refill=True,
        skip_unpriced_entries=False,
        protect_portfolio_ranks=False,
        rank_exit_fraction=None,
        entry_reason=None,
        allow_regime_reentry=False,
        regime_entry_signal=False,
        rank_exit_enabled=True,
        stop_loss_pct=None,
    ):
        """Apply one day's rules to one sleeve and return symbols now held.

        ``reserved_symbols`` contains stock symbols held by earlier sleeves
        and prevents a later sleeve from reusing them at entry.
        """
        self.decision_date = signal_date if signal_date is not None else date
        # Non-negotiable sector-strategy capacity guard.  It also protects
        # reports from historical rotation edge cases.
        equity_positions = [p for p in sleeve.holdings if p.symbol != self.hedge_symbol]
        if len(equity_positions) > sleeve.portfolio_size:
            for position in equity_positions[sleeve.portfolio_size:]:
                sleeve.cash += self._sell_position(sleeve, position, date, "CAPACITY_EXIT")
                sleeve.holdings.remove(position)
        if not market_bullish:
            if not self.hedge_enabled:
                if sleeve.holdings:
                    self.liquidate(sleeve, date, "MARKET_BEARISH")
            elif self._is_hedged(sleeve):
                self.mark_to_market(sleeve, date)
            else:
                self.liquidate(sleeve, date, "MARKET_BEARISH")
                # An inactive sector sleeve can have zero cash after pooled
                # sector rotation; do not create a zero-value hedge position.
                if sleeve.cash > 0:
                    self.buy_hedge(sleeve, date)
            return reserved_symbols

        regime_reentry = self._is_hedged(sleeve)
        if regime_reentry:
            self.liquidate(sleeve, date, "MARKET_BULLISH")

        self.mark_to_market(sleeve, date)
        if stop_loss_pct is not None and sleeve.holdings:
            survivors = []
            for position in sleeve.holdings:
                prices = self.context.price_repository.load(position.symbol)
                completed = prices[prices["Date"] <= self.decision_date]
                signal_close = float(completed.iloc[-1]["Close"]) if not completed.empty else None
                if signal_close is not None and signal_close <= position.entry_price * (1 - float(stop_loss_pct)):
                    execution = self.execution.execution_price(position.symbol, date)
                    position.current_price = execution.price
                    position.market_value = position.quantity * execution.price
                    sleeve.cash += self._sell_position(sleeve, position, date, "STOP_LOSS")
                else:
                    survivors.append(position)
            sleeve.holdings = survivors
        # Scores are decision-point signals.  Between the monthly rebalance
        # and a sector-regime rotation, holdings are only marked to market.
        if not evaluate_ranks:
            self._update_weights(sleeve)
            return reserved_symbols
        rank_lookup = {ranking.stock.symbol: ranking for ranking in rankings}
        fraction = 0.10 if rank_exit_fraction is None else float(rank_exit_fraction)
        sell_rank = max(1, math.floor(len(rankings) * fraction))
        if protect_portfolio_ranks:
            # A top-N portfolio must not sell an unchanged rank that is still
            # within N merely because 10% of a small universe rounds to one.
            sell_rank = max(sell_rank, sleeve.portfolio_size)
        kept = []
        for position in sleeve.holdings:
            ranking = rank_lookup.get(position.symbol)
            if position.symbol in reserved_symbols:
                sleeve.cash += self._sell_position(
                    sleeve, position, date, "DUPLICATE_EXIT",
                    ranking.rank if ranking is not None else None,
                )
                continue
            if rank_exit_enabled and (ranking is None or ranking.rank > sell_rank):
                sleeve.cash += self._sell_position(
                    sleeve, position, date, "RANK_EXIT",
                    ranking.rank if ranking is not None else None,
                )
                continue
            if ranking is not None:
                position.rank = ranking.rank
                position.score = ranking.score
            kept.append(position)
            reserved_symbols.add(position.symbol)
        sleeve.holdings = kept

        should_fill = (
            is_rebalance_day
            or (allow_regime_reentry and regime_reentry)
            or (allow_regime_reentry and regime_entry_signal)
            or (allow_daily_refill and not sleeve.holdings)
        )
        if should_fill:
            open_slots = max(0, sleeve.portfolio_size - len(sleeve.holdings))
            candidates = []
            if open_slots > 0:
                for ranking in entry_rankings:
                    if ranking.stock.symbol in reserved_symbols:
                        continue
                    if skip_unpriced_entries:
                        try:
                            self.execution.execution_price(ranking.stock.symbol, date)
                        except ValueError:
                            continue
                    candidates.append(ranking)
                    reserved_symbols.add(ranking.stock.symbol)
                    if len(candidates) >= open_slots:
                        break
            self.buy_rankings(
                sleeve, candidates, date,
                entry_reason or ("INITIAL_ENTRY" if not kept else "MONTHLY_REPLACEMENT"),
                skip_unpriced=skip_unpriced_entries,
            )
        self._update_weights(sleeve)
        return reserved_symbols

    def _is_hedged(self, sleeve):
        return bool(sleeve.holdings) and all(
            position.symbol == self.hedge_symbol
            for position in sleeve.holdings
        )

    def _sell_position(self, sleeve, position, date, reason, exit_rank=None):
        charges = self.transaction_cost.calculate_sell(position.market_value)
        proceeds = max(0.0, position.market_value - charges.total)
        self.events.append({
            "decision_date": self.decision_date or date,
            "execution_date": date,
            "universe": sleeve.universe,
            "action": "SELL",
            "symbol": position.symbol,
            "reason": reason,
            "entry_date": position.entry_date,
            "entry_rank": position.entry_rank,
            "exit_rank": exit_rank,
            "score": position.score,
            "price": position.current_price,
            "quantity": position.quantity,
            "gross_value": position.market_value,
            "cost_value": position.cost_value,
            **self._charge_fields(charges),
            "net_value": proceeds,
            "realized_pnl": proceeds - position.cost_value,
        })
        return proceeds

    def _record_buy(
        self, sleeve, symbol, decision_date, execution_date, rank, score,
        price, quantity, allocation, charges, reason,
    ):
        self.events.append({
            "decision_date": decision_date,
            "execution_date": execution_date,
            "universe": sleeve.universe,
            "action": "BUY",
            "symbol": symbol,
            "reason": reason,
            "entry_date": execution_date,
            "entry_rank": rank,
            "exit_rank": None,
            "score": score,
            "price": price,
            "quantity": quantity,
            "gross_value": allocation,
            "cost_value": allocation,
            **self._charge_fields(charges),
            "net_value": allocation - charges.total,
            "realized_pnl": 0.0,
        })

    @staticmethod
    def _charge_fields(charges):
        return {
            "brokerage": charges.brokerage,
            "stt": charges.stt,
            "exchange_charge": charges.exchange_charge,
            "sebi_charge": charges.sebi_charge,
            "gst": charges.gst,
            "stamp_duty": charges.stamp_duty,
            "transaction_cost": charges.total,
        }

    @staticmethod
    def _update_weights(sleeve):
        total = sum(position.market_value for position in sleeve.holdings)
        if total:
            for position in sleeve.holdings:
                position.weight = position.market_value / total
