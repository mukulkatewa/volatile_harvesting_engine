# Phase 1: Monte Carlo Risk Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Monte Carlo risk simulation engine that bootstrap-resamples backtest trade logs to produce P&L distributions, VaR, CVaR, ruin probability, and Kelly fraction, exposed via a FastAPI endpoint and rendered in a new Risk tab on the vanilla JS dashboard.

**Architecture:** Pure Python computation in `vhe/backtest/monte_carlo.py`, wired to a new `POST /api/backtest/monte-carlo` endpoint in `server.py`. The endpoint runs the existing `EventDrivenBacktester` to generate trades, then passes them to the MC engine. The Risk tab is added to the vanilla JS dashboard using the existing `data-view` / `switchView` pattern and Chart.js from CDN.

**Tech Stack:** Python 3.12, numpy (already a transitive dep via pandas), FastAPI, vanilla JS + Chart.js CDN

---

## File Map

| File | Action |
|------|--------|
| `python/vhe/backtest/monte_carlo.py` | Create — MC engine |
| `python/tests/test_monte_carlo.py` | Create — unit tests |
| `python/vhe/platform/server.py` | Modify — add endpoint |
| `python/vhe/platform/static/index.html` | Modify — add Risk nav button + Risk view section |
| `python/vhe/platform/static/app.js` | Modify — add renderRisk tab + Chart.js MC charts |

---

## Task 1: Monte Carlo Engine (TDD)

**Files:**
- Create: `python/vhe/backtest/monte_carlo.py`
- Create: `python/tests/test_monte_carlo.py`

- [ ] **Step 1.1: Write failing tests**

Create `python/tests/test_monte_carlo.py`:

```python
from __future__ import annotations

import pytest

from vhe.backtest.ledger import TradeRecord
from vhe.backtest.monte_carlo import MonteCarloResult, run


def _trades(n_win: int, win_pnl: float, n_lose: int, lose_pnl: float) -> list[TradeRecord]:
    wins = [TradeRecord(entry_price=100.0, exit_price=100.0, quantity=1, pnl=win_pnl, fees=0.0) for _ in range(n_win)]
    losses = [TradeRecord(entry_price=100.0, exit_price=100.0, quantity=1, pnl=lose_pnl, fees=0.0) for _ in range(n_lose)]
    return wins + losses


def test_run_returns_result_dataclass() -> None:
    result = run(_trades(8, 100.0, 2, -50.0), initial_capital=10_000, n_sims=500, rng_seed=42)
    assert isinstance(result, MonteCarloResult)
    assert result.sim_count == 500
    assert result.trade_count == 10


def test_positive_edge_low_ruin_probability() -> None:
    result = run(_trades(8, 100.0, 2, -50.0), initial_capital=10_000, n_sims=1000, rng_seed=42)
    assert result.p_ruin < 0.05
    assert result.pnl_percentiles["p50"] > 0


def test_negative_edge_high_ruin_probability() -> None:
    result = run(_trades(2, 50.0, 8, -100.0), initial_capital=10_000, n_sims=1000, rng_seed=42)
    assert result.p_ruin > 0.30


def test_kelly_clamps_to_zero_when_losing() -> None:
    result = run(_trades(1, 10.0, 9, -100.0), initial_capital=10_000, n_sims=500, rng_seed=0)
    assert result.kelly_fraction == 0.0


def test_kelly_clamps_to_max_025() -> None:
    result = run(_trades(10, 1000.0, 1, -1.0), initial_capital=10_000, n_sims=500, rng_seed=0)
    assert result.kelly_fraction <= 0.25


def test_raises_on_fewer_than_10_trades() -> None:
    with pytest.raises(ValueError, match="need at least 10 trades"):
        run(_trades(4, 100.0, 5, -50.0), initial_capital=10_000)


def test_equity_curves_at_most_100() -> None:
    result = run(_trades(6, 80.0, 4, -60.0), initial_capital=10_000, n_sims=500, rng_seed=1)
    assert len(result.equity_curves) <= 100
    assert len(result.equity_curves) > 0


def test_var_below_median_for_positive_edge() -> None:
    result = run(_trades(7, 80.0, 3, -60.0), initial_capital=10_000, n_sims=2000, rng_seed=7)
    # var_95 is the 5th-percentile equity; median equity should be higher
    assert result.var_95 <= result.pnl_percentiles["p50"] + 10_000


def test_pnl_percentiles_keys_present() -> None:
    result = run(_trades(5, 100.0, 5, -80.0), initial_capital=10_000, n_sims=500, rng_seed=3)
    assert set(result.pnl_percentiles.keys()) == {"p5", "p25", "p50", "p75", "p95"}


def test_cvar_le_var() -> None:
    result = run(_trades(5, 100.0, 5, -80.0), initial_capital=10_000, n_sims=1000, rng_seed=5)
    assert result.cvar_95 <= result.var_95 + 1.0  # CVaR (expected shortfall) ≤ VaR
```

