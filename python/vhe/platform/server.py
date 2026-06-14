from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from vhe.execution.paper import PaperBroker
from vhe.live.feed import SimulatedQuoteFeed
from vhe.platform.state import PlatformState
from vhe.strategies.dynamic_grid import DynamicGridInputs, DynamicGridStrategy
from vhe.strategies.momentum import MomentumInputs, MomentumStrategy
from vhe.strategies.regime import MarketRegime

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Volatility Harvesting Engine")
state = PlatformState()
grid_strategy = DynamicGridStrategy()
momentum_strategy = MomentumStrategy()
paper_broker = PaperBroker(initial_cash=25_000.0)
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
        current_quantity = paper_broker.positions.get(quote.symbol).quantity if quote.symbol in paper_broker.positions else 0

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

        orders = grid_strategy.orders_from_plan(grid_plan, quote) + momentum_strategy.orders_from_plan(momentum_plan, quote)
        fills = []
        for order in orders:
            fill = paper_broker.submit(order, quote)
            if fill is not None:
                fills.append(fill)

        state.quotes[quote.symbol] = quote
        state.plans[quote.symbol] = grid_plan
        state.momentum_plans[quote.symbol] = momentum_plan
        state.orders.extend(orders)
        state.fills.extend(fills)
        state.portfolio = paper_broker.snapshot(state.quotes)
        await _broadcast_state()


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
