import pandas as pd


class FactorNormalizer:

    @staticmethod
    def normalize(
        series: pd.Series,
        higher_is_better: bool,
    ) -> pd.Series:

        minimum = series.min()

        maximum = series.max()

        #
        # All values identical
        #
        if minimum == maximum:

            return pd.Series(
                1.0,
                index=series.index,
            )

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