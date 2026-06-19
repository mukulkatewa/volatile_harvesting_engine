from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import time

from vhe.backtest.models import Fill, Order, OrderSide, OrderType
from vhe.config.loader import PlatformConfig
from vhe.execution.capital import CapitalAllocator
from vhe.execution.execution_engine import ExecutionEngine
from vhe.execution.pair_ledger import PairLedger
from vhe.execution.paper import PaperBroker
from vhe.execution.risk import RiskConfig, RiskGuard
from vhe.live.market_session import SessionPhase
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
    session_tracker: object | None = None
    sentiment_service: object | None = None
    grid_strategy: DynamicGridStrategy = field(init=False)
    momentum_strategy: MomentumStrategy = field(init=False)
    pair_strategy: PairSpreadStrategy = field(init=False)
    _symbol_grid_fills: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        strategies = self.config.strategies
        grid_alloc = self.capital_allocator.symbol_grid_allocation("GRID")
        pair_alloc = self.capital_allocator.pair_allocation(
            f"{strategies.pair.symbol_a}/{strategies.pair.symbol_b}"
        )
        force_exit = time.fromisoformat(self.config.live.force_exit_time)
        self.grid_strategy = DynamicGridStrategy(
            DynamicGridConfig(
                atr_multiplier=strategies.grid.atr_multiplier,
                max_levels=self.config.live.max_grid_levels,
                symbol_capital=grid_alloc.capital,
                no_buy_above_fair_value_pct=strategies.grid.no_buy_above_fair_value_pct,
                min_spacing=strategies.grid.min_spacing,
                min_spacing_pct=strategies.grid.min_spacing_pct,
                fill_tolerance_pct=strategies.grid.fill_tolerance_pct,
                seed_deploy_pct=strategies.grid.seed_deploy_pct,
                level_capital_multiplier=strategies.grid.level_capital_multiplier,
                force_exit_time=force_exit,
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

    def reset_trading_state(self) -> None:
        self._symbol_grid_fills.clear()
        self.grid_strategy.reset_session()

    def _max_grid_fills_per_symbol(self) -> int:
        return self.config.live.risk.max_grid_fills_per_symbol

    def _filter_grid_churn(self, orders: list[Order]) -> list[Order]:
        cap = self._max_grid_fills_per_symbol()
        allowed: list[Order] = []
        for order in orders:
            if order.side != OrderSide.BUY or not (order.reason or "").startswith("dynamic_grid"):
                allowed.append(order)
                continue
            count = self._symbol_grid_fills.get(order.symbol, 0)
            if count >= cap:
                self.state.controls.last_risk_reject = "grid_fill_cap"
                self._log_event(event("risk", f"Rejected {order.symbol}: grid_fill_cap", "warning"))
                continue
            allowed.append(order)
        return allowed

    def _after_fill(self, fill: Fill) -> None:
        if fill.reason and fill.reason.startswith("dynamic_grid") and fill.side == OrderSide.BUY:
            self._symbol_grid_fills[fill.symbol] = self._symbol_grid_fills.get(fill.symbol, 0) + 1
        if fill.reason and fill.reason.startswith("dynamic_grid"):
            self.grid_strategy.on_fill_reason(fill.symbol, fill.reason)

    def _apply_sentiment_sizing(self, orders: list[Order]) -> list[Order]:
        if self.sentiment_service is None:
            return orders
        adjusted: list[Order] = []
        for order in orders:
            if order.side != OrderSide.BUY:
                adjusted.append(order)
                continue
            multiplier = self.sentiment_service.size_multiplier(order.symbol)
            if multiplier >= 0.999:
                adjusted.append(order)
                continue
            if multiplier <= 0:
                self.state.controls.last_risk_reject = "sentiment_reduce_zero"
                continue
            qty = max(int(order.quantity * multiplier), 1)
            if qty == order.quantity:
                adjusted.append(order)
            else:
                adjusted.append(replace(order, quantity=qty))
        return adjusted

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
        spacing_mult = 1.0
        sentiment_score = 0.0
        sentiment_allows = True
        if self.sentiment_service is not None:
            spacing_mult = self.sentiment_service.spacing_multiplier(quote.symbol)
            row = self.sentiment_service.symbol(quote.symbol)
            if row is not None:
                sentiment_score = row.score
            sentiment_allows = self.sentiment_service.momentum_allowed(quote.symbol)

        grid_plan = self.grid_strategy.build_plan(
            DynamicGridInputs(
                quote=quote,
                fair_value=snapshot.fair_value,
                atr_14=snapshot.atr_14,
                regime=regime,
                current_quantity=self.single_name_quantity(quote.symbol),
                sentiment_spacing_multiplier=spacing_mult,
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
                sentiment_score=sentiment_score,
                sentiment_allows_entry=sentiment_allows,
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

    def process_quote(
        self,
        quote: LiveQuote,
        snapshot: IndicatorSnapshot,
        regime: MarketRegime,
        *,
        session_phase: SessionPhase | None = None,
    ) -> None:
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

        trading_open = session_phase is None or allows_new_risk_for_phase(session_phase)
        force_exit_only = session_phase == SessionPhase.FORCE_EXIT

        pair_orders: list[Order] = []
        if trading_open:
            pair_orders = self.build_pair_plan()
        elif force_exit_only:
            pair_orders = self._force_exit_pair_orders()

        single_name_orders: list[Order] = []
        if not self.is_pair_symbol(quote.symbol):
            current_qty = self.single_name_quantity(quote.symbol)
            if force_exit_only or trading_open:
                single_name_orders = self.grid_strategy.orders_from_plan(grid_plan, quote, current_quantity=current_qty)
            if trading_open:
                single_name_orders.extend(self.momentum_strategy.orders_from_plan(momentum_plan, quote))

        single_name_orders = _filter_orders_for_session(single_name_orders, session_phase)
        pair_orders = _filter_orders_for_session(pair_orders, session_phase)
        single_name_orders = self._filter_grid_churn(single_name_orders)
        single_name_orders = self._apply_sentiment_sizing(single_name_orders)

        single_name_fills = self._submit_orders(single_name_orders)
        pair_fills = self._submit_pair_orders_atomic(pair_orders)
        self.state.orders.extend(single_name_orders + pair_orders)
        self.state.fills.extend(single_name_fills + pair_fills)
        self.state.portfolio = self._enrich_portfolio(self.execution.snapshot_portfolio(self.state.quotes))
        self.state.capital = self.capital_allocator.buckets_snapshot()
        self.state.execution_orders = self.execution.orders_snapshot()
        self.state.strategy_status = self._strategy_status(grid_plan, momentum_plan, regime, session_phase)

    def _force_exit_pair_orders(self) -> list[Order]:
        orders: list[Order] = []
        for symbol in (self.pair_strategy.config.symbol_a, self.pair_strategy.config.symbol_b):
            position = self.paper_broker.positions.get(symbol)
            quote = self.state.quotes.get(symbol)
            if position is None or position.quantity <= 0 or quote is None:
                continue
            orders.append(
                Order(
                    order_id=f"fe-{symbol}-{len(self.state.orders) + len(orders) + 1}",
                    symbol=symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.LIMIT,
                    price=quote.ltp,
                    quantity=position.quantity,
                    created_at=quote.timestamp,
                    reason="session_force_exit",
                )
            )
        return orders

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

    def _strategy_status(
        self,
        grid_plan: DynamicGridPlan,
        momentum_plan: MomentumPlan,
        regime: MarketRegime,
        session_phase: SessionPhase | None = None,
    ) -> dict:
        pair_plan = next(iter(self.state.pair_plans.values()), None)
        sentiment_note = ""
        if self.sentiment_service is not None:
            row = self.sentiment_service.symbol(grid_plan.symbol)
            if row is not None and row.status.value != "clear":
                sentiment_note = f" · sentiment {row.status.value}"
        status = {
            "regime": regime.value,
            "regime_summary": self._regime_summary(),
            "grid": "ACTIVE" if grid_plan.buy_levels else "WAITING",
            "momentum": "ARMED" if momentum_plan.enabled else "OFF",
            "pair": pair_plan.action if pair_plan else "WAITING",
            "edge": _edge_note(regime, session_phase) + sentiment_note,
        }
        if session_phase == SessionPhase.CLOSED:
            status["grid"] = "CLOSED"
            status["momentum"] = "CLOSED"
            status["pair"] = "CLOSED"
        elif session_phase == SessionPhase.FORCE_EXIT:
            status["grid"] = "EXITING"
            status["momentum"] = "OFF"
        elif session_phase == SessionPhase.PRE_MARKET:
            status["grid"] = "PREOPEN"
        return status

    def _regime_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for value in self.state.regimes.values():
            counts[value] = counts.get(value, 0) + 1
        return counts

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
            self._after_fill(fill)
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
                self.state.controls.last_risk_reject = None
                self.state.portfolio = self._enrich_portfolio(self.execution.snapshot_portfolio(self.state.quotes))
                self._log_event(event("fill", f"{fill.side.value} {fill.symbol} x{fill.quantity} @ {fill.price:.2f}"))
                self._persist_fill(fill)
                self._after_fill(fill)
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
        if self.session_tracker is not None:
            self.session_tracker.record_fill(fill)
        if not self.database or not self.config.live.storage.persist_fills:
            return
        try:
            fill_id = self.database.persist_fill_dataclass(fill)
            session_id = getattr(self.session_tracker, "session_id", None)
            if session_id:
                self.database.link_fill_to_session(session_id, fill_id)
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


def _edge_note(regime: MarketRegime, session_phase: SessionPhase | None = None) -> str:
    if session_phase == SessionPhase.CLOSED:
        return "NSE session closed. Feed stays on; new orders resume at 09:15 IST."
    if session_phase == SessionPhase.FORCE_EXIT:
        return "Square-off window — flattening intraday positions before 15:30."
    if session_phase == SessionPhase.PRE_MARKET:
        return "Pre-market — waiting for 09:15 IST open."
    if regime == MarketRegime.RANGE:
        return "Harvest oscillation via ATR grid buys below fair value, sell at mean."
    if regime == MarketRegime.TREND_UP:
        return "Grid off. Momentum captures continuation; pair spread if z-score extreme."
    if regime == MarketRegime.CRASH:
        return "Cash mode. No new risk until regime normalizes."
    return "Waiting for clean range or trend regime before deploying edge."


def allows_new_risk_for_phase(phase: SessionPhase) -> bool:
    return phase == SessionPhase.OPEN


def _filter_orders_for_session(orders: list[Order], phase: SessionPhase | None) -> list[Order]:
    if phase is None or phase == SessionPhase.OPEN:
        return orders
    if phase == SessionPhase.FORCE_EXIT:
        return [order for order in orders if order.side == OrderSide.SELL]
    return []
