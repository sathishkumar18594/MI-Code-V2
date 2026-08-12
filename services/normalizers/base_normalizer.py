from abc import ABC, abstractmethod

import pandas as pd


class BaseNormalizer(ABC):

    @abstractmethod
    def normalize(
        self,
        series: pd.Series,
        higher_is_better: bool,
    ) -> pd.Series:
        pass