- [ ] **Step 1.2: Run tests — expect ImportError / NameError**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/test_monte_carlo.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'MonteCarloResult' from 'vhe.backtest.monte_carlo'` (module doesn't exist yet)

- [ ] **Step 1.3: Implement `monte_carlo.py`**

Create `python/vhe/backtest/monte_carlo.py`:

```python
from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from vhe.backtest.ledger import TradeRecord


@dataclass(slots=True)
class MonteCarloResult:
    var_95: float
    cvar_95: float
    p_ruin: float
    drawdown_p95: float
    kelly_fraction: float
    pnl_percentiles: dict[str, float]
    equity_curves: list[list[float]]
    sim_count: int
    trade_count: int


def run(
    trades: list[TradeRecord],
    initial_capital: float,
    n_sims: int = 10_000,
    rng_seed: int | None = None,
) -> MonteCarloResult:
    if len(trades) < 10:
        raise ValueError(f"need at least 10 trades, got {len(trades)}")
    if n_sims > 100_000:
        raise ValueError("n_sims must be <= 100,000")

    rng = random.Random(rng_seed)
    pnls = [t.pnl for t in trades]

    final_equities: list[float] = []
    max_drawdowns: list[float] = []
    ruin_count = 0
    sampled_curves: list[list[float]] = []

    for i in range(n_sims):
        sample = rng.choices(pnls, k=len(pnls))
        equity = initial_capital
        peak = equity
        max_dd = 0.0
        curve: list[float] = [equity]
        for pnl in sample:
            equity += pnl
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
            curve.append(equity)
        final_equities.append(equity)
        max_drawdowns.append(max_dd)
        if equity < initial_capital * 0.5:
            ruin_count += 1
        if i < 100:
            sampled_curves.append(curve)

    arr = np.array(final_equities, dtype=np.float64)
    dd_arr = np.array(max_drawdowns, dtype=np.float64)

    var_95 = float(np.percentile(arr, 5))
    tail = arr[arr <= var_95]
    cvar_95 = float(tail.mean()) if tail.size > 0 else var_95

    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl < 0]
    win_rate = len(winners) / len(trades)
    loss_rate = 1.0 - win_rate
    avg_win = sum(t.pnl for t in winners) / len(winners) if winners else 1.0
    avg_loss = abs(sum(t.pnl for t in losers) / len(losers)) if losers else 1.0
    b = avg_win / avg_loss if avg_loss > 0 else 1.0
    kelly = win_rate - loss_rate / b
    kelly = max(0.0, min(0.25, kelly))

    pnl_arr = arr - initial_capital
    return MonteCarloResult(
        var_95=var_95,
        cvar_95=cvar_95,
        p_ruin=ruin_count / n_sims,
        drawdown_p95=float(np.percentile(dd_arr, 95)),
        kelly_fraction=round(kelly, 4),
        pnl_percentiles={
            "p5": float(np.percentile(pnl_arr, 5)),
            "p25": float(np.percentile(pnl_arr, 25)),
            "p50": float(np.percentile(pnl_arr, 50)),
            "p75": float(np.percentile(pnl_arr, 75)),
            "p95": float(np.percentile(pnl_arr, 95)),
        },
        equity_curves=sampled_curves,
        sim_count=n_sims,
        trade_count=len(trades),
    )
