"""Incrementally refresh Nifty stock candles from Upstox CSV into Parquet."""
from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

from providers.upstox_index_provider import (
    access_token,
    current_day_candle_available,
    fetch_current_day_candle,
)


PRICE_COLUMNS = [
    "date", "open", "high", "low", "close", "volume", "open_interest"
]
CSV_COLUMNS = PRICE_COLUMNS + [
    "requested_symbol", "resolved_symbol", "isin", "instrument_key"
]
DEFAULT_START = date(2020, 1, 1)


def _normalise_candles(candles: list[list]) -> pd.DataFrame:
    rows: dict[date, list] = {}
    for candle in candles:
        if not isinstance(candle, (list, tuple)) or len(candle) < 7:
            raise ValueError(f"Malformed Upstox daily candle: {candle!r}")
        day = pd.Timestamp(candle[0]).date()
        values = list(candle[1:7])
        if day in rows and rows[day] != values:
            raise ValueError(f"Conflicting Upstox daily candles for {day}")
        rows[day] = values
    frame = pd.DataFrame(
        [[day, *values] for day, values in rows.items()],
        columns=PRICE_COLUMNS,
    )
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"])
    for column in PRICE_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    invalid = frame["date"].isna() | frame[[
        "open", "high", "low", "close"
    ]].isna().any(axis=1)
    if invalid.any():
        raise ValueError(f"Upstox returned {int(invalid.sum())} invalid candles")
    return frame.sort_values("date").reset_index(drop=True)


