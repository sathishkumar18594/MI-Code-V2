import pandas as pd

from indicators.momentum_indicator import MomentumIndicator
from indicators.risk_adjusted_momentum_indicator import (
    RiskAdjustedMomentumIndicator,
)
from indicators.volatility_indicator import (
    VolatilityIndicator,
)


def test_risk_adjusted_momentum_indicator():

    df = pd.read_parquet(
        "data/prices/RELIANCE.parquet"
    )

    df = MomentumIndicator().execute(df)

    df = VolatilityIndicator().execute(df)

    df = (
        RiskAdjustedMomentumIndicator()
        .execute(df)
    )

    assert "momentum_score" in df.columns

    latest = df.iloc[-1]

    assert pd.notna(
        latest["momentum_score"]
    )