```

- [ ] **Step 1.4: Run tests — expect all pass**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/test_monte_carlo.py -v
```

Expected output:
```
PASSED test_run_returns_result_dataclass
PASSED test_positive_edge_low_ruin_probability
PASSED test_negative_edge_high_ruin_probability
PASSED test_kelly_clamps_to_zero_when_losing
PASSED test_kelly_clamps_to_max_025
PASSED test_raises_on_fewer_than_10_trades
PASSED test_equity_curves_at_most_100
PASSED test_var_below_median_for_positive_edge
PASSED test_pnl_percentiles_keys_present
PASSED test_cvar_le_var
10 passed
```

- [ ] **Step 1.5: Commit**

```bash
git add python/vhe/backtest/monte_carlo.py python/tests/test_monte_carlo.py
git commit -m "feat: add Monte Carlo risk engine with bootstrap simulation"
```

---

## Task 2: FastAPI Endpoint

**Files:**
- Modify: `python/vhe/platform/server.py`

- [ ] **Step 2.1: Add imports and request model at the top of server.py**

Open `python/vhe/platform/server.py`. After the existing imports block, add:

```python
from fastapi import HTTPException
from pydantic import BaseModel
```

Note: `FastAPI` is already imported. Only add what's missing.

- [ ] **Step 2.2: Add the endpoint after the existing `/api/sentiment/refresh` route**

In `python/vhe/platform/server.py`, add this after the `refresh_sentiment` function:

```python
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
```

- [ ] **Step 2.3: Verify server imports cleanly**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -c "from vhe.platform.server import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 2.4: Run full test suite — no regressions**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/ -x -q 2>&1 | tail -10
```

Expected: all tests pass, no errors.

- [ ] **Step 2.5: Commit**

```bash
git add python/vhe/platform/server.py
git commit -m "feat: add POST /api/backtest/monte-carlo endpoint"
```

---

## Task 3: Risk Tab UI (vanilla JS)

**Files:**
- Modify: `python/vhe/platform/static/index.html`
- Modify: `python/vhe/platform/static/app.js`

- [ ] **Step 3.1: Add Risk nav button and Risk view section to index.html**

In `python/vhe/platform/static/index.html`, find the nav buttons block:

```html
          <button type="button" class="nav-item" data-panel="activity">Activity</button>
```

Add after it:

```html
          <button type="button" class="nav-item" data-panel="risk">Risk</button>
```

Then find the closing `</section>` of the activity view (last `</section>` before `</main>`):

```html
        </section>
      </main>
```

Insert a new section before `</main>`:

```html
        <section class="view" data-view="risk">
          <div class="risk-header">
            <h2 class="risk-title">Monte Carlo Risk Analysis</h2>
            <div class="risk-controls">
              <input id="mc-symbol" class="risk-input" placeholder="Symbol e.g. RELIANCE" />
              <input id="mc-bars-file" class="risk-input" placeholder="bars_file e.g. data/RELIANCE.csv" />
              <input id="mc-n-sims" class="risk-input" type="number" value="5000" min="100" max="100000" />
              <button id="mc-run-btn" class="ctrl-btn primary">Run MC</button>
            </div>
          </div>
          <div id="mc-error" class="risk-error" style="display:none"></div>
          <div id="mc-results" style="display:none">
            <div class="risk-metrics-grid" id="mc-metrics"></div>
            <div class="risk-charts-row">
              <div class="risk-chart-wrap">
                <div class="risk-chart-label">P&amp;L Distribution</div>
                <canvas id="mc-hist-canvas" height="220"></canvas>
              </div>
              <div class="risk-chart-wrap">
                <div class="risk-chart-label">Equity Curve Scenarios</div>
                <canvas id="mc-curves-canvas" height="220"></canvas>
              </div>
            </div>
          </div>
        </section>
```

Also add Chart.js CDN just before the closing `</body>` tag:

```html
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
    <script src="/static/app.js?v=27"></script>
  </body>
