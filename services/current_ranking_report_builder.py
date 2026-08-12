

from models.current_ranking_report import CurrentRankingReport


class CurrentRankingReportBuilder:

    def __init__(
        self,
        scoring_service,
    ):
        self.scoring_service = scoring_service

    def build(
        self,
        trading_date,
        rankings,
    ):

        enabled_factors = list(
            self.scoring_service
            .get_enabled_factors()
            .keys()
        )

        return CurrentRankingReport(
            trading_date=trading_date,
            rankings=rankings,
            enabled_factors=enabled_factors,
        )