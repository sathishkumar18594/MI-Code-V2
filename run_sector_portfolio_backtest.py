"""Run the independent all-sector momentum portfolio backtest."""

import os
from datetime import datetime

from bootstrap import Bootstrap
from services.multi_universe_backtest_service import MultiUniverseBacktestService


bootstrap = Bootstrap()
os.environ.setdefault("MULTI_UNIVERSE_CONFIG", "config/sector_portfolio.yaml")
calendar = bootstrap.signal_calendar_service()
start = datetime.fromisoformat(os.getenv("BACKTEST_START_DATE", "2021-08-09"))
end = datetime.fromisoformat(os.getenv("BACKTEST_END_DATE", datetime.today().date().isoformat()))

result = MultiUniverseBacktestService(bootstrap.context).run(
    calendar.trading_dates(start, end),
    calendar.signal_dates(start, end),
    output_directory=os.getenv("SECTOR_OUTPUT", "reports/sector_portfolio"),
)
print(result["metrics"])