```

(Remove the existing `<script src="/static/app.js?v=...">` line since we're replacing it here.)

- [ ] **Step 3.2: Add CSS for risk tab to styles.css**

In `python/vhe/platform/static/styles.css`, append at the end:

```css
/* ── Risk Tab ─────────────────────────────────────────────────── */
.risk-header { padding: 20px 24px 0; display: flex; flex-direction: column; gap: 16px; }
.risk-title { margin: 0; font: 600 18px var(--sans); color: var(--text); }
.risk-controls { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.risk-input {
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text);
  font: 13px var(--mono);
  padding: 8px 12px;
  border-radius: 8px;
  min-width: 180px;
}
.risk-input::placeholder { color: var(--faint); }
.risk-error {
  margin: 12px 24px;
  padding: 10px 14px;
  background: var(--red-dim);
  border: 1px solid rgba(255,107,107,0.3);
  border-radius: 8px;
  color: var(--red);
  font: 13px var(--mono);
}
.risk-metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  padding: 16px 24px 0;
}
.risk-metric-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
}
.risk-metric-label { font: 600 10px var(--sans); color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }
.risk-metric-value { font: 600 18px var(--mono); color: var(--text); margin-top: 4px; }
.risk-metric-value.good { color: var(--green); }
.risk-metric-value.bad { color: var(--red); }
.risk-metric-value.warn { color: var(--amber); }
.risk-charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 16px 24px 24px;
}
.risk-chart-wrap {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
}
.risk-chart-label { font: 600 11px var(--sans); color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px; }
```

- [ ] **Step 3.3: Add MC rendering logic to app.js**

In `python/vhe/platform/static/app.js`, append at the end of the file:

```javascript
// ── Monte Carlo Risk Tab ───────────────────────────────────────

let mcHistChart = null;
let mcCurvesChart = null;

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("mc-run-btn");
  if (btn) btn.addEventListener("click", runMonteCarlo);
});

async function runMonteCarlo() {
  const symbol = document.getElementById("mc-symbol")?.value?.trim();
  const barsFile = document.getElementById("mc-bars-file")?.value?.trim();
  const nSims = parseInt(document.getElementById("mc-n-sims")?.value || "5000", 10);
  const errorEl = document.getElementById("mc-error");
  const resultsEl = document.getElementById("mc-results");

  errorEl.style.display = "none";
  resultsEl.style.display = "none";

  if (!symbol || !barsFile) {
    errorEl.textContent = "Symbol and bars_file are required.";
    errorEl.style.display = "block";
    return;
  }

  const btn = document.getElementById("mc-run-btn");
  btn.textContent = "Running…";
  btn.disabled = true;

  try {
    const resp = await fetch("/api/backtest/monte-carlo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, bars_file: barsFile, n_sims: nSims }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || resp.statusText);
    }
    const data = await resp.json();
    renderMCResults(data);
  } catch (err) {
    errorEl.textContent = `Error: ${err.message}`;
    errorEl.style.display = "block";
  } finally {
    btn.textContent = "Run MC";
    btn.disabled = false;
  }
}

function renderMCResults(data) {
  const resultsEl = document.getElementById("mc-results");
  const metricsEl = document.getElementById("mc-metrics");
  const ic = 75000; // default initial capital label

  const pnlP50 = data.pnl_percentiles?.p50 ?? 0;
  const pClass = pnlP50 >= 0 ? "good" : "bad";
  const ruinClass = data.p_ruin < 0.05 ? "good" : data.p_ruin < 0.15 ? "warn" : "bad";

  metricsEl.innerHTML = [
    { label: "Median P&L", value: money.format(pnlP50), cls: pClass },
    { label: "VaR 95%", value: money.format(data.var_95 - ic), cls: "bad" },
    { label: "CVaR 95%", value: money.format(data.cvar_95 - ic), cls: "bad" },
    { label: "Max DD P95", value: `${(data.drawdown_p95 * 100).toFixed(1)}%`, cls: data.drawdown_p95 > 0.05 ? "warn" : "good" },
    { label: "P(Ruin)", value: `${(data.p_ruin * 100).toFixed(1)}%`, cls: ruinClass },
    { label: "Kelly f*", value: `${(data.kelly_fraction * 100).toFixed(1)}%`, cls: "good" },
    { label: "Trades", value: String(data.trade_count), cls: "" },
    { label: "Simulations", value: String(data.sim_count), cls: "" },
  ].map(({ label, value, cls }) => `
    <div class="risk-metric-card">
      <div class="risk-metric-label">${label}</div>
      <div class="risk-metric-value ${cls}">${value}</div>
    </div>
  `).join("");

  renderMCHistogram(data);
  renderMCCurves(data, ic);
  resultsEl.style.display = "block";
}

