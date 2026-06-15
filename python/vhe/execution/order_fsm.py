from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class OrderState(str, Enum):
    NEW = "NEW"
    RISK_APPROVED = "RISK_APPROVED"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass(slots=True)
class ManagedOrder:
    order_id: str
    broker_order_id: str | None
    symbol: str
    side: str
    quantity: int
    price: float
    strategy_id: str
    state: OrderState = OrderState.NEW
    filled_quantity: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    last_error: str | None = None

    def transition(self, new_state: OrderState, *, broker_order_id: str | None = None, error: str | None = None) -> None:
        self.state = new_state
        self.updated_at = datetime.now(tz=timezone.utc)
        if broker_order_id is not None:
            self.broker_order_id = broker_order_id
        if error is not None:
            self.last_error = error


@dataclass(slots=True)
class OrderStateMachine:
    orders: dict[str, ManagedOrder] = field(default_factory=dict)

    def register(self, order: ManagedOrder) -> None:
        self.orders[order.order_id] = order

    def get(self, order_id: str) -> ManagedOrder | None:
        return self.orders.get(order_id)

    def snapshot(self, limit: int = 25) -> list[dict]:
        rows = sorted(self.orders.values(), key=lambda row: row.updated_at, reverse=True)[:limit]
        return [
            {
                "order_id": row.order_id,
                "broker_order_id": row.broker_order_id,
                "symbol": row.symbol,
                "side": row.side,
                "quantity": row.quantity,
                "price": row.price,
                "strategy_id": row.strategy_id,
                "state": row.state.value,
                "filled_quantity": row.filled_quantity,
                "last_error": row.last_error,
                "updated_at": row.updated_at.isoformat(),
            }
            for row in rows
        ]
