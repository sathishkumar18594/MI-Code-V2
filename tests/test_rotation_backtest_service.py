from services.rotation_backtest_service import RotationBacktestService


class FakeRegimeData:
    def __init__(self, bullish):
        self.bullish = set(bullish)

    def is_bullish(self, universe, _date):
        return universe in self.bullish


def rotation_service(bullish):
    service = RotationBacktestService.__new__(RotationBacktestService)
    service.priority = ["NIFTY500", "NIFTY200", "NIFTY100", "NIFTY50"]
    service.data = FakeRegimeData(bullish)
    return service


def test_rotation_selects_broadest_bullish_universe():
    service = rotation_service({"NIFTY50", "NIFTY100", "NIFTY200"})

    assert service.active_universe("2025-01-01") == "NIFTY200"


def test_rotation_falls_back_to_large_caps():
    service = rotation_service({"NIFTY50"})

    assert service.active_universe("2025-01-01") == "NIFTY50"


def test_rotation_returns_none_when_all_universes_are_bearish():
    service = rotation_service(set())

    assert service.active_universe("2025-01-01") is None

