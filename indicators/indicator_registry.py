from indicators.momentum_indicator import MomentumIndicator
from indicators.risk_adjusted_momentum_indicator import (
    RiskAdjustedMomentumIndicator,
)
from indicators.volatility_indicator import VolatilityIndicator


INDICATOR_REGISTRY = {
    "momentum": MomentumIndicator,
    "volatility": VolatilityIndicator,
    "risk_adjusted_momentum": RiskAdjustedMomentumIndicator,
}