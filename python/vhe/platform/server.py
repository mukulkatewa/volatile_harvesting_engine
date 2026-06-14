from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from vhe.backtest.models import Order, OrderSide, OrderType
from vhe.execution.paper import PaperBroker
from vhe.execution.risk import RiskConfig, RiskGuard
from vhe.live.feed import SimulatedQuoteFeed
from vhe.platform.events import event
from vhe.platform.state import PlatformState
from vhe.strategies.dynamic_grid import DynamicGridInputs, DynamicGridStrategy
from vhe.strategies.momentum import MomentumInputs, MomentumStrategy
from vhe.strategies.pair_spread import PairConfig, PairInputs, PairSpreadStrategy
from vhe.strategies.regime import MarketRegime

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Volatility Harvesting Engine")
state = PlatformState()
grid_strategy = DynamicGridStrategy()
momentum_strategy = MomentumStrategy()
pair_strategy = PairSpreadStrategy(PairConfig(symbol_a="RELIANCE", symbol_b="HDFCBANK", hedge_ratio=1.0, mean=-0.04, std=0.006))
paper_broker = PaperBroker(initial_cash=25_000.0)
risk_guard = RiskGuard(RiskConfig())
feed_task: asyncio.Task | None = None
subscribers: set[WebSocket] = set()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def startup() -> None:
    global feed_task
    if feed_task is None:
        feed_task = asyncio.create_task(_run_feed())


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (STATIC_DIR / "index.html").read_text()


@app.get("/api/state")
async def api_state() -> dict:
    return state.snapshot()


@app.post("/api/control/pause")
async def pause_automation() -> dict:
    risk_guard.automation_paused = True
    state.controls.automation_paused = True
    state.append_event(event("control", "Automation paused", "warning"))
    await _broadcast_state()
    return state.snapshot()


@app.post("/api/control/resume")
async def resume_automation() -> dict:
    risk_guard.automation_paused = False
    risk_guard.kill_switch = False
    state.controls.automation_paused = False
    state.controls.kill_switch = False
    state.controls.last_risk_reject = None
    state.append_event(event("control", "Automation resumed"))
    await _broadcast_state()
    return state.snapshot()


@app.post("/api/control/kill")
async def activate_kill_switch() -> dict:
    risk_guard.kill_switch = True
    state.controls.kill_switch = True
    state.controls.last_risk_reject = "kill_switch_active"
    state.append_event(event("risk", "Kill switch activated", "danger"))
    await _broadcast_state()
    return state.snapshot()


@app.post("/api/control/reset-paper")
async def reset_paper() -> dict:
    global paper_broker
    paper_broker = PaperBroker(initial_cash=25_000.0)
    state.orders.clear()
    state.fills.clear()
    state.portfolio = paper_broker.snapshot(state.quotes)
    state.controls.last_risk_reject = None
    state.append_event(event("control", "Paper account reset"))
    await _broadcast_state()
    return state.snapshot()


@app.post("/api/control/demo-fill")
async def demo_fill() -> dict:
    if not state.quotes:
        return state.snapshot()
    symbol = sorted(state.quotes)[0]
    quote = state.quotes[symbol]
    order = Order(
        order_id=f"demo-{symbol}-{len(state.orders) + 1}",
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=quote.ltp,
        quantity=1,
        created_at=quote.timestamp,
        reason="demo_paper_fill",
    )
    fill = paper_broker.submit(order, quote)
    state.orders.append(order)
    if fill is not None:
        state.fills.append(fill)
        state.append_event(event("fill", f"Demo fill {fill.side.value} {fill.symbol} x{fill.quantity}"))
    state.portfolio = paper_broker.snapshot(state.quotes)
    await _broadcast_state()
    return state.snapshot()


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@app.websocket("/ws/state")
async def ws_state(websocket: WebSocket) -> None:
    await websocket.accept()
    subscribers.add(websocket)
    try:
        await websocket.send_json(state.snapshot())
        while True:
            await asyncio.sleep(30)
    finally:
        subscribers.discard(websocket)


