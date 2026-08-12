from datetime import datetime

from models.holding import Holding
from models.trade import Trade
from models.sell_reason import SellReason


class TradeService:

    def buy(

        self,

        portfolio,

        symbol,

        entry_price,

        rank,

        score,

        capital,

        entry_date,

    ):

        invested = capital

        quantity = invested / entry_price

        holding = Holding(

            symbol=symbol,

            entry_date=entry_date,

            entry_price=entry_price,

            quantity=quantity,

            current_price=entry_price,

            current_rank=rank,

            current_score=score,

            weight=0.0,

            cost_value=invested,

            market_value=invested,

            realized_pnl=0.0,

            unrealized_pnl=0.0,

        )

        portfolio.cash -= invested

        portfolio.holdings.append(
            holding
        )

        return holding

    def sell(

        self,

        portfolio,

        holding,

        exit_price,

        exit_date,

        reason: SellReason,

    ):

        proceeds = (

            holding.quantity

            * exit_price

        )

        realized = (

            proceeds

            - holding.cost_value

        )

        portfolio.cash += proceeds

        portfolio.realized_pnl += (
            realized
        )

        trade = Trade(

            symbol=holding.symbol,

            entry_date=holding.entry_date,

            exit_date=exit_date,

            entry_price=holding.entry_price,

            exit_price=exit_price,

            quantity=holding.quantity,

            realized_pnl=realized,

            return_pct=(
                realized
                / holding.cost_value
            ),

            holding_days=(
                exit_date
                - holding.entry_date
            ).days,

            sell_reason=reason,

        )

        portfolio.trades.append(
            trade
        )

        portfolio.holdings.remove(
            holding
        )

        return trade