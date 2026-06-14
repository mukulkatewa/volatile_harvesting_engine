from __future__ import annotations

from dataclasses import asdict, dataclass, field

from vhe.backtest.costs import EquityIntradayCostModel
from vhe.backtest.models import Fill, Order, OrderSide
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
    cash: float = field(init=False)
    positions: dict[str, PaperPosition] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)
    seen_order_ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.cash = self.initial_cash

    def submit(self, order: Order, quote: LiveQuote) -> Fill | None:
        fill = self._preview_fill(order, quote, available_cash=self.cash)
        if fill is None:
            return None
        self.seen_order_ids.add(order.order_id)
        self._apply_fill(fill)
        return fill

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
            equity += market_value
            realized_pnl += position.realized_pnl
            unrealized_pnl += unrealized
            fees_paid += position.fees_paid
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
            "positions": positions,
            "fills": [asdict(fill) for fill in self.fills[-25:]],
        }

    def _preview_fill(self, order: Order, quote: LiveQuote, *, available_cash: float) -> Fill | None:
        if order.order_id in self.seen_order_ids:
            return None
        if order.side == OrderSide.BUY and quote.ltp > order.price:
            return None
        if order.side == OrderSide.SELL and quote.ltp < order.price:
            return None

        quantity = min(order.quantity, max(int(quote.volume * 0.01), 1))
        if quantity <= 0:
            return None

        fees = self.cost_model.estimate(side=order.side, price=quote.ltp, quantity=quantity)
        notional = quote.ltp * quantity
        if order.side == OrderSide.BUY and available_cash < notional + fees:
            return None

        return Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            price=quote.ltp,
            quantity=quantity,
            timestamp=quote.timestamp,
            fees=fees,
            reason=order.reason,
        )

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
