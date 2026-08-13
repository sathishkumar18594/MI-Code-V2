from types import SimpleNamespace

import pandas as pd

from services.market_cap_service import MarketCapService


def context(data_file, minimum=10000, yearly_minimums=None):
    return SimpleNamespace(
        config={
            "market_cap_filter": {
                "enabled": True,
                "min_market_cap_crore": minimum,
                "min_market_cap_crore_by_year": yearly_minimums or {},
                "data_file": str(data_file),
            }
        }
    )


def write_history(path):
    pd.DataFrame(
        [
            {
                "as_of_date": "2020-12-31",
                "symbol": "ABC",
                "nse_6m_avg_total_market_cap_crore": 9000,
            },
            {
                "as_of_date": "2021-12-31",
                "symbol": "ABC",
                "nse_6m_avg_total_market_cap_crore": 12000,
            },
            {
                "as_of_date": "2021-12-31",
                "symbol": "AT_LIMIT",
                "nse_6m_avg_total_market_cap_crore": 10000,
            },
            {
                "as_of_date": "2021-12-31",
                "symbol": "ARE&M",
                "nse_6m_avg_total_market_cap_crore": 11000,
            },
            {
                "as_of_date": "2021-12-31",
                "symbol": "OFSS",
                "nse_6m_avg_total_market_cap_crore": 25000,
            },
        ]
    ).to_csv(path, index=False)


def test_uses_latest_observation_available_on_or_before_signal_date(tmp_path):
    data_file = tmp_path / "market_cap.csv"
    write_history(data_file)
    service = MarketCapService(context(data_file))

    assert service.market_cap_as_of("ABC", "2021-06-30") == 9000
    assert service.market_cap_as_of("ABC", "2022-01-01") == 12000
    assert service.market_cap_as_of("ABC", "2020-01-01") is None
    assert service.market_cap_as_of("ARE& M", "2022-01-01") == 11000
    assert service.market_cap_as_of("ORACLE", "2022-01-01") == 25000


def test_filter_is_strictly_greater_than_threshold_and_rejects_missing(tmp_path):
    data_file = tmp_path / "market_cap.csv"
    write_history(data_file)
    service = MarketCapService(context(data_file))
    universe = pd.DataFrame(
        {
            "symbol": ["ABOVE", "AT_LIMIT", "BELOW", "MISSING"],
            "market_cap_crore": [10000.01, 10000, 9999.99, None],
        }
    )

    filtered = service.filter(universe)

    assert filtered["symbol"].tolist() == ["ABOVE"]


def test_filter_uses_threshold_in_force_for_signal_year(tmp_path):
    data_file = tmp_path / "market_cap.csv"
    write_history(data_file)
    service = MarketCapService(
        context(
            data_file,
            minimum=5000,
            yearly_minimums={
                2021: 5000,
                2022: 6000,
                2023: 7000,
                2024: 8000,
                2025: 9000,
                2026: 10000,
            },
        )
    )
    universe = pd.DataFrame(
        {
            "symbol": ["SIX_THOUSAND", "TEN_THOUSAND"],
            "market_cap_crore": [6000, 10000],
        }
    )

    assert service.filter(universe, "2021-06-30")["symbol"].tolist() == [
        "SIX_THOUSAND",
        "TEN_THOUSAND",
    ]
    assert service.filter(universe, "2022-06-30")["symbol"].tolist() == [
        "TEN_THOUSAND"
    ]
    assert service.filter(universe, "2026-06-30").empty
    assert service.minimum_for_date("2027-01-01") == 10000
    assert service.minimum_for_date("2020-12-31") == 5000
