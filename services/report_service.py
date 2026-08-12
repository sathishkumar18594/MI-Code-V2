
from models.backtest_result import BacktestResult


class ReportService:

    def build_monthly_return_matrix(
        self,
        result: BacktestResult,
    ):

        months = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]

        matrix = {}

        grouped = {}
        for period in result.periods:
            date = period.portfolio.rebalance_date
            grouped.setdefault((date.year, date.month), []).append(period)

        for (year, month_number), periods in grouped.items():
            if year not in matrix:
                matrix[year] = {m: None for m in months}
            beginning = periods[0].performance.beginning_value
            ending = periods[-1].performance.ending_value
            monthly_return = (
                (ending - beginning) / beginning if beginning else 0.0
            )
            matrix[year][months[month_number - 1]] = round(monthly_return * 100, 2)

        return matrix
