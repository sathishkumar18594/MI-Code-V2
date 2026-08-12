from dataclasses import dataclass


@dataclass(slots=True)
class TradeCharges:

    brokerage: float

    stt: float

    exchange_charge: float

    sebi_charge: float

    gst: float

    stamp_duty: float

    total: float