from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


@dataclass(frozen=True, slots=True)
class MarketBar:
    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float
    quantity: int
    created_at: datetime
    reason: str


@dataclass(frozen=True, slots=True)
class Fill:
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    quantity: int
    timestamp: datetime
    fees: float
    reason: str


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    timestamp: datetime
    symbol: str
    quantity: int
    avg_price: float
    realized_pnl: float
    fees_paid: float
    equity: float


@dataclass(frozen=True, slots=True)
class BacktestSummary:
    start_date: date
    end_date: date
    initial_cash: float
    final_equity: float
    realized_pnl: float
    fees_paid: float
    total_trades: int
    win_rate: float
    max_drawdown: float

