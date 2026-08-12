from models.current_portfolio_report import (
    CurrentPortfolioReport,
)


class CurrentPortfolioReportBuilder:

    def build(
        self,
        trading_date,
        portfolio,
        rankings,
    ):
        rank_lookup = self._build_rank_lookup(
            rankings,
        )

        return CurrentPortfolioReport(
            trading_date=trading_date,
            portfolio=portfolio,
            rank_lookup=rank_lookup,
        )

    def _build_rank_lookup(
        self,
        rankings,
    ):

        return {
            ranking.stock.symbol: ranking
            for ranking in rankings
        }