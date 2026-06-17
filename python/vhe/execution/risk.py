from __future__ import annotations

from dataclasses import dataclass

from vhe.backtest.models import Order, OrderSide


@dataclass(frozen=True, slots=True)
class RiskConfig:
    max_daily_loss_pct: float = 0.01
    max_gross_exposure_pct: float = 0.75
    max_single_symbol_qty: int = 100
    max_symbol_exposure_pct: float = 0.30


@dataclass(frozen=True, slots=True)
class RiskDecision:
    approved: bool
    reason: str


@dataclass(slots=True)
class RiskGuard:
    config: RiskConfig
    kill_switch: bool = False
    kill_switch_reason: str | None = None
    automation_paused: bool = False

    def evaluate(self, order: Order, portfolio: dict) -> RiskDecision:
        if self.kill_switch:
            return RiskDecision(False, "kill_switch_active")
        if self.automation_paused:
            return RiskDecision(False, "automation_paused")
        if _daily_loss_pct(portfolio) <= -self.config.max_daily_loss_pct:
            return RiskDecision(False, "daily_loss_limit")
        if order.quantity > self.config.max_single_symbol_qty:
            return RiskDecision(False, "symbol_quantity_limit")
        if order.side == OrderSide.BUY:
            if _projected_gross_exposure_pct(portfolio, order) >= self.config.max_gross_exposure_pct:
                return RiskDecision(False, "gross_exposure_limit")
            if _projected_symbol_exposure_pct(portfolio, order) >= self.config.max_symbol_exposure_pct:
                return RiskDecision(False, "symbol_exposure_limit")
        return RiskDecision(True, "approved")


def _daily_loss_pct(portfolio: dict) -> float:
    initial_cash = float(portfolio.get("initial_cash") or 0)
    if initial_cash <= 0:
        return 0.0
    equity = float(portfolio.get("equity") or initial_cash)
    return (equity - initial_cash) / initial_cash


def _gross_exposure_pct(portfolio: dict) -> float:
    initial_cash = float(portfolio.get("initial_cash") or 0)
    if initial_cash <= 0:
        return 0.0
    exposure = _gross_exposure(portfolio)
    return exposure / initial_cash


def _gross_exposure(portfolio: dict) -> float:
    return sum(abs(float(position.get("market_value") or 0)) for position in portfolio.get("positions", []))


def _symbol_exposure(portfolio: dict, symbol: str) -> float:
    for position in portfolio.get("positions", []):
        if position.get("symbol") == symbol:
            return abs(float(position.get("market_value") or 0))
    return 0.0


def _projected_gross_exposure_pct(portfolio: dict, order: Order) -> float:
    initial_cash = float(portfolio.get("initial_cash") or 0)
    if initial_cash <= 0:
        return 0.0
    projected = _gross_exposure(portfolio) + order.price * order.quantity
    return projected / initial_cash


def _projected_symbol_exposure_pct(portfolio: dict, order: Order) -> float:
    initial_cash = float(portfolio.get("initial_cash") or 0)
    if initial_cash <= 0:
        return 0.0
    projected = _symbol_exposure(portfolio, order.symbol) + order.price * order.quantity
    return projected / initial_cash
