#!/usr/bin/env python3
"""Download sector-index OHLC data from NSE's public historical-index API.

The NSE endpoint is session-protected, so this script establishes a fresh
browser-like session, downloads one calendar year per request, and stores the
normalised data under ``data/indices`` for the sector backtest.
"""

from __future__ import annotations

import argparse
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
import yaml


BASE_URL = "https://www.nseindia.com"
API = BASE_URL + "/api/historicalOR/indicesHistory"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE_URL + "/reports-indices-historical-index-data",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36",
}

# NSE display names are not always a simple underscore-to-space conversion.
OFFICIAL_NAMES = {
    "NIFTY_FINANCIAL_SERVICES_EX_BANK": "NIFTY FINANCIAL SERVICES EX-BANK",
    "NIFTY_HEALTHCARE": "NIFTY HEALTHCARE INDEX",
    "NIFTY_MIDSMALL_FINANCIAL_SERVICES": "NIFTY MIDSMALL FINANCIAL SERVICES",
    "NIFTY_MIDSMALL_HEALTHCARE": "NIFTY MIDSMALL HEALTHCARE",
    "NIFTY_MIDSMALL_IT_TELECOM": "NIFTY MIDSMALL IT & TELECOM",
    "NIFTY_OIL_GAS": "NIFTY OIL & GAS",
}


def fetch(session: requests.Session, index_name: str, start: date, end: date) -> list[dict]:
    params = {
        "indexType": OFFICIAL_NAMES.get(index_name, index_name.replace("_", " ")),
        "from": start.strftime("%d-%m-%Y"),
        "to": end.strftime("%d-%m-%Y"),
    }
    for attempt in range(4):
        response = session.get(API, params=params, timeout=60)
        if response.status_code == 200:
            body = response.json()
            return body.get("data", [])
        if response.status_code not in {429, 500, 502, 503}:
            response.raise_for_status()
        time.sleep(2 * (attempt + 1))
    response.raise_for_status()
    raise RuntimeError("unreachable")


def normalise(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume", "Turnover"])
    result = pd.DataFrame({
        "Date": pd.to_datetime(frame["EOD_TIMESTAMP"], format="%d-%b-%Y"),
        "Open": pd.to_numeric(frame["EOD_OPEN_INDEX_VAL"]),
        "High": pd.to_numeric(frame["EOD_HIGH_INDEX_VAL"]),
        "Low": pd.to_numeric(frame["EOD_LOW_INDEX_VAL"]),
        "Close": pd.to_numeric(frame["EOD_CLOSE_INDEX_VAL"]),
        "Volume": pd.to_numeric(frame.get("HIT_TRADED_QTY"), errors="coerce"),
        "Turnover": pd.to_numeric(frame.get("HIT_TURN_OVER"), errors="coerce"),
    })
    return result.drop_duplicates("Date").sort_values("Date").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/sector_portfolio.yaml")
    parser.add_argument("--output", default="data/indices")
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--indices", nargs="+", help="Internal index names to download (default: all sleeves).")
    args = parser.parse_args()

    sleeves = yaml.safe_load(Path(args.config).read_text())["sleeves"]
    indices = sorted({sleeve["index_name"] for sleeve in sleeves})
    if args.indices:
        unknown = sorted(set(args.indices) - set(indices))
        if unknown:
            parser.error(f"Not in config: {', '.join(unknown)}")
        indices = args.indices
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)
    bootstrap = session.get(HEADERS["Referer"], timeout=60)
    bootstrap.raise_for_status()

    for index_name in indices:
        chunks = []
        for year in range(args.start_year, args.end_year + 1):
            start = date(year, 1, 1)
            final_day = min(date(year, 12, 31), date.today())
            while start <= final_day:
                # NSE returns at most 70 observations.  60 calendar days
                # stays below that limit even when all weekdays trade.
                end = min(start + timedelta(days=59), final_day)
                print(f"Downloading {index_name}: {start} to {end}", flush=True)
                chunks.append(normalise(fetch(session, index_name, start, end)))
                start = end + timedelta(days=1)
                time.sleep(0.35)
        data = pd.concat(chunks, ignore_index=True).drop_duplicates("Date").sort_values("Date")
        data.to_parquet(output / f"{index_name}.parquet", index=False)
        print(f"Saved {index_name}: {len(data)} rows", flush=True)


if __name__ == "__main__":
    main()
