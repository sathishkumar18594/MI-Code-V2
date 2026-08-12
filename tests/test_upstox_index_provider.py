import json
from datetime import date

import pandas as pd

from providers.upstox_index_provider import import_index_json, sync_nifty500_index


def candle(day: str, close: float):
    return [f"{day}T00:00:00+05:30", close, close + 1, close - 1, close, 100, 0]


def test_import_json_materializes_sorted_parquet(tmp_path):
    source = tmp_path / "index.json"
    source.write_text(json.dumps({
        "status": "success",
        "data": {"candles": [candle("2026-08-11", 101), candle("2026-08-10", 100)]},
    }))
    output = tmp_path / "NIFTY500.parquet"

    import_index_json(source, output)

    frame = pd.read_parquet(output)
    assert frame["Date"].dt.date.tolist() == [date(2026, 8, 10), date(2026, 8, 11)]


def test_sync_requests_only_dates_after_latest_candle(tmp_path):
    output = tmp_path / "NIFTY500.parquet"
    pd.DataFrame([candle("2026-08-11", 101)], columns=[
        "Date", "Open", "High", "Low", "Close", "Volume", "Open Interest",
    ]).assign(Date=lambda frame: pd.to_datetime(frame["Date"]).map(lambda value: value.tz_localize(None))).to_parquet(output, index=False)
    requested = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "success", "data": {"candles": [candle("2026-08-12", 102)]}}

    def fake_get(url, **kwargs):
        requested["url"] = url
        return Response()

    _, added = sync_nifty500_index(
        output,
        to_date=date(2026, 8, 12),
        token="test-token",
        request_get=fake_get,
    )

    assert requested["url"].endswith("/2026-08-12/2026-08-12")
    assert added == 1
    assert len(pd.read_parquet(output)) == 2
