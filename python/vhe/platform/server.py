from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from vhe.backtest.models import Order, OrderSide, OrderType
from vhe.config.env import load_env_file
from vhe.platform.events import event
from vhe.platform.runtime import PlatformRuntime

STATIC_DIR = Path(__file__).resolve().parent / "static"

load_env_file()

app = FastAPI(title="Volatility Harvesting Engine")
runtime = PlatformRuntime.from_project_root()

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


@app.get("/api/stats/paper")
async def api_paper_stats() -> dict:
    return runtime.paper_stats_report()


@app.get("/api/sentiment")
async def api_sentiment() -> dict:
    return runtime.sentiment_service.to_public_dict()


@app.post("/api/sentiment/refresh")
async def refresh_sentiment() -> dict:
    await runtime.sentiment_service.refresh_async()
    runtime.state.sentiment = runtime.sentiment_service.to_public_dict()
    runtime._refresh_paper_stats(force=True)
    await runtime._broadcast_state()
    return runtime.state.sentiment


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
    runtime.risk_guard.kill_switch_reason = None
    runtime.state.controls.automation_paused = False
    runtime.state.controls.kill_switch = False
    runtime.state.controls.kill_switch_reason = None
    runtime.state.controls.last_risk_reject = None
    runtime.state.append_event(event("control", "Automation resumed"))
    await runtime._broadcast_state()
    return runtime.state.snapshot()


@app.post("/api/control/kill")
async def activate_kill_switch() -> dict:
    runtime.risk_guard.kill_switch = True
    runtime.risk_guard.kill_switch_reason = "manual_kill"
    runtime.state.controls.kill_switch = True
    runtime.state.controls.kill_switch_reason = "manual_kill"
    runtime.state.controls.last_risk_reject = "kill_switch_active"
    runtime.state.append_event(event("risk", "Kill switch activated", "danger"))
    await runtime._broadcast_state()
    return runtime.state.snapshot()


@app.post("/api/control/reset-paper")
async def reset_paper() -> dict:
    runtime.reset_paper()
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
    fill = runtime.execution.submit(order, quote)
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


class MonteCarloRequest(BaseModel):
    symbol: str
    bars_file: str
    n_sims: int = 10_000
    initial_capital: float = 75_000.0


@app.post("/api/backtest/monte-carlo")
async def run_monte_carlo(req: MonteCarloRequest) -> dict:
    import pandas as pd
    from datetime import time
    from pathlib import Path as FilePath

    from vhe.backtest.engine import EventDrivenBacktester
    from vhe.backtest.monte_carlo import run as mc_run
    from vhe.strategies.adaptive_grid import AdaptiveGridConfig, AdaptiveGridStrategy

    if req.n_sims > 100_000:
        raise HTTPException(status_code=422, detail="n_sims must be <= 100,000")

    bars_path = FilePath(req.bars_file)
    if not bars_path.is_absolute():
        bars_path = STATIC_DIR.parents[3] / req.bars_file
    if not bars_path.exists():
        raise HTTPException(status_code=400, detail=f"bars_file not found: {req.bars_file}")

    if bars_path.suffix.lower() == ".csv":
        bars = pd.read_csv(bars_path)
    elif bars_path.suffix.lower() == ".parquet":
        bars = pd.read_parquet(bars_path)
    else:
        raise HTTPException(status_code=400, detail="bars_file must be .csv or .parquet")

    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    symbol = req.symbol.upper()
    bars = bars[bars["symbol"].astype(str).str.upper() == symbol]
    if bars.empty:
        raise HTTPException(status_code=400, detail=f"no bars found for symbol {symbol}")

    strategy = AdaptiveGridStrategy(
        config=AdaptiveGridConfig(
            symbol_capital=req.initial_capital * 0.70,
            force_exit_time=time(15, 10),
        ),
        symbol=symbol,
    )
    backtester = EventDrivenBacktester(strategy=strategy, initial_cash=req.initial_capital)
    backtester.run(bars)

    trades = backtester.ledger.trades
    if len(trades) < 10:
        raise HTTPException(
            status_code=400,
            detail=f"backtest produced only {len(trades)} trades — need at least 10",
        )

    result = mc_run(trades, initial_capital=req.initial_capital, n_sims=req.n_sims)
    return {
        "var_95": result.var_95,
        "cvar_95": result.cvar_95,
        "p_ruin": result.p_ruin,
        "drawdown_p95": result.drawdown_p95,
        "kelly_fraction": result.kelly_fraction,
        "pnl_percentiles": result.pnl_percentiles,
        "equity_curves": result.equity_curves,
        "sim_count": result.sim_count,
        "trade_count": result.trade_count,
    }


@app.websocket("/ws/state")
async def ws_state(websocket: WebSocket) -> None:
    await websocket.accept()
    runtime.subscribers.add(websocket)
    try:
        try:
            await websocket.send_json(runtime.state.snapshot())
        except Exception:
            runtime.subscribers.discard(websocket)
            return
        while True:
            await asyncio.sleep(30)
    finally:
        runtime.subscribers.discard(websocket)