function renderMCHistogram(data) {
  const canvas = document.getElementById("mc-hist-canvas");
  if (!canvas) return;
  if (mcHistChart) { mcHistChart.destroy(); mcHistChart = null; }

  const ic = 75000;
  const p5 = data.pnl_percentiles.p5;
  const p95 = data.pnl_percentiles.p95;
  const buckets = 20;
  const step = (p95 - p5) / buckets || 1;
  const counts = new Array(buckets).fill(0);
  const labels = [];
  for (let i = 0; i < buckets; i++) {
    labels.push(Math.round(p5 + step * i));
  }

  // Approximate distribution from percentiles as a simple bar chart
  const pctKeys = ["p5", "p25", "p50", "p75", "p95"];
  const pctVals = pctKeys.map((k) => data.pnl_percentiles[k]);

  mcHistChart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: pctKeys,
      datasets: [{
        label: "P&L (₹)",
        data: pctVals,
        backgroundColor: pctVals.map((v) => v >= 0 ? "rgba(0,208,156,0.6)" : "rgba(255,107,107,0.6)"),
        borderColor: pctVals.map((v) => v >= 0 ? "#00d09c" : "#ff6b6b"),
        borderWidth: 1,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#8b97a8" }, grid: { color: "rgba(148,163,184,0.08)" } },
        y: { ticks: { color: "#8b97a8" }, grid: { color: "rgba(148,163,184,0.08)" } },
      },
    },
  });
}

function renderMCCurves(data, ic) {
  const canvas = document.getElementById("mc-curves-canvas");
  if (!canvas) return;
  if (mcCurvesChart) { mcCurvesChart.destroy(); mcCurvesChart = null; }

  const curves = (data.equity_curves || []).slice(0, 50);
  if (!curves.length) return;
  const n = curves[0].length;
  const labels = Array.from({ length: n }, (_, i) => i);

  const datasets = curves.map((curve, i) => ({
    data: curve,
    borderColor: "rgba(56,126,209,0.15)",
    borderWidth: 1,
    pointRadius: 0,
    tension: 0.2,
  }));

  // Add median line
  const median = labels.map((_, idx) => {
    const vals = curves.map((c) => c[idx] ?? ic).sort((a, b) => a - b);
    return vals[Math.floor(vals.length / 2)];
  });
  datasets.push({
    label: "Median",
    data: median,
    borderColor: "#00d09c",
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.2,
  });

  mcCurvesChart = new Chart(canvas, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      animation: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { ticks: { color: "#8b97a8" }, grid: { color: "rgba(148,163,184,0.08)" } },
      },
    },
  });
}
```

- [ ] **Step 3.4: Start the server and verify Risk tab appears**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m uvicorn vhe.platform.server:app --port 8765 --reload 2>&1 &
sleep 2 && curl -s http://localhost:8765/ | grep -c "data-panel=\"risk\""
```

Expected: `1` (the nav button is present in the HTML)

- [ ] **Step 3.5: Kill dev server and commit**

```bash
pkill -f "uvicorn vhe.platform.server" 2>/dev/null || true
git add python/vhe/platform/static/index.html python/vhe/platform/static/app.js python/vhe/platform/static/styles.css
git commit -m "feat: add Risk tab with Monte Carlo charts to dashboard"
```

---

## Task 4: Verify full test suite still passes

- [ ] **Step 4.1: Run full test suite**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/ -q 2>&1 | tail -5
```

Expected: all tests pass, 0 errors.

- [ ] **Step 4.2: Final commit if any files were missed**

```bash
git status
# If clean, nothing to do. If there are uncommitted changes, add and commit them.
```