def _write_csv(
    frame: pd.DataFrame,
    symbol: str,
    isin: str,
    instrument_key: str,
    start_date: date,
    to_date: date,
    data_root: Path,
) -> Path:
    output = (
        data_root / "upstox" / "candles"
        / f"{symbol}_{start_date.isoformat()}_{to_date.isoformat()}.csv"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    csv_frame = frame.copy()
    csv_frame["date"] = csv_frame["date"].dt.date
    csv_frame["requested_symbol"] = symbol
    csv_frame["resolved_symbol"] = symbol
    csv_frame["isin"] = isin
    csv_frame["instrument_key"] = instrument_key
    temporary = output.with_suffix(".tmp.csv")
    csv_frame[CSV_COLUMNS].to_csv(temporary, index=False)
    temporary.replace(output)
    return output


def _materialize_csv(csv_path: Path, parquet_path: Path, isin: str) -> int:
    """Merge the just-saved provider CSV into the ISIN Parquet atomically."""
    additions = pd.read_csv(csv_path)
    additions = additions[PRICE_COLUMNS].copy()
    additions["date"] = pd.to_datetime(additions["date"])
    existing = (
        pd.read_parquet(parquet_path)
        if parquet_path.exists()
        else pd.DataFrame()
    )
    before = len(existing)
    combined = pd.concat([existing, additions], ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    for column in PRICE_COLUMNS[1:]:
        combined[column] = pd.to_numeric(combined[column], errors="coerce")
    combined = combined.sort_values("date").drop_duplicates("date", keep="last")
    combined["isin"] = isin
    combined["adjustment_status"] = "PROVIDER_BASIS_REVIEW_REQUIRED"
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = parquet_path.with_suffix(".tmp.parquet")
    combined.to_parquet(temporary, index=False)
    temporary.replace(parquet_path)
    return len(combined) - before


def sync_stock(
    symbol: str,
    isin: str,
    data_root: str | Path = "data_v2",
    start_date: date = DEFAULT_START,
    to_date: date | None = None,
    token: str | None = None,
    request_get=None,
    now: datetime | None = None,
) -> dict[str, object]:
    root = Path(data_root)
    parquet = root / "upstox" / "parquet_by_isin" / f"{isin}.parquet"
    if parquet.exists():
        existing = pd.read_parquet(parquet, columns=["date"])
        if not existing.empty:
            start_date = pd.Timestamp(existing["date"].max()).date() + timedelta(days=1)
    to_date = to_date or date.today()
    result = {
        "symbol": symbol,
        "isin": isin,
        "from_date": start_date.isoformat(),
        "to_date": to_date.isoformat(),
        "status": "CURRENT",
        "rows_added": 0,
        "csv_path": "",
        "parquet_path": str(parquet),
        "error": "",
    }
    if start_date > to_date:
        return result

    instrument_key = f"NSE_EQ|{isin}"
    url = (
        "https://api.upstox.com/v3/historical-candle/"
        f"{quote(instrument_key, safe='')}/days/1/"
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
    frame = _normalise_candles(payload.get("data", {}).get("candles", []))
    has_to_date = not frame.empty and to_date in set(frame["date"].dt.date)
    if not has_to_date and current_day_candle_available(to_date, now):
        current_day = fetch_current_day_candle(
            instrument_key,
            to_date,
            token or access_token(),
            get,
        ).rename(columns={
            "Date": "date", "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume", "Open Interest": "open_interest",
        })
        frame = pd.concat([frame, current_day[PRICE_COLUMNS]], ignore_index=True)
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"])
            frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    if frame.empty:
        result["status"] = "NO_NEW_CANDLES"
        return result
    csv_path = _write_csv(
        frame, symbol, isin, instrument_key, start_date, to_date, root
    )
    result["rows_added"] = _materialize_csv(csv_path, parquet, isin)
    result["csv_path"] = str(csv_path)
    result["status"] = "UPDATED"
    return result


def sync_universe(
    universe: str = "nifty500",
    data_root: str | Path = "data_v2",
    start_date: date = DEFAULT_START,
    to_date: date | None = None,
    pause_seconds: float = 0.05,
    token: str | None = None,
    request_get=None,
) -> Path:
    root = Path(data_root)
    universe_path = root / "universe" / f"{universe.lower()}.csv"
    if not universe_path.exists():
        raise FileNotFoundError(f"Universe file not found: {universe_path}")
    members = pd.read_csv(universe_path, dtype=str).fillna("")
    required = {"Symbol", "ISIN Code"}
    if not required.issubset(members.columns):
        raise ValueError(f"{universe_path} is missing {sorted(required - set(members))}")
    resolved_token = token or access_token()
    results = []
    for symbol, isin in members[["Symbol", "ISIN Code"]].itertuples(index=False):
        try:
            result = sync_stock(
                symbol=symbol.strip(),
                isin=isin.strip().upper(),
                data_root=root,
                start_date=start_date,
                to_date=to_date,
                token=resolved_token,
                request_get=request_get,
            )
        except Exception as error:
            result = {
                "symbol": symbol,
                "isin": isin,
                "from_date": "",
                "to_date": (to_date or date.today()).isoformat(),
                "status": "FAILED",
                "rows_added": 0,
                "csv_path": "",
                "parquet_path": str(
                    root / "upstox" / "parquet_by_isin" / f"{isin}.parquet"
                ),
                "error": str(error),
            }
        results.append(result)
        print(
            f"[{result['status']}] {symbol} rows_added={result['rows_added']}"
            + (f" error={result['error']}" if result["error"] else "")
        )
        if pause_seconds:
            time.sleep(pause_seconds)

    manifest_root = root / "upstox" / "manifests"
    manifest_root.mkdir(parents=True, exist_ok=True)
    run_date = (to_date or date.today()).isoformat()
    output = manifest_root / f"{universe.lower()}_incremental_sync_{run_date}.csv"
    pd.DataFrame(results).to_csv(output, index=False)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download Upstox stock CSVs and incrementally update ISIN Parquet."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--universe", default="nifty500")
    sync_parser.add_argument("--data-root", default="data_v2")
    sync_parser.add_argument("--start-date", type=date.fromisoformat, default=DEFAULT_START)
    sync_parser.add_argument("--to-date", type=date.fromisoformat)
    sync_parser.add_argument("--pause-seconds", type=float, default=0.05)
    args = parser.parse_args()
    output = sync_universe(
        universe=args.universe,
        data_root=args.data_root,
        start_date=args.start_date,
        to_date=args.to_date,
        pause_seconds=args.pause_seconds,
    )
    report = pd.read_csv(output)
    print(report.groupby("status").size().to_string())
    print(f"Manifest: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
