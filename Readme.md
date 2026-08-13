# MI-Code V2

MI-Code V2 is the original MI-Code strategy migrated to use the audited
QM-Book-Code `data_v2` market-data store. It retains MI-Code's configurations,
ranking, portfolio construction, backtests, and reports while consuming local
Upstox candles keyed by ISIN.

## Data model

`data_v2/` is copied from QM-Book-Code. `UpstoxRepository` resolves MI-Code
symbols from the Nifty universe CSV files to their ISIN parquet candle series,
then normalizes the candles to the original `Date/Open/High/Low/Close/Volume`
contract. No price data is copied, adjusted, or overwritten by the strategy.

The V2 market-cap screen uses QM's point-in-time Nifty 500 market-cap manifest.
The legacy market-index filter is disabled by default because the copied store
does not include a compatible index-candle series.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run streamlit_app.py
```

Refresh the Nifty 500 stock store incrementally. Each Upstox response is first
saved as a raw CSV and then merged into its ISIN Parquet file. Subsequent runs
request only sessions after the latest locally stored candle:

```bash
.venv/bin/python -m providers.upstox_stock_provider sync --universe nifty500
```

The benchmark index has its own updater:

```bash
.venv/bin/python -m providers.upstox_index_provider sync
```

The Streamlit workspace launches the original `run_backtest.py` and
`run_current_portfolio.py` workflows and exposes their generated CSV reports.
