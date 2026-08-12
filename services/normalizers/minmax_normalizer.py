import pandas as pd

from services.normalizers.base_normalizer import (
    BaseNormalizer,
)


class MinMaxNormalizer(BaseNormalizer):

    def normalize(
        self,
        series: pd.Series,
        higher_is_better: bool,
    ) -> pd.Series:

        minimum = series.min()

        maximum = series.max()

        if minimum == maximum:

            normalized = pd.Series(
                1.0,
                index=series.index,
            )

        else:

            normalized = (
                series - minimum
            ) / (
                maximum - minimum
            )

        if not higher_is_better:

            normalized = (
                1 - normalized
            )

        return normalized