async def _run_feed() -> None:
    feed = SimulatedQuoteFeed(symbols=["RELIANCE", "HDFCBANK", "TATAMOTORS", "BEL"], interval_seconds=0.75)
    state.connected = True
    async for quote in feed.stream():
        fair_value = quote.close
        atr = max(quote.high - quote.low, quote.ltp * 0.006)
        regime = _simulated_regime(quote)
        current_quantity = _single_name_quantity(quote.symbol)

        grid_plan = grid_strategy.build_plan(
            DynamicGridInputs(
                quote=quote,
                fair_value=fair_value,
                atr_14=atr,
                regime=regime,
                current_quantity=current_quantity,
            )
        )
        momentum_plan = momentum_strategy.build_plan(
            MomentumInputs(
                quote=quote,
                regime=regime,
                ema_20=quote.close - (atr * 0.04),
                ema_50=quote.close - (atr * 0.14),
                atr_14=atr,
                current_quantity=current_quantity,
            )
        )

        state.quotes[quote.symbol] = quote
        state.plans[quote.symbol] = grid_plan
        state.momentum_plans[quote.symbol] = momentum_plan
        state.portfolio = paper_broker.snapshot(state.quotes)
        pair_orders = _pair_orders_if_ready()

        single_name_orders = [] if _is_pair_symbol(quote.symbol) else grid_strategy.orders_from_plan(grid_plan, quote) + momentum_strategy.orders_from_plan(momentum_plan, quote)
        orders = single_name_orders + pair_orders
        fills = _submit_orders(orders)
        state.orders.extend(orders)
        state.fills.extend(fills)
        state.portfolio = paper_broker.snapshot(state.quotes)
        await _broadcast_state()


def _is_pair_symbol(symbol: str) -> bool:
    return symbol in {pair_strategy.config.symbol_a, pair_strategy.config.symbol_b}


def _single_name_quantity(symbol: str) -> int:
    if _is_pair_symbol(symbol):
        return 0
    position = paper_broker.positions.get(symbol)
    return position.quantity if position else 0


def _pair_orders_if_ready() -> list[Order]:
    quote_a = state.quotes.get(pair_strategy.config.symbol_a)
    quote_b = state.quotes.get(pair_strategy.config.symbol_b)
    if quote_a is None or quote_b is None:
        return []
    position_a = paper_broker.positions.get(pair_strategy.config.symbol_a)
    current_position = position_a.quantity if position_a else 0
    plan = pair_strategy.build_plan(
        PairInputs(
            quote_a=quote_a,
            quote_b=quote_b,
            regime=MarketRegime.RANGE,
            current_position=current_position,
        )
    )
    state.pair_plans[plan.pair_id] = plan
    return pair_strategy.orders_from_plan(plan, quote_a, quote_b)


def _submit_orders(orders: list[Order]) -> list:
    fills = []
    for order in orders:
        quote = state.quotes.get(order.symbol)
        if quote is None:
            state.append_event(event("risk", f"Rejected {order.symbol}: missing_quote", "warning"))
            continue

        decision = risk_guard.evaluate(order, state.portfolio)
        if not decision.approved:
            state.controls.last_risk_reject = decision.reason
            state.append_event(event("risk", f"Rejected {order.symbol}: {decision.reason}", "warning"))
            continue

        fill = paper_broker.submit(order, quote)
        if fill is not None:
            fills.append(fill)
            state.portfolio = paper_broker.snapshot(state.quotes)
            state.append_event(event("fill", f"{fill.side.value} {fill.symbol} x{fill.quantity} @ {fill.price:.2f}"))
    return fills


def _simulated_regime(quote) -> MarketRegime:
    if quote.symbol == "HDFCBANK" and quote.ltp > quote.close:
        return MarketRegime.TREND_UP
    return MarketRegime.RANGE


async def _broadcast_state() -> None:
    if not subscribers:
        return
    snapshot = state.snapshot()
    stale: set[WebSocket] = set()
    for websocket in subscribers:
        try:
            await websocket.send_json(snapshot)
        except RuntimeError:
            stale.add(websocket)
    subscribers.difference_update(stale)
