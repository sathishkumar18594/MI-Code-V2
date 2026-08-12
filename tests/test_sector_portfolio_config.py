from pathlib import Path

import yaml

from services.universe_service import UniverseService


def test_all_requested_sectors_are_configured_as_independent_sleeves():
    config = yaml.safe_load(Path("config/sector_portfolio.yaml").read_text())

    sleeves = config["sleeves"]
    names = [sleeve["universe"] for sleeve in sleeves]

    # The strategy deliberately uses the 19 sector sleeves with usable
    # historical constituent coverage, rather than every current NSE sector.
    assert len(sleeves) == 19
    assert len(names) == len(set(names))
    assert abs(sum(sleeve["capital"] for sleeve in sleeves) - config["initial_capital"]) < 0.01
    assert all(sleeve["portfolio_size"] == 3 for sleeve in sleeves)
    assert all(sleeve["index_name"] == sleeve["universe"] for sleeve in sleeves)
    assert config["market_regime"] == {
        "timeframe": "WEEKLY",
        "supertrend_period": 10,
        "supertrend_multiplier": 3,
    }
    assert config["sector_rotation"]["redeploy_to_bullish"] is True
    assert config["sector_rotation"]["selection_mode"] == "TOP_RANKED_BULLISH"
    assert config["sector_rotation"]["max_selected_sectors"] == 5
    assert config["sector_rotation"]["lock_selected_sectors_until_bearish"] is True
    assert config["sector_rotation"]["sector_score"] == {
        "return_6m_weight": 0.50,
        "return_3m_weight": 0.30,
        "return_1m_weight": 0.20,
    }
    assert config["sector_rotation"]["ranking_scope"] == "UNIVERSE_BEFORE_FILTERS"
    assert config["sector_rotation"]["market_cap_filter_enabled"] is True
    assert config["sector_rotation"]["strict_top_rank_entries"] is True
    assert config["market_hedge"]["enabled"] is False
    assert all(
        sleeve["universe"].lower().replace("_", "") in UniverseService.URLS
        for sleeve in sleeves
    )
