"""Run the standalone breadth-rotation momentum backtest."""

import os
from datetime import datetime

from bootstrap import Bootstrap
from services.rotation_backtest_service import RotationBacktestService


bootstrap = Bootstrap()
calendar = bootstrap.signal_calendar_service()
start = datetime.fromisoformat(os.getenv("BACKTEST_START_DATE", "2021-08-09"))
end = datetime.fromisoformat(
    os.getenv("BACKTEST_END_DATE", datetime.today().date().isoformat())
)

result = RotationBacktestService(bootstrap.context).run(
    calendar.trading_dates(start, end),
    calendar.signal_dates(start, end),
    output_directory=os.getenv(
        "ROTATION_OUTPUT",
        "reports/universe_rotation",
    ),
)
print(result["metrics"])

