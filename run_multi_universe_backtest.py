"""Run the standalone combined portfolio backtest."""

import os
from datetime import datetime

from bootstrap import Bootstrap
from services.multi_universe_backtest_service import MultiUniverseBacktestService


context = Bootstrap().context
calendar = Bootstrap().signal_calendar_service()
start = datetime.fromisoformat(os.getenv("BACKTEST_START_DATE", "2021-08-09"))
end = datetime.fromisoformat(os.getenv("BACKTEST_END_DATE", datetime.today().date().isoformat()))
result = MultiUniverseBacktestService(context).run(
    calendar.trading_dates(start, end),
    calendar.signal_dates(start, end),
    output_directory=os.getenv(
        "MULTI_UNIVERSE_OUTPUT",
        "reports/multi_universe",
    ),
)
print(result["metrics"])
