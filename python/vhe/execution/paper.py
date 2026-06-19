from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum

from vhe.backtest.costs import EquityIntradayCostModel
from vhe.backtest.models import Fill, Order, OrderSide, OrderType
from vhe.live.models import LiveQuote


@dataclass(slots=True)
class PaperPosition:
    symbol: str
    quantity: int = 0
    avg_price: float = 0.0
    realized_pnl: float = 0.0
    fees_paid: float = 0.0

    def mark_to_market(self, last_price: float) -> float:
        return self.quantity * last_price

    def unrealized_pnl(self, last_price: float) -> float:
        return (last_price - self.avg_price) * self.quantity if self.quantity else 0.0


@dataclass(slots=True)
class PaperBroker:
    initial_cash: float = 25_000.0
    cost_model: EquityIntradayCostModel = field(default_factory=EquityIntradayCostModel)
    aggressive_fills: bool = False
    limit_tolerance_bps: float = 25.0
    fill_full_quantity: bool = False
    use_bar_low_for_fills: bool = True
    resting_proximity_bps: float = 0.0
    cash: float = field(init=False)
    positions: dict[str, PaperPosition] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)
    seen_order_ids: set[str] = field(default_factory=set)
    resting_orders: dict[str, Order] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.cash = self.initial_cash

    def submit(self, order: Order, quote: LiveQuote) -> Fill | None:
        fill = self._preview_fill(order, quote, available_cash=self.cash)
        if fill is None:
            return None
        self.seen_order_ids.add(order.order_id)
        self._apply_fill(fill)
        return fill

    def place_resting(self, order: Order) -> bool:
        if order.order_id in self.seen_order_ids:
            return False
        self.resting_orders[order.order_id] = order
        return True

    def cancel_resting(self, order_id: str) -> None:
        self.resting_orders.pop(order_id, None)

    def cancel_resting_except(self, symbol: str, keep_ids: set[str]) -> None:
        for order_id, order in list(self.resting_orders.items()):
            if order.symbol == symbol and order_id not in keep_ids:
                self.cancel_resting(order_id)

    def fill_resting(self, quotes: dict[str, LiveQuote]) -> list[Fill]:
        fills: list[Fill] = []
        filled_symbols: set[str] = set()
        for order_id, order in sorted(
            self.resting_orders.items(),
            key=lambda item: (_level_sort_key(item[1]), item[1].symbol),
        ):
            if order.symbol in filled_symbols:
                continue
            quote = quotes.get(order.symbol)
            if quote is None:
                continue
            fill = self._preview_fill(order, quote, available_cash=self.cash, resting=True)
            if fill is None:
                continue
            self.cancel_resting(order_id)
            self.seen_order_ids.add(order_id)
            self._apply_fill(fill)
            fills.append(fill)
            filled_symbols.add(order.symbol)
        return fills

    def submit_atomic(self, orders: list[Order], quotes: dict[str, LiveQuote]) -> list[Fill]:
        if not orders:
            return []
        order_ids = [order.order_id for order in orders]
        if len(order_ids) != len(set(order_ids)):
            return []

        available_cash = self.cash
        fills: list[Fill] = []
        for order in orders:
            quote = quotes.get(order.symbol)
            if quote is None:
                return []
            fill = self._preview_fill(order, quote, available_cash=available_cash)
            if fill is None:
                return []
            fills.append(fill)
            if order.side == OrderSide.BUY:
                available_cash -= fill.price * fill.quantity + fill.fees
            else:
                available_cash += fill.price * fill.quantity - fill.fees

        for fill in fills:
            self.seen_order_ids.add(fill.order_id)
            self._apply_fill(fill)
        return fills

    def snapshot(self, quotes: dict[str, LiveQuote]) -> dict:
        equity = self.cash
        positions = []
        realized_pnl = 0.0
        unrealized_pnl = 0.0
        fees_paid = 0.0

        for symbol, position in sorted(self.positions.items()):
            quote = quotes.get(symbol)
            last_price = quote.ltp if quote else position.avg_price
            market_value = position.mark_to_market(last_price)
            unrealized = position.unrealized_pnl(last_price)
            realized_pnl += position.realized_pnl
            unrealized_pnl += unrealized
            fees_paid += position.fees_paid
            if position.quantity == 0:
                continue
            equity += market_value
            positions.append(
                {
                    **asdict(position),
                    "last_price": last_price,
                    "market_value": market_value,
                    "unrealized_pnl": unrealized,
                }
            )

        return {
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "equity": equity,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "fees_paid": fees_paid,
            "gross_exposure": round(sum(position["market_value"] for position in positions), 2),
            "gross_exposure_pct": round((sum(position["market_value"] for position in positions) / self.initial_cash) * 100, 1)
            if self.initial_cash > 0
            else 0.0,
            "positions": positions,
            "fills": [_json_ready(asdict(fill)) for fill in self.fills[-25:]],
            "resting_orders": [
                {
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "price": order.price,
                    "quantity": order.quantity,
                    "reason": order.reason,
                }
                for order in sorted(self.resting_orders.values(), key=lambda row: (row.symbol, row.price))
            ],
        }

    def _preview_fill(self, order: Order, quote: LiveQuote, *, available_cash: float, resting: bool = False) -> Fill | None:
        if order.order_id in self.seen_order_ids:
            return None
        if not self._limit_order_fills(order, quote, resting=resting):
            return None

        quantity = order.quantity if self.fill_full_quantity else min(order.quantity, max(int(quote.volume * 0.01), 1))
        if quantity <= 0:
            return None

        fill_price = _fill_price(order, quote)
        fees = self.cost_model.estimate(side=order.side, price=fill_price, quantity=quantity)
        notional = fill_price * quantity
        if order.side == OrderSide.BUY and available_cash < notional + fees:
            return None

        return Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=quantity,
            timestamp=quote.timestamp,
            fees=fees,
            reason=order.reason,
        )

    def _limit_order_fills(self, order: Order, quote: LiveQuote, *, resting: bool = False) -> bool:
        if order.side == OrderSide.BUY:
            touch = quote.ltp
            if resting and self.use_bar_low_for_fills and quote.low > 0:
                touch = min(quote.ltp, quote.low)
            if touch <= order.price:
                return True
            if resting and self.resting_proximity_bps > 0:
                proximity = order.price * (1 + self.resting_proximity_bps / 10_000)
                if touch <= proximity:
                    return True
            if not self.aggressive_fills:
                return False
            tolerance = order.price * (1 + self.limit_tolerance_bps / 10_000)
            return touch <= tolerance
        touch = quote.ltp
        if resting and self.use_bar_low_for_fills and quote.high > 0:
            touch = max(quote.ltp, quote.high)
        if touch >= order.price:
            return True
        if not self.aggressive_fills:
            return False
        tolerance = order.price * (1 - self.limit_tolerance_bps / 10_000)
        return touch >= tolerance

    def _apply_fill(self, fill: Fill) -> None:
        position = self.positions.setdefault(fill.symbol, PaperPosition(symbol=fill.symbol))
        position.fees_paid += fill.fees

        if fill.side == OrderSide.BUY:
            self._apply_buy(position, fill)
        else:
            self._apply_sell(position, fill)

        self.fills.append(fill)

    def _apply_buy(self, position: PaperPosition, fill: Fill) -> None:
        remaining_quantity = fill.quantity

        if position.quantity < 0:
            cover_quantity = min(remaining_quantity, abs(position.quantity))
            position.realized_pnl += (position.avg_price - fill.price) * cover_quantity
            position.quantity += cover_quantity
            remaining_quantity -= cover_quantity
            if position.quantity == 0:
                position.avg_price = 0.0

        if remaining_quantity > 0:
            total_cost = fill.price * remaining_quantity
            new_quantity = position.quantity + remaining_quantity
            position.avg_price = ((position.avg_price * position.quantity) + total_cost) / new_quantity
            position.quantity = new_quantity

        self.cash -= fill.price * fill.quantity + fill.fees
        position.realized_pnl -= fill.fees

    def _apply_sell(self, position: PaperPosition, fill: Fill) -> None:
        remaining_quantity = fill.quantity

        if position.quantity > 0:
            sell_quantity = min(remaining_quantity, position.quantity)
            position.realized_pnl += (fill.price - position.avg_price) * sell_quantity
            position.quantity -= sell_quantity
            remaining_quantity -= sell_quantity
            if position.quantity == 0:
                position.avg_price = 0.0

        if remaining_quantity > 0:
            short_notional = fill.price * remaining_quantity
            new_abs_quantity = abs(position.quantity) + remaining_quantity
            position.avg_price = ((position.avg_price * abs(position.quantity)) + short_notional) / new_abs_quantity
            position.quantity -= remaining_quantity

        self.cash += fill.price * fill.quantity - fill.fees
        position.realized_pnl -= fill.fees


def _level_sort_key(order: Order) -> int:
    reason = order.reason or ""
    if reason.startswith("dynamic_grid_level_"):
        try:
            return int(reason.removeprefix("dynamic_grid_level_"))
        except ValueError:
            return 99
    return 99


def _fill_price(order: Order, quote: LiveQuote) -> float:
    if order.order_type == OrderType.MARKET:
        return quote.ltp
    if order.side == OrderSide.BUY:
        return min(order.price, quote.ltp)
    return max(order.price, quote.ltp)


def _json_ready(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
