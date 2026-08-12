#!/usr/bin/env python3
"""Audit independent weekly Supertrend regimes for sector sleeves."""

from pathlib import Path
import sys

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from indicators.supertrend_indicator import SupertrendIndicator
from utils.timeframe_converter import TimeframeConverter


CONFIG = Path("config/sector_portfolio.yaml")
OUTPUT = Path("reports/sector_regimes")


def intervals(index_name: str, weekly: pd.DataFrame) -> list[dict]:
    changes = weekly["trend"].ne(weekly["trend"].shift()).cumsum()
    rows = []
    for _, group in weekly.groupby(changes):
        first, last = group.iloc[0], group.iloc[-1]
        rows.append({
            "index_name": index_name,
            "regime": "BULLISH" if first["trend"] == 1 else "BEARISH",
            "start_date": first["Date"],
            "end_date": last["Date"],
            "weeks": len(group),
            "days": (last["Date"] - first["Date"]).days + 1,
            "start_close": first["Close"],
            "end_close": last["Close"],
            "return_pct": (last["Close"] / first["Close"] - 1) * 100,
        })
    return rows


def main():
    config = yaml.safe_load(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    trends, regime_rows = {}, []
    for sleeve in config["sleeves"]:
        name = sleeve["index_name"]
        daily = pd.read_parquet(Path("data/indices") / f"{name}.parquet")
        weekly = TimeframeConverter.convert(daily, "WEEKLY")
        weekly = SupertrendIndicator().execute(weekly, period=1, multiplier=2.5)
        trends[name] = weekly.set_index("Date")["trend"].rename(name)
        regime_rows.extend(intervals(name, weekly))

    regimes = pd.DataFrame(regime_rows).sort_values(["index_name", "start_date"])
    regimes.to_csv(OUTPUT / "regime_intervals.csv", index=False)

    trend_grid = pd.concat(trends.values(), axis=1).sort_index().ffill()
    trend_grid.index.name = "date"
    trend_grid["available_sectors"] = trend_grid.notna().sum(axis=1)
    trend_grid["bullish_sectors"] = (trend_grid == 1).sum(axis=1)
    trend_grid["bearish_sectors"] = (trend_grid == -1).sum(axis=1)
    trend_grid["selected_sectors_max_5"] = trend_grid["bullish_sectors"].clip(upper=5)
    trend_grid["stock_slots_top_2_each"] = trend_grid["selected_sectors_max_5"] * 2
    trend_grid.to_csv(OUTPUT / "weekly_regime_concurrency.csv")

    summary = trend_grid.groupby("bullish_sectors", as_index=False).agg(
        weeks=("selected_sectors_max_5", "size"),
        first_date=("selected_sectors_max_5", lambda s: s.index.min()),
        last_date=("selected_sectors_max_5", lambda s: s.index.max()),
        average_selected_sectors=("selected_sectors_max_5", "mean"),
        average_stock_slots=("stock_slots_top_2_each", "mean"),
    )
    summary.to_csv(OUTPUT / "bullish_sector_distribution.csv", index=False)
    # Sector selection: use the same 9/6/3-month momentum and inverse
    # 3-month volatility factors as the stock scorer, but only within the
    # sectors that are already Supertrend-bullish on that date.
    prices = {}
    for sleeve in config["sleeves"]:
        name = sleeve["index_name"]
        prices[name] = pd.read_parquet(Path("data/indices") / f"{name}.parquet").set_index("Date")["Close"]
    closes = pd.concat(prices, axis=1).sort_index()
    weekly_close = closes.resample("W-FRI").last().ffill()
    return_3m = weekly_close.pct_change(13)
    return_6m = weekly_close.pct_change(26)
    return_9m = weekly_close.pct_change(39)
    volatility_3m = weekly_close.pct_change().rolling(13).std()
    ranking_rows = []
    for date, regime in trend_grid.iterrows():
        if date not in weekly_close.index:
            continue
        eligible = [name for name in trends if regime.get(name) == 1]
        factors = pd.DataFrame({
            "return_3m": return_3m.loc[date].reindex(eligible),
            "return_6m": return_6m.loc[date].reindex(eligible),
            "return_9m": return_9m.loc[date].reindex(eligible),
            "volatility_3m": volatility_3m.loc[date].reindex(eligible),
        }).dropna()
        if factors.empty:
            continue
        normalized = (factors - factors.min()) / (factors.max() - factors.min()).replace(0, 1)
        factors["sector_score"] = (
            normalized["return_9m"] * 0.35 + normalized["return_6m"] * 0.40
            + normalized["return_3m"] * 0.25 + (1 - normalized["volatility_3m"]) * 0.20
        ) / 1.20
        factors = factors.sort_values("sector_score", ascending=False)
        factors["sector_rank"] = range(1, len(factors) + 1)
        factors["selected_top_5"] = factors["sector_rank"] <= 5
        factors.insert(0, "date", date)
        factors.insert(1, "index_name", factors.index)
        ranking_rows.append(factors.reset_index(drop=True))
    rankings = pd.concat(ranking_rows, ignore_index=True)
    rankings.to_csv(OUTPUT / "sector_rankings.csv", index=False)
    rankings[rankings["date"] == rankings["date"].max()].to_csv(
        OUTPUT / "latest_sector_selection.csv", index=False
    )
    print(f"Wrote {len(regimes)} regime intervals for {len(trends)} sectors to {OUTPUT}")


if __name__ == "__main__":
    main()
