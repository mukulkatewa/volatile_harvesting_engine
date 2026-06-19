from __future__ import annotations

from dataclasses import dataclass, field

from vhe.backtest.models import Fill, Order
from vhe.execution.kite_broker import KiteBroker, KiteBrokerError
from vhe.execution.order_fsm import ManagedOrder, OrderState, OrderStateMachine
from vhe.execution.paper import PaperBroker
from vhe.live.kite_auth import KiteCredentialError, load_kite_credentials
from vhe.live.models import LiveQuote


@dataclass(slots=True)
class ExecutionEngine:
    mode: str
    paper_broker: PaperBroker
    order_fsm: OrderStateMachine = field(default_factory=OrderStateMachine)
    kite_broker: KiteBroker | None = None
    live_orders_enabled: bool = False

    @classmethod
    def from_config(cls, *, mode: str, paper_broker: PaperBroker, broker_config) -> ExecutionEngine:
        kite = None
        live_enabled = False
        if mode == "live":
            try:
                credentials = load_kite_credentials(broker_config)
                kite = KiteBroker(credentials=credentials)
                live_enabled = True
            except (KiteCredentialError, ValueError) as exc:
                raise RuntimeError(f"live mode requires valid Kite credentials: {exc}") from exc
        return cls(mode=mode, paper_broker=paper_broker, kite_broker=kite, live_orders_enabled=live_enabled)

    def submit(self, order: Order, quote: LiveQuote) -> Fill | None:
        managed = ManagedOrder(
            order_id=order.order_id,
            broker_order_id=None,
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.quantity,
            price=order.price,
            strategy_id=order.reason or "strategy",
        )
        self.order_fsm.register(managed)
        managed.transition(OrderState.RISK_APPROVED)

        if self.live_orders_enabled and self.kite_broker is not None:
            try:
                response = self.kite_broker.place_order(order, quote)
                managed.transition(OrderState.SENT, broker_order_id=response.broker_order_id)
                return None
            except KiteBrokerError as exc:
                managed.transition(OrderState.REJECTED, error=str(exc))
                return None

        fill = self.paper_broker.submit(order, quote)
        if fill is None:
            managed.transition(OrderState.REJECTED, error="paper_no_fill")
            return None
        managed.transition(OrderState.FILLED)
        managed.filled_quantity = fill.quantity
        return fill

    def place_resting(self, order: Order) -> bool:
        if self.live_orders_enabled:
            return False
        existing = self.order_fsm.get(order.order_id)
        if existing is not None and existing.state not in {OrderState.REJECTED, OrderState.CANCELLED, OrderState.FILLED}:
            return True
        managed = ManagedOrder(
            order_id=order.order_id,
            broker_order_id=None,
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.quantity,
            price=order.price,
            strategy_id=order.reason or "strategy",
        )
        self.order_fsm.register(managed)
        managed.transition(OrderState.RISK_APPROVED)
        if not self.paper_broker.place_resting(order):
            managed.transition(OrderState.REJECTED, error="resting_duplicate")
            return False
        managed.transition(OrderState.ACKNOWLEDGED)
        return True

    def cancel_resting_except(self, symbol: str, keep_ids: set[str]) -> None:
        if self.live_orders_enabled:
            return
        for order_id, order in list(self.paper_broker.resting_orders.items()):
            if order.symbol != symbol or order_id in keep_ids:
                continue
            self.paper_broker.cancel_resting(order_id)
            managed = self.order_fsm.get(order_id)
            if managed is not None:
                managed.transition(OrderState.CANCELLED)

    def process_resting(self, quotes: dict[str, LiveQuote]) -> list[Fill]:
        if self.live_orders_enabled:
            return []
        fills = self.paper_broker.fill_resting(quotes)
        for fill in fills:
            managed = self.order_fsm.get(fill.order_id)
            if managed is not None:
                managed.transition(OrderState.FILLED)
                managed.filled_quantity = fill.quantity
        return fills

    def submit_atomic(self, orders: list[Order], quotes: dict[str, LiveQuote]) -> list[Fill]:
        if self.live_orders_enabled:
            fills: list[Fill] = []
            for order in orders:
                quote = quotes[order.symbol]
                fill = self.submit(order, quote)
                if fill is not None:
                    fills.append(fill)
            return fills if len(fills) == len(orders) else []
        return self.paper_broker.submit_atomic(orders, quotes)

    def snapshot_portfolio(self, quotes: dict[str, LiveQuote]) -> dict:
        return self.paper_broker.snapshot(quotes)

    def orders_snapshot(self) -> list[dict]:
        return self.order_fsm.snapshot()
