from enum import Enum


class RebalanceAction(str, Enum):

    BUY = "BUY"

    HOLD = "HOLD"

    SELL = "SELL"