import pandas as pd

from indicators.indicator_pipeline import IndicatorPipeline


df = pd.read_parquet(
    "data/prices/RELIANCE.parquet"
)

df = IndicatorPipeline().execute(df)

columns = [
    "Date",
    "Close",
    "return_3m",
    "return_6m",
    "return_9m",
    "volatility_3m",
    "momentum_score",
]

print(df[columns].tail(20))