import math


class ReturnCalculator:

    @staticmethod
    def simple(
        buy_price: float,
        sell_price: float,
    ) -> float:

        return (
            sell_price
            - buy_price
        ) / buy_price

    @staticmethod
    def logarithmic(
        buy_price: float,
        sell_price: float,
    ) -> float:

        return math.log(
            sell_price / buy_price
        )