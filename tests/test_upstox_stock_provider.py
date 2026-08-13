from datetime import date

import pandas as pd

from providers.upstox_stock_provider import sync_stock


def candle(day: str, close: float):
    return [f"{day}T00:00:00+05:30", close, close + 1, close - 1, close, 100, 0]


def test_sync_saves_csv_then_incrementally_updates_isin_parquet(tmp_path):
    root = tmp_path / "data_v2"
    parquet = root / "upstox" / "parquet_by_isin" / "INE000A01001.parquet"
    parquet.parent.mkdir(parents=True)
    pd.DataFrame({
        "date": pd.to_datetime(["2026-08-10"]),
        "open": [100], "high": [101], "low": [99], "close": [100],
        "volume": [100], "open_interest": [0], "isin": ["INE000A01001"],
        "adjustment_status": ["PROVIDER_BASIS_REVIEW_REQUIRED"],
    }).to_parquet(parquet, index=False)
    requested = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "success", "data": {"candles": [candle("2026-08-11", 102)]}}

    def fake_get(url, **kwargs):
        requested["url"] = url
        return Response()

    result = sync_stock(
        "ABC", "INE000A01001", root,
        to_date=date(2026, 8, 11), token="token", request_get=fake_get,
    )

    assert requested["url"].endswith("/2026-08-11/2026-08-11")
    assert result["status"] == "UPDATED"
    assert result["rows_added"] == 1
    csv = pd.read_csv(result["csv_path"])
    assert csv["requested_symbol"].tolist() == ["ABC"]
    output = pd.read_parquet(parquet)
    assert output["date"].dt.date.tolist() == [date(2026, 8, 10), date(2026, 8, 11)]


def test_sync_does_not_call_upstox_when_parquet_is_current(tmp_path):
    root = tmp_path / "data_v2"
    parquet = root / "upstox" / "parquet_by_isin" / "INE000A01001.parquet"
    parquet.parent.mkdir(parents=True)
    pd.DataFrame({"date": pd.to_datetime(["2026-08-11"])}).to_parquet(parquet, index=False)

    result = sync_stock(
        "ABC", "INE000A01001", root,
        to_date=date(2026, 8, 11), token="token",
        request_get=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    assert result["status"] == "CURRENT"
    assert result["rows_added"] == 0
