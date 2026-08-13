"""Streamlit workspace for the migrated MI-Code strategy and QM Upstox data."""
from __future__ import annotations

import os
import csv
from collections import deque
from datetime import datetime
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from repositories.upstox_repository import UpstoxRepository
from services.universe_service import UniverseService
from providers.upstox_index_provider import sync_nifty500_index


ROOT = Path(__file__).parent
DATA_ROOT = ROOT / "data_v2"
REPORT_ROOT = ROOT / "reports" / "output"

st.set_page_config(page_title="MI Code V2", layout="wide")
st.title("MI Code V2")
st.caption("Original MI-Code strategy · QM-Book-Code Upstox/ISIN market-data store")


@st.cache_resource
def repository() -> UpstoxRepository:
    return UpstoxRepository(DATA_ROOT)


@st.cache_data(show_spinner=False)
def load_report(path: str, modified_at: float) -> tuple[dict[str, str], pd.DataFrame]:
    """Load MI-Code CSV reports that may begin with a metadata preamble."""
    del modified_at  # Included only so Streamlit invalidates cache after a run.
    report_path = Path(path)
    with report_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    metadata: dict[str, str] = {}
    header_index = 0
    if rows and rows[0][:1] == ["Trading Date"]:
        while header_index < len(rows) and rows[header_index]:
            row = rows[header_index]
            metadata[row[0]] = row[1] if len(row) > 1 else ""
            header_index += 1
        if header_index < len(rows) and not rows[header_index]:
            header_index += 1

    if header_index >= len(rows):
        return metadata, pd.DataFrame()

    headers = rows[header_index]
    width = len(headers)
    values = [row[:width] + [""] * max(0, width - len(row)) for row in rows[header_index + 1:] if row]
    frame = pd.DataFrame(values, columns=headers)
    for column in frame.columns:
        converted = pd.to_numeric(frame[column], errors="coerce")
        if len(frame) and converted.notna().sum() == frame[column].replace("", pd.NA).notna().sum():
            frame[column] = converted
    return metadata, frame


@st.cache_data(show_spinner=False)
def backtest_universe_size(start: str, end: str) -> int:
    return len(UniverseService().history_symbols("nifty500", start, end))


def run_strategy(command: list[str], environment: dict[str, str], expected_symbols: int) -> tuple[int, str]:
    """Run a strategy command while showing concise data-loading progress."""
    progress = st.progress(0.0, text="Starting strategy process...")
    latest = st.empty()
    tail: deque[str] = deque(maxlen=80)
    processed = 0
    environment = {**environment, "PYTHONUNBUFFERED": "1"}
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        clean = line.rstrip()
        tail.append(clean)
        if clean.startswith(("[LOAD]", "[EXCLUDED]", "[MISSING]")):
            processed += 1
            ratio = min(1.0, processed / max(1, expected_symbols))
            progress.progress(
                ratio,
                text=f"Preparing market data: {processed:,}/{expected_symbols:,} symbols",
            )
            if processed % 10 == 0 or processed == expected_symbols:
                latest.caption(clean)

    return_code = process.wait()
    if return_code == 0:
        progress.progress(1.0, text="Strategy run completed")
    else:
        progress.progress(
            min(1.0, processed / max(1, expected_symbols)),
            text="Strategy run failed",
        )
    return return_code, "\n".join(tail)


def show_backtest_summary() -> None:
    metrics_path = REPORT_ROOT / "metrics.csv"
    monthly_path = REPORT_ROOT / "monthly.csv"
    if not metrics_path.exists():
        return

    metrics = pd.read_csv(metrics_path).iloc[0]
    cards = st.columns(6)
    cards[0].metric("Ending value", f"₹{metrics['final_portfolio_value']:,.0f}")
    cards[1].metric("Total return", f"{metrics['absolute_return']:.1%}")
    cards[2].metric("CAGR", f"{metrics['cagr']:.1%}")
    cards[3].metric("Max drawdown", f"{metrics['max_drawdown']:.1%}")
    cards[4].metric("Trades", f"{int(metrics['total_trades']):,}")
    cards[5].metric("Win rate", f"{metrics['win_rate']:.1%}")

    if monthly_path.exists():
        monthly = pd.read_csv(monthly_path, parse_dates=["rebalance_date"])
        if not monthly.empty:
            st.subheader("Portfolio value")
            st.line_chart(monthly.set_index("rebalance_date")["ending_value"])


def open_reports() -> None:
    st.session_state.workspace = "Reports"


def source_modified_at() -> float:
    """Latest strategy source timestamp used to identify stale report files."""
    sources = [
        ROOT / "services" / "portfolio_manager.py",
        ROOT / "run_current_portfolio.py",
        ROOT / "config" / "strategy.yaml",
    ]
    return max(path.stat().st_mtime for path in sources if path.exists())


