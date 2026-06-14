from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from vhe.backtest.models import Fill


ENTRY_REASONS = {"pair_short_a", "pair_long_b", "pair_long_a", "pair_short_b"}
EXIT_REASONS = {"pair_exit_a", "pair_exit_b"}


@dataclass(slots=True)
class PairTrade:
    trade_id: str
    pair_id: str
    status: str
    opened_at: datetime
    closed_at: datetime | None = None
    entry_fills: list[Fill] = field(default_factory=list)
    exit_fills: list[Fill] = field(default_factory=list)
    realized_pnl: float = 0.0
    fees_paid: float = 0.0

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["opened_at"] = self.opened_at.isoformat()
        payload["closed_at"] = self.closed_at.isoformat() if self.closed_at else None
        return payload


@dataclass(slots=True)
class PairLedger:
    trades: list[PairTrade] = field(default_factory=list)
    _sequence: int = 0

    def apply_pair_fills(self, pair_id: str, fills: list[Fill]) -> PairTrade | None:
        if not fills:
            return None
        reasons = {fill.reason for fill in fills}
        if reasons <= ENTRY_REASONS:
            return self._open_trade(pair_id, fills)
        if reasons <= EXIT_REASONS:
            return self._close_trade(pair_id, fills)
        return None

    def snapshot(self) -> list[dict]:
        return [trade.to_dict() for trade in self.trades[-20:]]

    def open_trade(self, pair_id: str) -> PairTrade | None:
        for trade in reversed(self.trades):
            if trade.pair_id == pair_id and trade.status == "OPEN":
                return trade
        return None

    def _open_trade(self, pair_id: str, fills: list[Fill]) -> PairTrade:
        existing = self.open_trade(pair_id)
        if existing is not None:
            return existing
        self._sequence += 1
        trade = PairTrade(
            trade_id=f"pair-trade-{self._sequence}",
            pair_id=pair_id,
            status="OPEN",
            opened_at=min(fill.timestamp for fill in fills),
            entry_fills=list(fills),
            fees_paid=sum(fill.fees for fill in fills),
        )
        self.trades.append(trade)
        return trade

    def _close_trade(self, pair_id: str, fills: list[Fill]) -> PairTrade | None:
        trade = self.open_trade(pair_id)
        if trade is None:
            return None
        trade.status = "CLOSED"
        trade.closed_at = max(fill.timestamp for fill in fills)
        trade.exit_fills = list(fills)
        trade.fees_paid += sum(fill.fees for fill in fills)
        trade.realized_pnl = _realized_pnl(trade.entry_fills, trade.exit_fills) - trade.fees_paid
        return trade


def _realized_pnl(entry_fills: list[Fill], exit_fills: list[Fill]) -> float:
    by_symbol: dict[str, int] = {}
    cashflow = 0.0
    for fill in entry_fills + exit_fills:
        signed_quantity = fill.quantity if fill.side.value == "BUY" else -fill.quantity
        by_symbol[fill.symbol] = by_symbol.get(fill.symbol, 0) + signed_quantity
        cashflow += -fill.price * signed_quantity
    if any(quantity != 0 for quantity in by_symbol.values()):
        return 0.0
    return cashflow
