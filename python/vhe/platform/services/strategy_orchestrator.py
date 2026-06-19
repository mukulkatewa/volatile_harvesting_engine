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
                min_harvest_pct=strategies.grid.min_harvest_pct,
                min_order_notional=strategies.grid.min_order_notional,
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

    def _resting_grid_enabled(self) -> bool:
        return self.config.live.mode == "paper" and self.config.live.paper.resting_grid_enabled

    def _sync_grid_resting_orders(self, plan: DynamicGridPlan, quote: LiveQuote, *, current_quantity: int) -> None:
        if not self._resting_grid_enabled():
            return

        desired = self.grid_strategy.resting_buy_orders_from_plan(plan, quote, current_quantity=current_quantity)
        desired = self._apply_sentiment_sizing(desired)
        keep_ids: set[str] = set()

        for order in desired:
            if order.side == OrderSide.BUY:
                count = self._symbol_grid_fills.get(order.symbol, 0)
                if count >= self._max_grid_fills_per_symbol():
                    continue

            decision = self.risk_guard.evaluate(order, self.state.portfolio)
            if not decision.approved:
                continue

            if self.execution.place_resting(order):
                keep_ids.add(order.order_id)

        self.execution.cancel_resting_except(quote.symbol, keep_ids)

    def sync_all_active_resting_orders(self) -> None:
        if not self._resting_grid_enabled():
            return
        for symbol in self.state.active_trading_symbols:
            if self.is_pair_symbol(symbol) or not self._grid_symbol_active(symbol):
                continue
            if self.sentiment_service is not None and not self.sentiment_service.allows_buy(symbol):
                # Do not place fresh buy ladders on names under a sentiment halt.
                self.execution.cancel_resting_except(symbol, set())
                continue
            plan = self.state.plans.get(symbol)
            quote = self.state.quotes.get(symbol)
            if plan is None or quote is None:
                continue
            if plan.regime != MarketRegime.RANGE or not plan.buy_levels:
                self.execution.cancel_resting_except(symbol, set())
                continue
            self._sync_grid_resting_orders(plan, quote, current_quantity=self.single_name_quantity(symbol))

    def _process_resting_fills(self) -> list[Fill]:
        if not self._resting_grid_enabled() or not self.state.quotes:
            return []

        fills = self.execution.process_resting(self.state.quotes)
        for fill in fills:
            self.state.controls.last_risk_reject = None
            self.state.portfolio = self._enrich_portfolio(self.execution.snapshot_portfolio(self.state.quotes))
            self._log_event(event("fill", f"{fill.side.value} {fill.symbol} x{fill.quantity} @ {fill.price:.2f} (resting)"))
            self._persist_fill(fill)
            self._after_fill(fill)
        return fills

    def _after_fill(self, fill: Fill) -> None:
        if fill.reason and fill.reason.startswith("dynamic_grid") and fill.side == OrderSide.BUY:
            self._symbol_grid_fills[fill.symbol] = self._symbol_grid_fills.get(fill.symbol, 0) + 1
        if fill.reason and fill.reason.startswith("dynamic_grid"):
            self.grid_strategy.on_fill_reason(fill.symbol, fill.reason)
        if fill.side == OrderSide.SELL and self.single_name_quantity(fill.symbol) <= 0:
            self._symbol_grid_fills.pop(fill.symbol, None)

    def _apply_sentiment_sizing(self, orders: list[Order]) -> list[Order]:
        if self.sentiment_service is None:
            return orders
        adjusted: list[Order] = []
        for order in orders:
            if order.side != OrderSide.BUY:
                adjusted.append(order)
                continue
            multiplier = self.sentiment_service.size_multiplier_for(order.symbol)
            if multiplier <= 0:
                self.state.controls.last_risk_reject = "sentiment_reduce_zero"
                continue
            if abs(multiplier - 1.0) < 0.001:
                adjusted.append(order)
                continue
            # Reduce on cautionary buzz, scale up on strong positive buzz (risk caps still apply).
            qty = max(int(round(order.quantity * multiplier)), 1)
            if qty == order.quantity:
                adjusted.append(order)
            else:
                adjusted.append(replace(order, quantity=qty))
        return adjusted

    def _sentiment_exit_order(self, quote: LiveQuote, current_quantity: int) -> Order | None:
        # Sentiment-driven SELL: when a held single-name turns to HALT (strongly
        # negative buzz), exit the position as a risk-off stop regardless of P&L.
        if self.sentiment_service is None or self.is_pair_symbol(quote.symbol):
            return None
        if current_quantity <= 0:
            return None
        if self.sentiment_service.allows_buy(quote.symbol):
            return None
        return Order(
            order_id=f"sx-{quote.symbol}-{len(self.state.orders) + 1}",
            symbol=quote.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=quote.ltp,
            quantity=current_quantity,
            created_at=quote.timestamp,
            reason="sentiment_halt_exit",
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

    def _update_trading_universe(self) -> list[str]:
        if self.sentiment_service is None:
            universe = [
                symbol
                for symbol in self.config.strategies.feed.symbols
                if not self.is_pair_symbol(symbol)
            ][: self.config.live.max_symbols]
        else:
            universe = self.sentiment_service.trading_universe(
                self.config.live.max_symbols,
                regime_by_symbol=self.state.regimes,
            )
        held = [
            symbol
            for symbol, position in self.paper_broker.positions.items()
            if position.quantity > 0 and not self.is_pair_symbol(symbol)
        ]
        for symbol in held:
            if symbol not in universe:
                universe.append(symbol)
        self.state.active_trading_symbols = universe[: self.config.live.max_symbols + len(held)]
        return self.state.active_trading_symbols

    def _grid_symbol_active(self, symbol: str) -> bool:
        if self.is_pair_symbol(symbol):
            return False
        if self.single_name_quantity(symbol) > 0:
            return True
        return symbol in getattr(self.state, "active_trading_symbols", [])

    def build_plans(
        self, quote: LiveQuote, snapshot: IndicatorSnapshot, regime: MarketRegime
    ) -> tuple[DynamicGridPlan, MomentumPlan, bool]:
        spacing_mult = 1.0
        sentiment_score = 0.0
        sentiment_allows = True
        seed_allowed = True
        if self.sentiment_service is not None:
            spacing_mult = self.sentiment_service.spacing_multiplier(quote.symbol)
            row = self.sentiment_service.symbol(quote.symbol)
            if row is not None:
                sentiment_score = row.score
            sentiment_allows = self.sentiment_service.momentum_allowed(quote.symbol)
            seed_allowed = self.sentiment_service.seed_deploy_allowed(quote.symbol)

        grid_plan = self.grid_strategy.build_plan(
            DynamicGridInputs(
                quote=quote,
                fair_value=snapshot.fair_value,
                atr_14=snapshot.atr_14,
                regime=regime,
                current_quantity=self.single_name_quantity(quote.symbol),
                sentiment_spacing_multiplier=spacing_mult,
                seed_deploy_allowed=seed_allowed and self._grid_symbol_active(quote.symbol),
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
        return grid_plan, momentum_plan, seed_allowed

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
        self._update_trading_universe()
        grid_plan, momentum_plan, seed_allowed = self.build_plans(quote, snapshot, regime)
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
            sentiment_exit = self._sentiment_exit_order(quote, current_qty)
            if sentiment_exit is not None:
                # Negative buzz on a held name -> risk-off: flatten and stop re-arming.
                self.execution.cancel_resting_except(quote.symbol, set())
                single_name_orders = [sentiment_exit]
            else:
                grid_active = self._grid_symbol_active(quote.symbol)
                if force_exit_only or (trading_open and grid_active):
                    position = self.paper_broker.positions.get(quote.symbol)
                    average_cost = position.avg_price if position else 0.0
                    single_name_orders = self.grid_strategy.orders_from_plan(
                        grid_plan,
                        quote,
                        current_quantity=current_qty,
                        seed_deploy_allowed=seed_allowed and self._grid_symbol_active(quote.symbol),
                        average_cost=average_cost,
                    )
                elif trading_open and not grid_active:
                    self.execution.cancel_resting_except(quote.symbol, set())
                if trading_open and grid_active:
                    single_name_orders.extend(self.momentum_strategy.orders_from_plan(momentum_plan, quote))

        single_name_orders = _filter_orders_for_session(single_name_orders, session_phase)
        pair_orders = _filter_orders_for_session(pair_orders, session_phase)
        single_name_orders = self._filter_grid_churn(single_name_orders)
        single_name_orders = self._apply_sentiment_sizing(single_name_orders)

        if self._resting_grid_enabled() and not self.is_pair_symbol(quote.symbol) and self._grid_symbol_active(quote.symbol):
            single_name_orders = [
                order
                for order in single_name_orders
                if not (order.reason or "").startswith("dynamic_grid_level_")
            ]
        self.sync_all_active_resting_orders()

        single_name_fills = self._submit_orders(single_name_orders)
        resting_fills = self._process_resting_fills()
        pair_fills = self._submit_pair_orders_atomic(pair_orders)
        self.state.orders.extend(single_name_orders + pair_orders)
        self.state.fills.extend(single_name_fills + resting_fills + pair_fills)
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
        active = len(self.state.active_trading_symbols) or self.config.live.max_symbols
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
        resting_total = len(self.paper_broker.resting_orders)
        armed_symbols = sum(
            1
            for symbol in self.state.active_trading_symbols
            if (plan := self.state.plans.get(symbol)) and plan.buy_levels and plan.regime == MarketRegime.RANGE
        )
        grid_status = "WAITING"
        if resting_total:
            grid_status = f"ARMED({resting_total})"
        elif armed_symbols:
            grid_status = "ACTIVE"
        elif grid_plan.buy_levels:
            grid_status = "ACTIVE"
        status = {
            "regime": regime.value,
            "regime_summary": self._regime_summary(),
            "grid": grid_status,
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
