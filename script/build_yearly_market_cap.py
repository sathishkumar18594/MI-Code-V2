"""Build annual historical market-cap data for point-in-time NIFTY universes.

The source reports are AMFI's calendar half-year reports.  They contain the
six-month average *total* market capitalisation on NSE, in INR crore.  Using
the average avoids choosing an arbitrary single trading day and matches the
size measure used for SEBI/AMFI stock categorisation.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import pdfplumber


ROOT = Path(__file__).resolve().parents[1]


DEFAULT_SOURCE_DIR = ROOT / "data" / "market_cap" / "source"
DEFAULT_OUTPUT = ROOT / "data" / "market_cap" / "yearly_market_cap.csv"
DEFAULT_ALL_NSE_OUTPUT = ROOT / "data" / "market_cap" / "yearly_market_cap_all_nse.csv"
DEFAULT_MISSING = ROOT / "data" / "market_cap" / "yearly_market_cap_missing.csv"
UNIVERSES = ("nifty50", "nifty100", "nifty200", "nifty500")


def clean_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_symbol(value) -> str:
    value = clean_text(value).upper().replace(" *", "").rstrip("*")
    return value.replace(" ", "")


def parse_crore(value):
    value = clean_text(value).replace(",", "").replace(" ", "")
    if not value or value == "-":
        return pd.NA
    try:
        return float(value)
    except ValueError:
        return pd.NA


def extract_report(pdf_file: Path, year: int, as_of_date: pd.Timestamp) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if len(row) < 11 or not clean_text(row[0]).isdigit():
                        continue
                    nse_symbol = clean_symbol(row[5])
                    symbol = nse_symbol or clean_symbol(row[3])
                    nse_market_cap = parse_crore(row[6])
                    all_exchange_market_cap = parse_crore(row[9])
                    market_cap = (
                        nse_market_cap
                        if not pd.isna(nse_market_cap)
                        else all_exchange_market_cap
                    )
                    if not symbol or pd.isna(market_cap):
                        continue
                    rows.append(
                        {
                            "year": year,
                            "as_of_date": as_of_date.date().isoformat(),
                            "symbol": symbol,
                            "company_name": clean_text(row[1]),
                            "isin": clean_text(row[2]).upper(),
                            "nse_6m_avg_total_market_cap_crore": market_cap,
                            "market_cap_basis": (
                                "NSE_6M_AVERAGE"
                                if not pd.isna(nse_market_cap)
                                else "ALL_EXCHANGES_6M_AVERAGE"
                            ),
                            "size_category": clean_text(row[10]),
                            "source_file": pdf_file.name,
                        }
                    )
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError(f"No market-cap rows extracted from {pdf_file}")
    return frame.sort_values(
        "nse_6m_avg_total_market_cap_crore", ascending=False
    ).drop_duplicates("symbol", keep="first")


def universe_as_of(universe: str, date: pd.Timestamp) -> set[str]:
    history_file = ROOT / "data" / "universe" / "history" / f"{universe}_history.csv"
    history = pd.read_csv(history_file, parse_dates=["effective_date"])
    eligible = history[history["effective_date"] <= date].sort_values("effective_date")
    if eligible.empty:
        raise ValueError(f"No {universe} snapshot exists on or before {date.date()}")
    symbols = str(eligible.iloc[-1]["symbols"]).split(",")
    return {clean_symbol(symbol) for symbol in symbols if clean_symbol(symbol)}


def membership_as_of(date: pd.Timestamp) -> dict[str, set[str]]:
    result = {}
    for universe in UNIVERSES:
        result[universe] = universe_as_of(universe, date)
    return result


def build(
    source_dir: Path,
    output: Path,
    all_nse_output: Path,
    missing_output: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    reports = {}
    for pdf_file in sorted(source_dir.glob("amfi_market_cap_*.pdf")):
        match = re.search(r"(20\d{2})", pdf_file.stem)
        if match:
            reports[int(match.group(1))] = pdf_file
    if not reports:
        raise FileNotFoundError(f"No annual AMFI reports found in {source_dir}")

    annual_frames = []
    missing_rows = []
    for year, pdf_file in sorted(reports.items()):
        as_of_date = pd.Timestamp(year=year, month=6 if year == 2026 else 12, day=30 if year == 2026 else 31)
        market_caps = extract_report(pdf_file, year, as_of_date).set_index("symbol", drop=False)
        memberships = membership_as_of(as_of_date)
        all_symbols = sorted(set().union(*memberships.values()))
        membership_labels = {
            symbol: "|".join(
                name for name, symbols in memberships.items() if symbol in symbols
            )
            for symbol in all_symbols
        }
        market_caps["universes"] = [
            membership_labels.get(symbol, "") for symbol in market_caps.index
        ]
        market_caps["in_tracked_universe"] = market_caps["universes"].ne("")
        annual_frames.append(market_caps.reset_index(drop=True))
        for symbol in all_symbols:
            universes = [name for name, symbols in memberships.items() if symbol in symbols]
            if symbol not in market_caps.index:
                missing_rows.append(
                    {
                        "year": year,
                        "as_of_date": as_of_date.date().isoformat(),
                        "symbol": symbol,
                        "universes": "|".join(universes),
                        "reason": "No matching NSE symbol in AMFI report",
                        "source_file": pdf_file.name,
                    }
                )
                continue
    all_nse = pd.concat(annual_frames, ignore_index=True).sort_values(["year", "symbol"])
    result = all_nse[all_nse["in_tracked_universe"]].copy()
    result = result.drop(columns=["in_tracked_universe"])
    missing = pd.DataFrame(missing_rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    all_nse.to_csv(all_nse_output, index=False)
    missing.to_csv(missing_output, index=False)
    return result, all_nse, missing


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--all-nse-output", type=Path, default=DEFAULT_ALL_NSE_OUTPUT)
    parser.add_argument("--missing-output", type=Path, default=DEFAULT_MISSING)
    args = parser.parse_args()
    result, all_nse, missing = build(
        args.source_dir,
        args.output,
        args.all_nse_output,
        args.missing_output,
    )
    coverage = result.groupby("year")["symbol"].nunique()
    gaps = missing.groupby("year")["symbol"].nunique() if not missing.empty else pd.Series(dtype=int)
    print("Annual market-cap coverage:")
    for year, count in coverage.items():
        print(
            f"  {year}: {count} universe stocks matched, "
            f"{int(gaps.get(year, 0))} universe mismatches"
        )
    print(f"Saved {len(result)} rows to {args.output}")
    print(f"Saved {len(all_nse)} source rows to {args.all_nse_output}")
    print(f"Saved {len(missing)} unmatched rows to {args.missing_output}")


if __name__ == "__main__":
    main()
