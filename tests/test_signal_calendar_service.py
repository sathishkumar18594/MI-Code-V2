import pandas as pd

from services.signal_calendar_service import (
    SignalCalendarService,
)


def test_signal_calendar_service():

    service = SignalCalendarService()

    dates = service.signal_dates(

        start_date=pd.Timestamp(
            "2025-01-01"
        ),

        end_date=pd.Timestamp(
            "2025-12-31"
        ),

    )

    print()

    for date in dates:

        print(
            date.strftime("%d-%b-%Y")
        )

    assert len(dates) == 12