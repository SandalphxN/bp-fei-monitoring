from __future__ import annotations
from abc import ABC, abstractmethod
import pandas as pd


class BaseParser(ABC):
    faculty_code: str = "UNKNOWN"

    @abstractmethod
    def detect(self, file_path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, file_path: str, year: int) -> pd.DataFrame:
        raise NotImplementedError