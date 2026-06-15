from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from vhe.backtest.models import Order, OrderSide, OrderType
from vhe.config.env import load_env_file
from vhe.platform.events import event
from vhe.platform.runtime import PlatformRuntime

STATIC_DIR = Path(__file__).resolve().parent / "static"

load_env_file()

app = FastAPI(title="Volatility Harvesting Engine")
runtime = PlatformRuntime.from_project_root()
runtime.state.phase = "0"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def startup() -> None:
    await runtime.start_feed()


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (STATIC_DIR / "index.html").read_text()


@app.get("/api/state")
async def api_state() -> dict:
    return runtime.state.snapshot()


@app.get("/api/config")
async def api_config() -> dict:
    return {
        "mode": runtime.config.live.mode,
        "capital_cap_inr": runtime.config.live.capital_cap_inr,
        "max_symbols": runtime.config.live.max_symbols,
        "force_exit_time": runtime.config.live.force_exit_time,
        "feed": runtime.config.strategies.feed.model_dump(),
        "capital_buckets": runtime.config.strategies.capital.model_dump(),
    }


@app.post("/api/control/pause")
async def pause_automation() -> dict:
    runtime.risk_guard.automation_paused = True
    runtime.state.controls.automation_paused = True
    runtime.state.append_event(event("control", "Automation paused", "warning"))
    await runtime._broadcast_state()
    return runtime.state.snapshot()


@app.post("/api/control/resume")
async def resume_automation() -> dict:
    runtime.risk_guard.automation_paused = False
    runtime.risk_guard.kill_switch = False
    runtime.state.controls.automation_paused = False
    runtime.state.controls.kill_switch = False
    runtime.state.controls.last_risk_reject = None
    runtime.state.append_event(event("control", "Automation resumed"))
    await runtime._broadcast_state()
    return runtime.state.snapshot()


@app.post("/api/control/kill")
async def activate_kill_switch() -> dict:
    runtime.risk_guard.kill_switch = True
    runtime.state.controls.kill_switch = True
    runtime.state.controls.last_risk_reject = "kill_switch_active"
    runtime.state.append_event(event("risk", "Kill switch activated", "danger"))
    await runtime._broadcast_state()
    return runtime.state.snapshot()


@app.post("/api/control/reset-paper")
async def reset_paper() -> dict:
    runtime.reset_paper()
    runtime.state.portfolio = runtime.paper_broker.snapshot(runtime.state.quotes)
    await runtime._broadcast_state()
    return runtime.state.snapshot()


@app.post("/api/control/demo-fill")
async def demo_fill() -> dict:
    if not runtime.state.quotes:
        return runtime.state.snapshot()
    symbol = sorted(runtime.state.quotes)[0]
    quote = runtime.state.quotes[symbol]
    order = Order(
        order_id=f"demo-{symbol}-{len(runtime.state.orders) + 1}",
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=quote.ltp,
        quantity=1,
        created_at=quote.timestamp,
        reason="demo_paper_fill",
    )
    fill = runtime.paper_broker.submit(order, quote)
    runtime.state.orders.append(order)
    if fill is not None:
        runtime.state.fills.append(fill)
        runtime.state.append_event(event("fill", f"Demo fill {fill.side.value} {fill.symbol} x{fill.quantity}"))
        if runtime.database:
            runtime.database.persist_fill_dataclass(fill)
    runtime.state.portfolio = runtime.paper_broker.snapshot(runtime.state.quotes)
    await runtime._broadcast_state()
    return runtime.state.snapshot()


@app.get("/favicon.ico")
async def favicon() -> Response:
    return Response(status_code=204)


@app.websocket("/ws/state")
async def ws_state(websocket: WebSocket) -> None:
    await websocket.accept()
    runtime.subscribers.add(websocket)
    try:
        await websocket.send_json(runtime.state.snapshot())
        while True:
            await asyncio.sleep(30)
    finally:
        runtime.subscribers.discard(websocket)
