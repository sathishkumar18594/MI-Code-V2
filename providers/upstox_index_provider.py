"""Incremental Upstox Nifty 500 index-candle storage for MI-Code V2."""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import requests


INSTRUMENT_KEY = "NSE_INDEX|Nifty 500"
DEFAULT_OUTPUT = Path("data_v2/upstox/index/NIFTY500.parquet")
DEFAULT_START = date(2020, 1, 1)
COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume", "Open Interest"]
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")
MARKET_DATA_FINAL_AFTER = time(15, 35)


def access_token(project_root: str | Path = ".") -> str:
    token = os.environ.get("UPSTOX_ACCESS_TOKEN", "").strip()
    credentials = Path(project_root) / ".upstox.env"
    if not token and credentials.exists():
        for line in credentials.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "UPSTOX_ACCESS_TOKEN":
                token = value.strip().strip("\"'")
                break
    if not token:
        raise RuntimeError(
            "UPSTOX_ACCESS_TOKEN is not set. Export it or add it to .upstox.env."
        )
    return token


def candles_frame(candles: list[list]) -> pd.DataFrame:
    frame = pd.DataFrame(candles, columns=COLUMNS)
    if frame.empty:
        return frame
    dates = pd.to_datetime(frame["Date"], errors="raise")
    frame["Date"] = dates.map(lambda value: value.tz_localize(None) if value.tzinfo else value)
    for column in COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values("Date").drop_duplicates("Date", keep="last").reset_index(drop=True)


def write_index(frame: pd.DataFrame, output: str | Path = DEFAULT_OUTPUT) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.parquet")
    frame.to_parquet(temporary, index=False)
    temporary.replace(output)
    return output


def current_day_candle_available(to_date: date, now: datetime | None = None) -> bool:
    """Use Upstox intraday daily candles only after the NSE session is final."""
    current = now or datetime.now(INDIA_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=INDIA_TIMEZONE)
    else:
        current = current.astimezone(INDIA_TIMEZONE)
    return to_date == current.date() and current.time() >= MARKET_DATA_FINAL_AFTER


def fetch_current_day_candle(
    instrument_key: str,
    to_date: date,
    token: str,
    request_get,
) -> pd.DataFrame:
    url = (
        "https://api.upstox.com/v3/historical-candle/intraday/"
        f"{quote(instrument_key, safe='')}/days/1"
    )
    response = request_get(
        url,
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"Upstox response was not successful: {payload}")
    frame = candles_frame(payload.get("data", {}).get("candles", []))
    if frame.empty:
        return frame
    return frame[frame["Date"].dt.date == to_date].copy()


def import_index_json(json_path: str | Path, output: str | Path = DEFAULT_OUTPUT) -> Path:
    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    if payload.get("status") != "success":
        raise ValueError(f"Upstox response was not successful: {payload}")
    frame = candles_frame(payload.get("data", {}).get("candles", []))
    if frame.empty:
        raise ValueError(f"No candles found in {json_path}")
    return write_index(frame, output)


def sync_nifty500_index(
    output: str | Path = DEFAULT_OUTPUT,
    start_date: date = DEFAULT_START,
    to_date: date | None = None,
    token: str | None = None,
    request_get=None,
    now: datetime | None = None,
) -> tuple[Path, int]:
    """Append only sessions after the last locally stored index candle."""
    output = Path(output)
    existing = pd.read_parquet(output) if output.exists() else pd.DataFrame(columns=COLUMNS)
    if not existing.empty:
        existing["Date"] = pd.to_datetime(existing["Date"])
        start_date = pd.Timestamp(existing["Date"].max()).date() + timedelta(days=1)

    to_date = to_date or date.today()
    if start_date > to_date:
        return output, 0

    encoded_key = quote(INSTRUMENT_KEY, safe="")
    url = (
        f"https://api.upstox.com/v3/historical-candle/{encoded_key}/days/1/"
        f"{to_date.isoformat()}/{start_date.isoformat()}"
    )
    get = request_get or requests.get
    response = get(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token or access_token()}",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"Upstox response was not successful: {payload}")
    additions = candles_frame(payload.get("data", {}).get("candles", []))
    resolved_token = token or access_token()
    has_to_date = (
        not additions.empty and to_date in set(additions["Date"].dt.date)
    )
    if not has_to_date and current_day_candle_available(to_date, now):
        current_day = fetch_current_day_candle(
            INSTRUMENT_KEY,
            to_date,
            resolved_token,
            get,
        )
        additions = pd.concat([additions, current_day], ignore_index=True)
        if not additions.empty:
            additions = additions.sort_values("Date").drop_duplicates(
                "Date", keep="last"
            )
    if additions.empty:
        return output, 0

    combined = pd.concat([existing, additions], ignore_index=True)
    combined["Date"] = pd.to_datetime(combined["Date"])
    combined = combined.sort_values("Date").drop_duplicates("Date", keep="last")
    write_index(combined, output)
    return output, len(additions)


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintain the Upstox Nifty 500 index parquet.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    import_parser = subparsers.add_parser("import-json")
    import_parser.add_argument("json_path")
    import_parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    sync_parser.add_argument("--to-date", type=date.fromisoformat)
    args = parser.parse_args()

    if args.command == "import-json":
        output = import_index_json(args.json_path, args.output)
        frame = pd.read_parquet(output)
        print(f"Saved {len(frame):,} candles through {pd.Timestamp(frame['Date'].max()).date()} to {output}")
    else:
        output, added = sync_nifty500_index(args.output, to_date=args.to_date)
        frame = pd.read_parquet(output)
        print(f"Added {added:,} candles; latest date is {pd.Timestamp(frame['Date'].max()).date()} in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
