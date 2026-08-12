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

The Streamlit workspace launches the original `run_backtest.py` and
`run_current_portfolio.py` workflows and exposes their generated CSV reports.
