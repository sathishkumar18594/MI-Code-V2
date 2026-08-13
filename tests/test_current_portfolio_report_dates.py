from types import SimpleNamespace

import pandas as pd

from reports.current_portfolio_report_writer import CurrentPortfolioReportWriter


def test_current_portfolio_report_separates_run_date_from_market_data_date(tmp_path):
    writer = CurrentPortfolioReportWriter()
    writer.output_directory = tmp_path
    report = SimpleNamespace(
        trading_date=pd.Timestamp("2026-08-13"),
        market_data_date=pd.Timestamp("2026-08-12"),
        portfolio=SimpleNamespace(holdings=[]),
        rank_lookup={},
    )

    output = writer.write(report)

    assert output.read_text().splitlines()[:3] == [
        "Trading Date,2026-08-13",
        "Market Data Through,2026-08-12",
        "",
    ]
