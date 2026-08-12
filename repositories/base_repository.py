from abc import ABC, abstractmethod
import pandas as pd


class BaseRepository(ABC):

    @abstractmethod
    def last_date(self, symbol: str):
        pass

    @abstractmethod
    def save(self, symbol: str, df: pd.DataFrame):
        pass

    @abstractmethod
    def load(self, symbol: str) -> pd.DataFrame:
        pass

    @abstractmethod
    def exists(self, symbol: str) -> bool:
        pass