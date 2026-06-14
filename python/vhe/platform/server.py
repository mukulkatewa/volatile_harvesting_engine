from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from vhe.live.feed import SimulatedQuoteFeed
from vhe.platform.state import PlatformState
from vhe.strategies.dynamic_grid import DynamicGridInputs, DynamicGridStrategy
from vhe.strategies.regime import MarketRegime

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Volatility Harvesting Engine")
state = PlatformState()
strategy = DynamicGridStrategy()
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
        plan = strategy.build_plan(
            DynamicGridInputs(
                quote=quote,
                fair_value=fair_value,
                atr_14=atr,
                regime=MarketRegime.RANGE,
                current_quantity=0,
            )
        )
        orders = strategy.orders_from_plan(plan, quote)
        state.quotes[quote.symbol] = quote
        state.plans[quote.symbol] = plan
        state.orders.extend(orders)
        await _broadcast_state()


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
