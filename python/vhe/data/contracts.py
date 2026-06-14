from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SymbolRecord:
    symbol: str
    exchange: str
    series: str


@dataclass(frozen=True, slots=True)
class DailyBar:
    trading_date: date
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    turnover: Decimal


@dataclass(frozen=True, slots=True)
class IngestResult:
    output_path: str
    rows: int

