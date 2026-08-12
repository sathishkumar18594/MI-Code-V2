from models.holding import Holding


class HoldingService:

    def create(

        self,

        symbol,

        entry_date,

        entry_price,

        weight,

        rank,

        score,

        capital,

    ):

        invested = capital * weight

        quantity = invested / entry_price

        return Holding(

            symbol=symbol,

            entry_date=entry_date,

            entry_price=entry_price,

            quantity=quantity,

            current_price=entry_price,

            current_rank=rank,

            current_score=score,

            weight=weight,

            cost_value=invested,

            market_value=invested,

            realized_pnl=0.0,

            unrealized_pnl=0.0,

        )