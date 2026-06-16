from __future__ import annotations

from dataclasses import dataclass, field, replace

from vhe.backtest.models import Fill, Order
from vhe.config.loader import PlatformConfig
from vhe.execution.capital import CapitalAllocator
from vhe.execution.execution_engine import ExecutionEngine
from vhe.execution.pair_ledger import PairLedger
from vhe.execution.paper import PaperBroker
from vhe.execution.risk import RiskConfig, RiskGuard
from vhe.live.models import LiveQuote
from vhe.platform.events import PlatformEvent, event
from vhe.platform.services.indicator_service import IndicatorSnapshot
from vhe.platform.services.regime_service import RegimeService
from vhe.platform.state import PlatformState
from vhe.storage.db import PlatformDatabase
from vhe.strategies.dynamic_grid import DynamicGridConfig, DynamicGridInputs, DynamicGridPlan, DynamicGridStrategy
from vhe.strategies.momentum import MomentumConfig, MomentumInputs, MomentumPlan, MomentumStrategy
from vhe.strategies.pair_spread import PairConfig, PairInputs, PairSpreadPlan, PairSpreadStrategy
from vhe.strategies.regime import MarketRegime


@dataclass(slots=True)
class StrategyOrchestrator:
    config: PlatformConfig
    state: PlatformState
    execution: ExecutionEngine
    pair_ledger: PairLedger
    risk_guard: RiskGuard
    capital_allocator: CapitalAllocator
    regime_service: RegimeService
    database: PlatformDatabase | None = None
    grid_strategy: DynamicGridStrategy = field(init=False)
    momentum_strategy: MomentumStrategy = field(init=False)
    pair_strategy: PairSpreadStrategy = field(init=False)

    def __post_init__(self) -> None:
        strategies = self.config.strategies
        grid_alloc = self.capital_allocator.symbol_grid_allocation("GRID")
        pair_alloc = self.capital_allocator.pair_allocation(
            f"{strategies.pair.symbol_a}/{strategies.pair.symbol_b}"
        )
        self.grid_strategy = DynamicGridStrategy(
            DynamicGridConfig(
                atr_multiplier=strategies.grid.atr_multiplier,
                max_levels=self.config.live.max_grid_levels,
                symbol_capital=grid_alloc.capital,
                no_buy_above_fair_value_pct=strategies.grid.no_buy_above_fair_value_pct,
                min_spacing=strategies.grid.min_spacing,
                fill_tolerance_pct=strategies.grid.fill_tolerance_pct,
                seed_deploy_pct=strategies.grid.seed_deploy_pct,
                level_capital_multiplier=strategies.grid.level_capital_multiplier,
            )
        )
        self.momentum_strategy = MomentumStrategy(
            MomentumConfig(
                risk_per_trade=strategies.momentum.risk_per_trade_inr,
                max_capital_per_trade=strategies.momentum.max_capital_per_trade_inr,
            )
        )
        pair_cfg = strategies.pair
        self.pair_strategy = PairSpreadStrategy(
            PairConfig(
                symbol_a=pair_cfg.symbol_a,
                symbol_b=pair_cfg.symbol_b,
                hedge_ratio=pair_cfg.hedge_ratio,
                mean=pair_cfg.mean,
                std=pair_cfg.std,
                entry_z=pair_cfg.entry_z,
                exit_z=pair_cfg.exit_z,
                max_abs_z=pair_cfg.max_abs_z,
                leg_capital=pair_alloc.leg_capital,
            )
        )

    def is_pair_symbol(self, symbol: str) -> bool:
        return symbol in {self.pair_strategy.config.symbol_a, self.pair_strategy.config.symbol_b}

    @property
    def paper_broker(self) -> PaperBroker:
        return self.execution.paper_broker

    def single_name_quantity(self, symbol: str) -> int:
        if self.is_pair_symbol(symbol):
            return 0
        position = self.paper_broker.positions.get(symbol)
        return position.quantity if position else 0

    def build_plans(self, quote: LiveQuote, snapshot: IndicatorSnapshot, regime: MarketRegime) -> tuple[DynamicGridPlan, MomentumPlan]:
        grid_plan = self.grid_strategy.build_plan(
            DynamicGridInputs(
                quote=quote,
                fair_value=snapshot.fair_value,
                atr_14=snapshot.atr_14,
                regime=regime,
                current_quantity=self.single_name_quantity(quote.symbol),
            )
        )
        momentum_plan = self.momentum_strategy.build_plan(
            MomentumInputs(
                quote=quote,
                regime=regime,
                ema_20=snapshot.ema_20,
                ema_50=snapshot.ema_50,
                atr_14=snapshot.atr_14,
                current_quantity=self.single_name_quantity(quote.symbol),
            )
        )
        return grid_plan, momentum_plan

    def build_pair_plan(self) -> list[Order]:
        quote_a = self.state.quotes.get(self.pair_strategy.config.symbol_a)
        quote_b = self.state.quotes.get(self.pair_strategy.config.symbol_b)
        if quote_a is None or quote_b is None:
            return []

        position_a = self.paper_broker.positions.get(self.pair_strategy.config.symbol_a)
        position_b = self.paper_broker.positions.get(self.pair_strategy.config.symbol_b)
        market_regime = self.regime_service.get(self.pair_strategy.config.symbol_a)
        plan = self.pair_strategy.build_plan(
            PairInputs(
                quote_a=quote_a,
                quote_b=quote_b,
                regime=market_regime,
                quantity_a=position_a.quantity if position_a else 0,
                quantity_b=position_b.quantity if position_b else 0,
            )
        )
        self.state.pair_plans[plan.pair_id] = plan
        return self.pair_strategy.orders_from_plan(plan, quote_a, quote_b)

    def process_quote(self, quote: LiveQuote, snapshot: IndicatorSnapshot, regime: MarketRegime) -> None:
        self._refresh_grid_capital()
        grid_plan, momentum_plan = self.build_plans(quote, snapshot, regime)
        self.state.quotes[quote.symbol] = quote
        self.state.plans[quote.symbol] = grid_plan
        self.state.momentum_plans[quote.symbol] = momentum_plan
        self.state.regimes[quote.symbol] = regime.value
        self.state.indicators[quote.symbol] = {
            "ema_20": round(snapshot.ema_20, 2),
            "ema_50": round(snapshot.ema_50, 2),
            "atr_14": round(snapshot.atr_14, 2),
            "adx_14": round(snapshot.adx_14, 2),
            "fair_value": round(snapshot.fair_value, 2),
        }

        pair_orders = self.build_pair_plan()
        single_name_orders: list[Order] = []
        if not self.is_pair_symbol(quote.symbol):
            current_qty = self.single_name_quantity(quote.symbol)
            single_name_orders = self.grid_strategy.orders_from_plan(grid_plan, quote, current_quantity=current_qty) + self.momentum_strategy.orders_from_plan(
                momentum_plan, quote
            )

        single_name_fills = self._submit_orders(single_name_orders)
        pair_fills = self._submit_pair_orders_atomic(pair_orders)
        self.state.orders.extend(single_name_orders + pair_orders)
        self.state.fills.extend(single_name_fills + pair_fills)
        self.state.portfolio = self._enrich_portfolio(self.execution.snapshot_portfolio(self.state.quotes))
        self.state.capital = self.capital_allocator.buckets_snapshot()
        self.state.execution_orders = self.execution.orders_snapshot()
        self.state.strategy_status = self._strategy_status(grid_plan, momentum_plan, regime)

    def _enrich_portfolio(self, portfolio: dict) -> dict:
        enriched = dict(portfolio)
        enriched["max_gross_exposure_pct"] = self.risk_guard.config.max_gross_exposure_pct
        enriched["max_symbol_exposure_pct"] = self.risk_guard.config.max_symbol_exposure_pct
        return enriched

    def _refresh_grid_capital(self) -> None:
        alloc = self.capital_allocator.symbol_grid_allocation(
            "GRID",
            active_symbol_count=self._active_grid_symbol_count(),
        )
        self.grid_strategy.config = replace(self.grid_strategy.config, symbol_capital=alloc.capital)

    def _active_grid_symbol_count(self) -> int:
        tradeable = [symbol for symbol in self.config.strategies.feed.symbols if not self.is_pair_symbol(symbol)]
        in_range = sum(1 for symbol in tradeable if self.state.regimes.get(symbol) == MarketRegime.RANGE.value)
        active = in_range or len(tradeable)
        return max(min(active, self.config.live.max_symbols), 1)

    def _strategy_status(self, grid_plan: DynamicGridPlan, momentum_plan: MomentumPlan, regime: MarketRegime) -> dict:
        pair_plan = next(iter(self.state.pair_plans.values()), None)
        return {
            "regime": regime.value,
            "grid": "ACTIVE" if grid_plan.buy_levels else "WAITING",
            "momentum": "ARMED" if momentum_plan.enabled else "OFF",
            "pair": pair_plan.action if pair_plan else "WAITING",
            "edge": _edge_note(regime),
        }

    def _submit_pair_orders_atomic(self, orders: list[Order]) -> list[Fill]:
        if not orders:
            return []

        for order in orders:
            if order.symbol not in self.state.quotes:
                self._log_event(event("risk", f"Rejected pair batch: missing_quote_{order.symbol}", "warning"))
                return []
            decision = self.risk_guard.evaluate(order, self.state.portfolio)
            if not decision.approved:
                self.state.controls.last_risk_reject = decision.reason
                self._log_event(event("risk", f"Rejected pair batch: {decision.reason}", "warning"))
                return []

        fills = self.execution.submit_atomic(orders, self.state.quotes)
        if not fills:
            self._log_event(event("risk", "Rejected pair batch: atomic_no_fill", "warning"))
            return []

        self.state.portfolio = self._enrich_portfolio(self.execution.snapshot_portfolio(self.state.quotes))
        for fill in fills:
            self._log_event(event("fill", f"{fill.side.value} {fill.symbol} x{fill.quantity} @ {fill.price:.2f}"))
            self._persist_fill(fill)
        trade = self.pair_ledger.apply_pair_fills(
            f"{self.pair_strategy.config.symbol_a}/{self.pair_strategy.config.symbol_b}",
            fills,
        )
        if trade is not None:
            self.state.pair_trades = self.pair_ledger.snapshot()
            self._log_event(event("pair", f"{trade.status} {trade.pair_id} {trade.trade_id}"))
        return fills

    def _submit_orders(self, orders: list[Order]) -> list[Fill]:
        fills: list[Fill] = []
        for order in orders:
            quote = self.state.quotes.get(order.symbol)
            if quote is None:
                self._log_event(event("risk", f"Rejected {order.symbol}: missing_quote", "warning"))
                continue

            decision = self.risk_guard.evaluate(order, self.state.portfolio)
            if not decision.approved:
                self.state.controls.last_risk_reject = decision.reason
                self._log_event(event("risk", f"Rejected {order.symbol}: {decision.reason}", "warning"))
                continue

            fill = self.execution.submit(order, quote)
            if fill is not None:
                fills.append(fill)
                self.state.portfolio = self._enrich_portfolio(self.execution.snapshot_portfolio(self.state.quotes))
                self._log_event(event("fill", f"{fill.side.value} {fill.symbol} x{fill.quantity} @ {fill.price:.2f}"))
                self._persist_fill(fill)
        return fills

    def _log_event(self, entry: PlatformEvent) -> None:
        self.state.append_event(entry)
        if self.database and self.config.live.storage.persist_events:
            self.database.append_event(
                category=entry.category,
                message=entry.message,
                severity=entry.severity,
            )

    def _persist_fill(self, fill: Fill) -> None:
        if not self.database or not self.config.live.storage.persist_fills:
            return
        try:
            self.database.persist_fill_dataclass(fill)
        except Exception as exc:
            self._log_event(event("risk", f"Fill persist failed: {exc}", "warning"))


def build_risk_guard(config: PlatformConfig) -> RiskGuard:
    risk = config.live.risk
    return RiskGuard(
        RiskConfig(
            max_daily_loss_pct=risk.max_daily_loss_pct,
            max_gross_exposure_pct=risk.max_gross_exposure_pct,
            max_single_symbol_qty=risk.max_single_symbol_qty,
            max_symbol_exposure_pct=risk.max_symbol_exposure_pct,
        )
    )


def _edge_note(regime: MarketRegime) -> str:
    if regime == MarketRegime.RANGE:
        return "Harvest oscillation via ATR grid buys below fair value, sell at mean."
    if regime == MarketRegime.TREND_UP:
        return "Grid off. Momentum captures continuation; pair spread if z-score extreme."
    if regime == MarketRegime.CRASH:
        return "Cash mode. No new risk until regime normalizes."
    return "Waiting for clean range or trend regime before deploying edge."
