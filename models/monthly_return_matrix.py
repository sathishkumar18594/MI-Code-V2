from dataclasses import dataclass


@dataclass(slots=True)
class MonthlyReturnMatrix:

    year: int

    january: float | None = None

    february: float | None = None

    march: float | None = None

    april: float | None = None

    may: float | None = None

    june: float | None = None

    july: float | None = None

    august: float | None = None

    september: float | None = None

    october: float | None = None

    november: float | None = None

    december: float | None = None

    annual_return: float = 0.0