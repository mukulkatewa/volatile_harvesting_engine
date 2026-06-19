from __future__ import annotations

from abc import ABC, abstractmethod

from vhe.sentiment.models import BuzzItem


class BuzzCollector(ABC):
    name: str

    @abstractmethod
    def collect(self, symbol: str) -> list[BuzzItem]:
        raise NotImplementedError
