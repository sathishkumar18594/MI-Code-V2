from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from providers.upstox_stock_provider import sync_stock, sync_universe


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


def test_stock_sync_uses_current_day_endpoint_after_market_close(tmp_path):
    requested = []

    class Response:
        def __init__(self, candles):
            self.candles = candles

        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "success", "data": {"candles": self.candles}}

    def fake_get(url, **kwargs):
        requested.append(url)
        return Response(
            [candle("2026-08-13", 103)] if "/intraday/" in url else []
        )

    result = sync_stock(
        "ABC", "INE000A01001", tmp_path / "data_v2",
        start_date=date(2026, 8, 13),
        to_date=date(2026, 8, 13),
        token="token",
        request_get=fake_get,
        now=datetime(2026, 8, 13, 16, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
    )

    assert any("/intraday/" in url for url in requested)
    assert result["status"] == "UPDATED"
    assert result["rows_added"] == 1


def test_sync_fills_entire_gap_from_each_stocks_latest_saved_date(tmp_path):
    root = tmp_path / "data_v2"
    parquet = root / "upstox" / "parquet_by_isin" / "INE000A01001.parquet"
    parquet.parent.mkdir(parents=True)
    pd.DataFrame({"date": pd.to_datetime(["2026-01-02"])}).to_parquet(
        parquet, index=False
    )
    requested = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "success",
                "data": {
                    "candles": [
                        candle("2026-01-05", 101),
                        candle("2026-04-01", 110),
                        candle("2026-07-03", 120),
                    ]
                },
            }

    def fake_get(url, **kwargs):
        requested["url"] = url
        return Response()

    result = sync_stock(
        "ABC", "INE000A01001", root,
        to_date=date(2026, 7, 3), token="token", request_get=fake_get,
    )

    assert requested["url"].endswith("/2026-07-03/2026-01-03")
    assert result["rows_added"] == 3
    assert pd.read_parquet(parquet)["date"].dt.date.tolist() == [
        date(2026, 1, 2), date(2026, 1, 5), date(2026, 4, 1), date(2026, 7, 3)
    ]


def test_universe_refresh_happens_before_members_are_synced(tmp_path, monkeypatch):
    root = tmp_path / "data_v2"

    def fake_refresh(self, universe):
        frame = pd.DataFrame({"Symbol": ["ABC"], "ISIN Code": ["INE000A01001"]})
        self.folder.mkdir(parents=True, exist_ok=True)
        frame.to_csv(self.folder / f"{universe}.csv", index=False)
        return frame

    monkeypatch.setattr(
        "providers.upstox_stock_provider.UniverseService.refresh", fake_refresh
    )

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "success", "data": {"candles": [candle("2026-08-13", 103)]}}

    manifest = sync_universe(
        data_root=root,
        start_date=date(2026, 8, 13),
        to_date=date(2026, 8, 13),
        token="token",
        request_get=lambda *args, **kwargs: Response(),
        pause_seconds=0,
        refresh_universe=True,
    )

    report = pd.read_csv(manifest)
    assert report[["symbol", "status", "rows_added"]].to_dict("records") == [
        {"symbol": "ABC", "status": "UPDATED", "rows_added": 1}
    ]
