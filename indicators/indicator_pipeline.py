import pandas as pd

from application.app_context import AppContext
from indicators.indicator_registry import (
    INDICATOR_REGISTRY,
)


class IndicatorPipeline:

    def __init__(
        self,
        context: AppContext,
    ):

        self.context = context

        enabled = (
            context.config["indicators"]["enabled"]
        )

        self.indicator_classes = [
            INDICATOR_REGISTRY[name]
            for name in enabled
        ]

    def execute(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        for indicator_class in self.indicator_classes:

            indicator = indicator_class()

            df = indicator.execute(df)

        return df