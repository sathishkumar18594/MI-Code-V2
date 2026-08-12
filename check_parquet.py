import pandas as pd

from application.app_context import AppContext

context = AppContext()
repository = context.price_repository

df = repository.load("HFCL")

df["Date"] = pd.to_datetime(df["Date"])

df = df.sort_values("Date")

print(df.tail(80)[["Date", "Close"]].to_string(index=False))

latest = df.iloc[-1]
print("\nLatest Date:", latest["Date"])
print("Latest Close:", latest["Close"])

for months in [3, 6, 9]:
    periods = months * 21
    lookback = len(df) - 1 - periods
    if lookback < 0:
        continue
    previous = df.iloc[lookback]
    manual_return = (
        (latest["Close"] / previous["Close"]) - 1
    ) * 100
    print(f"\n===== {months}M =====")
    print(f"Trading Days : {periods}")
    print(f"Lookback Date: {previous['Date'].date()}")
    print(f"Lookback Close: {previous['Close']:.2f}")
    print(f"Latest Close  : {latest['Close']:.2f}")
    print(f"Manual Return : {manual_return:.2f}%")