page = st.sidebar.radio(
    "Workspace",
    ["Overview", "Run strategy", "Reports"],
    key="workspace",
)
if page == "Overview":
    prices = list((DATA_ROOT / "upstox" / "parquet_by_isin").glob("*.parquet"))
    universes = sorted((DATA_ROOT / "universe").glob("*.csv"))
    token = bool(os.getenv("UPSTOX_ACCESS_TOKEN")) or (ROOT / ".upstox.env").exists()
    index_path = DATA_ROOT / "upstox" / "index" / "NIFTY500.parquet"
    index_frame = pd.read_parquet(index_path, columns=["Date"]) if index_path.exists() else pd.DataFrame()
    index_latest = (
        pd.Timestamp(index_frame["Date"].max()).date().isoformat()
        if not index_frame.empty else "Not downloaded"
    )
    first, second, third, fourth = st.columns(4)
    first.metric("Upstox candle series", f"{len(prices):,}")
    second.metric("Universe files", len(universes))
    third.metric("Upstox credential", "Available" if token else "Not configured")
    fourth.metric("Nifty 500 index", index_latest)
    st.info("Data remains ISIN-keyed in data_v2. The migrated repository resolves strategy symbols through the current Nifty universe files and presents the legacy strategy with its expected OHLCV schema.")
    if st.button("Sync Nifty 500 index", disabled=not token):
        with st.spinner("Downloading only sessions after the latest local index candle..."):
            try:
                output, added = sync_nifty500_index()
            except Exception as error:
                st.error(f"Index sync failed: {error}")
            else:
                st.success(f"Added {added:,} new candles to {output}.")
                st.rerun()
    st.stop()

if page == "Reports":
    reports = sorted(REPORT_ROOT.glob("*.csv")) if REPORT_ROOT.exists() else []
    if not reports:
        st.info("No reports yet. Run a backtest or generate the current portfolio first.")
        st.stop()
    report = st.selectbox("Report", reports, format_func=lambda path: path.name)
    if report.name.startswith("current_") and report.stat().st_mtime < source_modified_at():
        generated = datetime.fromtimestamp(report.stat().st_mtime).strftime("%d %b %Y %H:%M")
        st.warning(
            f"This current-portfolio report is stale (generated {generated}). "
            "Run Current portfolio again to apply the latest strategy rules."
        )
    metadata, frame = load_report(str(report), report.stat().st_mtime)
    summary = st.columns(3)
    summary[0].metric("Rows", f"{len(frame):,}")
    summary[1].metric("Trading date", metadata.get("Trading Date", "—"))
    summary[2].metric("Market data through", metadata.get("Market Data Through", "—"))

    query = st.text_input("Filter rows", placeholder="Type a symbol, rank, value, or date")
    visible = frame
    if query:
        matches = frame.astype(str).apply(
            lambda column: column.str.contains(query, case=False, na=False)
        ).any(axis=1)
        visible = frame.loc[matches]

    page_size = st.selectbox("Rows per page", [25, 50, 100, "All"], index=2)
    if page_size == "All":
        page_frame = visible
    else:
        pages = max(1, (len(visible) + page_size - 1) // page_size)
        selected_page = st.number_input("Page", min_value=1, max_value=pages, value=1)
        start = (selected_page - 1) * page_size
        page_frame = visible.iloc[start:start + page_size]

    st.caption(f"Showing {len(page_frame):,} of {len(visible):,} matching rows · {len(frame):,} total")
    st.dataframe(
        page_frame,
        use_container_width=True,
        hide_index=True,
        height=min(1_200, max(240, 36 * (len(page_frame) + 1))),
    )
    st.download_button("Download CSV", frame.to_csv(index=False), report.name, "text/csv")
    st.stop()

st.subheader("Run MI-Code strategy")
workflow = st.radio("Workflow", ["Current portfolio", "Backtest"], horizontal=True)
if workflow == "Backtest":
    latest_date = repository().latest_trading_date()
    default_end = (latest_date or pd.Timestamp.today()).date()
    st.info(
        "This runs the point-in-time Nifty 500 universe using the original "
        "MI-Code ranking, portfolio, execution, and reporting logic."
    )
    universe_col, coverage_col = st.columns(2)
    universe_col.text_input("Universe", value="NIFTY500", disabled=True)
    coverage_col.text_input(
        "Available market data through",
        value=str(default_end),
        disabled=True,
    )
    start_col, end_col = st.columns(2)
    start = start_col.date_input("Backtest start", value=pd.Timestamp("2016-01-01").date())
    end = end_col.date_input("Backtest end", value=default_end, max_value=default_end)
    invalid_dates = start >= end
    if invalid_dates:
        st.error("Backtest start must be earlier than the end date.")
        expected_symbols = 0
    else:
        expected_symbols = backtest_universe_size(str(start), str(end))
        st.caption(
            f"The selected period requires {expected_symbols:,} unique historical constituents. "
            "Only PASS-gated Upstox ISIN series will be admitted."
        )
    command = [sys.executable, "run_backtest.py"]
    environment = {**os.environ, "BACKTEST_START_DATE": str(start), "BACKTEST_END_DATE": str(end)}
else:
    current = pd.read_csv(DATA_ROOT / "universe" / "nifty500.csv")
    expected_symbols = len(current)
    st.info(
        "Current rules: rank exits and replacements run only on monthly "
        "rebalance signals. Completed buys and sells remain available in the "
        "action history with their original signal and execution details; "
        "market-regime exits and bullish re-entry remain immediate."
    )
    st.caption("Generate the latest Nifty 500 rankings, portfolio, and scheduled actions.")
    command = [sys.executable, "run_current_portfolio.py"]
    environment = os.environ.copy()
    invalid_dates = False

if st.button(f"Run {workflow.lower()}", type="primary", disabled=invalid_dates):
    return_code, log_tail = run_strategy(command, environment, expected_symbols)
    with st.expander("Run log", expanded=return_code != 0):
        st.code(log_tail or "No process output")
    if return_code:
        st.error("Strategy run failed.")
    else:
        load_report.clear()
        st.success("Strategy run completed and reports were generated.")
        if workflow == "Backtest":
            show_backtest_summary()
        st.button("Open generated reports", on_click=open_reports)
