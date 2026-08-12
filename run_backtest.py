from datetime import datetime
import os

from bootstrap import Bootstrap
from services.universe_service import UniverseService


bootstrap = Bootstrap()

calendar = bootstrap.signal_calendar_service()

backtest = bootstrap.backtest_service()

universe = UniverseService()

universe_name = bootstrap.context.config[
    "universe"
]["name"]

symbols = universe.get_universe(
    universe_name.lower()
)

start_date = datetime.fromisoformat(
    os.getenv("BACKTEST_START_DATE", "2016-01-01")
)
end_date = datetime.fromisoformat(
    os.getenv("BACKTEST_END_DATE", datetime.today().date().isoformat())
)

signal_dates = calendar.signal_dates(
    start_date=start_date,
    end_date=end_date,
)

trading_dates = calendar.trading_dates(
    start_date=start_date,
    end_date=end_date,
)

result = backtest.run(
    symbols=symbols,
    trading_dates=trading_dates,
    rebalance_dates=signal_dates,
)

print()
print("=" * 60)
print(f"Periods Created : {len(result.periods)}")
print("=" * 60)
print()

if result.periods:
    print("First 5 period returns:")
    for period in result.periods[:5]:
        print(period.performance.period_return)
    print()

print(result.metrics)

print()
print("=" * 60)
print("CSV reports generated successfully")
print("Location : reports/output")
print("=" * 60)
print()
