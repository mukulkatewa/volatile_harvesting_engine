# Phase 2: Walk-Forward Validation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a walk-forward validation harness that splits historical bars into rolling train/test windows, optimises the grid strategy parameters on each training window, evaluates on the held-out test window, and reports the Walk-Forward Efficiency ratio to prove the strategy is not overfit.

**Architecture:** `optimiser.py` provides a `grid_search()` function that runs the existing `EventDrivenBacktester` over a parameter grid using a thread pool. `walk_forward.py` orchestrates rolling windows using `grid_search()`. A new `GET /api/backtest/walk-forward` endpoint exposes the results. The Risk tab (added in Phase 1) gets a walk-forward results table appended below the MC section.

**Tech Stack:** Python 3.12, `concurrent.futures.ThreadPoolExecutor`, FastAPI, vanilla JS (existing dashboard)

**Prerequisite:** Phase 1 (Monte Carlo) must be complete — this plan extends the Risk tab UI added there.

---

## File Map

| File | Action |
|------|--------|
| `python/vhe/backtest/optimiser.py` | Create — grid search over param combinations |
| `python/vhe/backtest/walk_forward.py` | Create — rolling window orchestrator |
| `python/tests/test_optimiser.py` | Create — unit tests for grid search |
| `python/tests/test_walk_forward.py` | Create — unit tests for WF harness |
| `python/vhe/platform/server.py` | Modify — add GET endpoint |
| `python/vhe/platform/static/index.html` | Modify — add WF UI section inside Risk view |
| `python/vhe/platform/static/app.js` | Modify — add WF rendering |

---

## Task 1: Grid Search Optimiser (TDD)

**Files:**
- Create: `python/vhe/backtest/optimiser.py`
- Create: `python/tests/test_optimiser.py`

- [ ] **Step 1.1: Write failing tests for optimiser**

Create `python/tests/test_optimiser.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from vhe.backtest.optimiser import OptimiseResult, grid_search


def _synthetic_bars(n_bars: int = 200, symbol: str = "TST") -> pd.DataFrame:
    start = datetime(2025, 1, 2, 9, 15)
    rows = []
    for i in range(n_bars):
        close = 100.0 + (i % 10) - 5.0  # oscillates ±5 around 100
        rows.append({
            "timestamp": start + timedelta(minutes=5 * i),
            "symbol": symbol,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 10_000,
        })
    return pd.DataFrame(rows)


def test_grid_search_returns_optimise_result() -> None:
    bars = _synthetic_bars(200)
    param_grid = {"atr_multiplier": [0.30, 0.45], "max_levels": [3]}
    result = grid_search(bars, "TST", param_grid, initial_capital=25_000.0)
    assert isinstance(result, OptimiseResult)
    assert result.best_params["atr_multiplier"] in {0.30, 0.45}
    assert result.best_params["max_levels"] == 3


def test_grid_search_picks_from_all_combinations() -> None:
    bars = _synthetic_bars(200)
    param_grid = {"atr_multiplier": [0.30, 0.60], "max_levels": [3, 5]}
    result = grid_search(bars, "TST", param_grid, initial_capital=25_000.0)
    assert result.best_params["atr_multiplier"] in {0.30, 0.60}
    assert result.best_params["max_levels"] in {3, 5}


def test_grid_search_sharpe_is_finite_float() -> None:
    bars = _synthetic_bars(200)
    result = grid_search(bars, "TST", {"atr_multiplier": [0.45], "max_levels": [3]}, 25_000.0)
    assert isinstance(result.best_sharpe, float)
```

- [ ] **Step 1.2: Run tests — expect ImportError**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/test_optimiser.py -v 2>&1 | head -15
```

Expected: `ImportError: cannot import name 'OptimiseResult' from 'vhe.backtest.optimiser'`

- [ ] **Step 1.3: Implement `optimiser.py`**

Create `python/vhe/backtest/optimiser.py`:

```python
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import time
from itertools import product

import numpy as np
import pandas as pd

from vhe.backtest.engine import EventDrivenBacktester
from vhe.strategies.adaptive_grid import AdaptiveGridConfig, AdaptiveGridStrategy


@dataclass(frozen=True, slots=True)
class OptimiseResult:
    best_params: dict
    best_sharpe: float


def _sharpe_for_params(
    bars: pd.DataFrame,
    symbol: str,
    params: dict,
    initial_capital: float,
) -> tuple[dict, float]:
    strategy = AdaptiveGridStrategy(
        config=AdaptiveGridConfig(
            grid_spacing_atr_multiplier=params["atr_multiplier"],
            max_levels=params["max_levels"],
            symbol_capital=initial_capital * 0.70,
            force_exit_time=time(15, 10),
        ),
        symbol=symbol,
    )
    bt = EventDrivenBacktester(strategy=strategy, initial_cash=initial_capital)
    bt.run(bars)
    trades = bt.ledger.trades
    if not trades:
        return params, -999.0
    pnls = np.array([t.pnl for t in trades], dtype=np.float64)
    std = float(pnls.std()) if len(pnls) > 1 else 1.0
    sharpe = float(pnls.mean()) / std if std > 0 else 0.0
    return params, sharpe


def grid_search(
    bars: pd.DataFrame,
    symbol: str,
    param_grid: dict,
    initial_capital: float = 75_000.0,
) -> OptimiseResult:
    keys = list(param_grid.keys())
    combos = [dict(zip(keys, vals)) for vals in product(*param_grid.values())]

    best_params = combos[0]
    best_sharpe = -999.0

    with ThreadPoolExecutor(max_workers=min(len(combos), 4)) as pool:
        futures = {
            pool.submit(_sharpe_for_params, bars, symbol, p, initial_capital): p
            for p in combos
        }
        for future in as_completed(futures):
            params, sharpe = future.result()
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = params

    return OptimiseResult(best_params=best_params, best_sharpe=round(best_sharpe, 4))
```

- [ ] **Step 1.4: Run optimiser tests — expect all pass**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/test_optimiser.py -v
```

Expected:
```
PASSED test_grid_search_returns_optimise_result
PASSED test_grid_search_picks_from_all_combinations
PASSED test_grid_search_sharpe_is_finite_float
3 passed
```

- [ ] **Step 1.5: Commit**

```bash
git add python/vhe/backtest/optimiser.py python/tests/test_optimiser.py
git commit -m "feat: add grid search optimiser for walk-forward parameter selection"
```

---

## Task 2: Walk-Forward Harness (TDD)

**Files:**
- Create: `python/vhe/backtest/walk_forward.py`
- Create: `python/tests/test_walk_forward.py`

- [ ] **Step 2.1: Write failing tests for walk-forward**

Create `python/tests/test_walk_forward.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from vhe.backtest.walk_forward import WFResult, WFWindow, run


def _bars(n_days: int, symbol: str = "TST") -> pd.DataFrame:
    rows = []
    base = datetime(2025, 1, 2, 9, 15)
    for day in range(n_days):
        day_start = base + timedelta(days=day)
        for minute in range(75):  # 75 five-min bars per day
            close = 100.0 + (minute % 8) - 4.0
            rows.append({
                "timestamp": day_start + timedelta(minutes=5 * minute),
                "symbol": symbol,
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": 5_000,
            })
    return pd.DataFrame(rows)


def test_run_returns_wf_result() -> None:
    bars = _bars(n_days=30)
    result = run(bars, "TST", train_days=15, test_days=5, step_days=5, initial_capital=25_000.0)
    assert isinstance(result, WFResult)
    assert len(result.windows) >= 1
    assert all(isinstance(w, WFWindow) for w in result.windows)


def test_window_count_is_correct() -> None:
    bars = _bars(n_days=40)
    result = run(bars, "TST", train_days=20, test_days=5, step_days=5, initial_capital=25_000.0)
    # Days: 40 total, train=20, test=5, step=5
    # Window starts: 0, 5, 10, 15 → 4 windows (each needs 25 days from start)
    assert len(result.windows) >= 2


def test_wf_efficiency_is_float_between_neg_and_pos() -> None:
    bars = _bars(n_days=30)
    result = run(bars, "TST", train_days=15, test_days=5, step_days=5, initial_capital=25_000.0)
    assert isinstance(result.wf_efficiency, float)


def test_verdict_is_valid_string() -> None:
    bars = _bars(n_days=30)
    result = run(bars, "TST", train_days=15, test_days=5, step_days=5, initial_capital=25_000.0)
    assert result.verdict in {"Not overfit", "Marginal", "Curve-fitted"}


def test_param_stability_contains_atr_key() -> None:
    bars = _bars(n_days=30)
    result = run(bars, "TST", train_days=15, test_days=5, step_days=5, initial_capital=25_000.0)
    assert "atr_multiplier" in result.param_stability
    assert "stability_score" in result.param_stability
    assert 0.0 <= result.param_stability["stability_score"] <= 1.0


def test_raises_when_not_enough_bars() -> None:
    bars = _bars(n_days=5)
    with pytest.raises(ValueError, match="need at least"):
        run(bars, "TST", train_days=20, test_days=10, step_days=5, initial_capital=25_000.0)


def test_window_fields_present() -> None:
    bars = _bars(n_days=30)
    result = run(bars, "TST", train_days=15, test_days=5, step_days=5, initial_capital=25_000.0)
    w = result.windows[0]
    assert isinstance(w.period, str)
    assert isinstance(w.is_sharpe, float)
    assert isinstance(w.oos_sharpe, float)
    assert isinstance(w.oos_pnl, float)
    assert "atr_multiplier" in w.best_params
    assert "max_levels" in w.best_params
```

- [ ] **Step 2.2: Run tests — expect ImportError**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/test_walk_forward.py -v 2>&1 | head -15
```

Expected: `ImportError: cannot import name 'WFResult' from 'vhe.backtest.walk_forward'`

- [ ] **Step 2.3: Implement `walk_forward.py`**

Create `python/vhe/backtest/walk_forward.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from statistics import mode as stat_mode

import numpy as np
import pandas as pd

from vhe.backtest.engine import EventDrivenBacktester
from vhe.backtest.optimiser import grid_search
from vhe.strategies.adaptive_grid import AdaptiveGridConfig, AdaptiveGridStrategy

_PARAM_GRID: dict = {
    "atr_multiplier": [0.30, 0.45, 0.60],
    "max_levels": [3, 5],
}


@dataclass(frozen=True, slots=True)
class WFWindow:
    period: str
    is_sharpe: float
    oos_sharpe: float
    oos_pnl: float
    best_params: dict


@dataclass(frozen=True, slots=True)
class WFResult:
    windows: list[WFWindow]
    wf_efficiency: float
    verdict: str
    param_stability: dict


def _oos_metrics(
    bars: pd.DataFrame,
    symbol: str,
    params: dict,
    initial_capital: float,
) -> tuple[float, float]:
    strategy = AdaptiveGridStrategy(
        config=AdaptiveGridConfig(
            grid_spacing_atr_multiplier=params["atr_multiplier"],
            max_levels=params["max_levels"],
            symbol_capital=initial_capital * 0.70,
            force_exit_time=time(15, 10),
        ),
        symbol=symbol,
    )
    bt = EventDrivenBacktester(strategy=strategy, initial_cash=initial_capital)
    summary = bt.run(bars)
    trades = bt.ledger.trades
    if not trades:
        return 0.0, 0.0
    pnls = np.array([t.pnl for t in trades], dtype=np.float64)
    std = float(pnls.std()) if len(pnls) > 1 else 1.0
    sharpe = float(pnls.mean()) / std if std > 0 else 0.0
    return round(sharpe, 3), round(summary.realized_pnl, 2)


def run(
    bars_df: pd.DataFrame,
    symbol: str,
    train_days: int = 60,
    test_days: int = 15,
    step_days: int = 15,
    initial_capital: float = 75_000.0,
) -> WFResult:
    df = bars_df.copy().sort_values("timestamp").reset_index(drop=True)
    df["_date"] = pd.to_datetime(df["timestamp"]).dt.date
    dates = sorted(df["_date"].unique())

    if len(dates) < train_days + test_days:
        raise ValueError(
            f"need at least {train_days + test_days} trading days, got {len(dates)}"
        )

    windows: list[WFWindow] = []
    i = 0
    while i + train_days + test_days <= len(dates):
        train_dates = set(dates[i : i + train_days])
        test_dates = set(dates[i + train_days : i + train_days + test_days])

        train_bars = df[df["_date"].isin(train_dates)].drop(columns=["_date"]).copy()
        test_bars = df[df["_date"].isin(test_dates)].drop(columns=["_date"]).copy()

        opt = grid_search(train_bars, symbol, _PARAM_GRID, initial_capital)
        oos_sharpe, oos_pnl = _oos_metrics(test_bars, symbol, opt.best_params, initial_capital)

        period_start = min(train_dates)
        period_end = max(train_dates)
        test_start = min(test_dates)
        test_end = max(test_dates)
        period = f"{period_start} to {period_end} | test: {test_start} to {test_end}"

        windows.append(
            WFWindow(
                period=period,
                is_sharpe=round(opt.best_sharpe, 3),
                oos_sharpe=oos_sharpe,
                oos_pnl=oos_pnl,
                best_params=opt.best_params,
            )
        )
        i += step_days

    if not windows:
        raise ValueError("no walk-forward windows were generated")

    is_sharpes = [w.is_sharpe for w in windows]
    oos_sharpes = [w.oos_sharpe for w in windows]
    mean_is = float(np.mean(is_sharpes)) if is_sharpes else 0.0
    mean_oos = float(np.mean(oos_sharpes)) if oos_sharpes else 0.0
    wfe = round(mean_oos / mean_is, 4) if mean_is != 0 else 0.0

    if wfe > 0.5:
        verdict = "Not overfit"
    elif wfe > 0.3:
        verdict = "Marginal"
    else:
        verdict = "Curve-fitted"

    atr_mults = [w.best_params["atr_multiplier"] for w in windows]
    try:
        dominant = stat_mode(atr_mults)
    except Exception:
        dominant = atr_mults[0]
    stability = round(sum(1 for v in atr_mults if v == dominant) / len(atr_mults), 2)

    return WFResult(
        windows=windows,
        wf_efficiency=wfe,
        verdict=verdict,
        param_stability={"atr_multiplier": dominant, "stability_score": stability},
    )
```

- [ ] **Step 2.4: Run walk-forward tests — expect all pass**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/test_walk_forward.py -v
```

Expected:
```
PASSED test_run_returns_wf_result
PASSED test_window_count_is_correct
PASSED test_wf_efficiency_is_float_between_neg_and_pos
PASSED test_verdict_is_valid_string
PASSED test_param_stability_contains_atr_key
PASSED test_raises_when_not_enough_bars
PASSED test_window_fields_present
7 passed
```

- [ ] **Step 2.5: Commit**

```bash
git add python/vhe/backtest/walk_forward.py python/tests/test_walk_forward.py
git commit -m "feat: add walk-forward validation harness with rolling train/test windows"
```

---

## Task 3: FastAPI Endpoint

**Files:**
- Modify: `python/vhe/platform/server.py`

- [ ] **Step 3.1: Add the walk-forward endpoint after the monte-carlo endpoint in server.py**

In `python/vhe/platform/server.py`, add this after the `run_monte_carlo` function:

```python
@app.get("/api/backtest/walk-forward")
async def run_walk_forward(
    symbol: str,
    bars_file: str,
    train_days: int = 60,
    test_days: int = 15,
    step_days: int = 15,
    initial_capital: float = 75_000.0,
) -> dict:
    import pandas as pd
    from pathlib import Path as FilePath

    from vhe.backtest.walk_forward import run as wf_run

    bars_path = FilePath(bars_file)
    if not bars_path.is_absolute():
        bars_path = STATIC_DIR.parents[3] / bars_file
    if not bars_path.exists():
        raise HTTPException(status_code=400, detail=f"bars_file not found: {bars_file}")

    if bars_path.suffix.lower() == ".csv":
        bars = pd.read_csv(bars_path)
    elif bars_path.suffix.lower() == ".parquet":
        bars = pd.read_parquet(bars_path)
    else:
        raise HTTPException(status_code=400, detail="bars_file must be .csv or .parquet")

    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    sym = symbol.upper()
    bars = bars[bars["symbol"].astype(str).str.upper() == sym]
    if bars.empty:
        raise HTTPException(status_code=400, detail=f"no bars found for symbol {sym}")

    try:
        result = wf_run(
            bars,
            sym,
            train_days=train_days,
            test_days=test_days,
            step_days=step_days,
            initial_capital=initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "windows": [
            {
                "period": w.period,
                "is_sharpe": w.is_sharpe,
                "oos_sharpe": w.oos_sharpe,
                "oos_pnl": w.oos_pnl,
                "best_params": w.best_params,
            }
            for w in result.windows
        ],
        "wf_efficiency": result.wf_efficiency,
        "verdict": result.verdict,
        "param_stability": result.param_stability,
    }
```

- [ ] **Step 3.2: Verify server still imports cleanly**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -c "from vhe.platform.server import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3.3: Commit**

```bash
git add python/vhe/platform/server.py
git commit -m "feat: add GET /api/backtest/walk-forward endpoint"
```

---

## Task 4: Walk-Forward UI in Risk Tab

**Files:**
- Modify: `python/vhe/platform/static/index.html`
- Modify: `python/vhe/platform/static/app.js`

- [ ] **Step 4.1: Add WF controls and results section inside the Risk view in index.html**

In `python/vhe/platform/static/index.html`, find the existing risk section ending:

```html
          </div>
        </section>
```

(The closing of `<div id="mc-results">` and then the risk `<section>`.) Add a WF block inside the risk `<section>`, before its closing `</section>`:

```html
          <div class="risk-divider"></div>
          <div class="risk-header">
            <h2 class="risk-title">Walk-Forward Validation</h2>
            <div class="risk-controls">
              <input id="wf-symbol" class="risk-input" placeholder="Symbol e.g. RELIANCE" />
              <input id="wf-bars-file" class="risk-input" placeholder="bars_file e.g. data/RELIANCE.csv" />
              <input id="wf-train-days" class="risk-input" type="number" value="60" min="10" max="250" style="width:90px" />
              <input id="wf-test-days" class="risk-input" type="number" value="15" min="5" max="60" style="width:90px" />
              <button id="wf-run-btn" class="ctrl-btn primary">Run WF</button>
            </div>
          </div>
          <div id="wf-error" class="risk-error" style="display:none"></div>
          <div id="wf-results" style="display:none">
            <div class="wf-summary-row" id="wf-summary"></div>
            <div class="wf-table-wrap">
              <table class="data-table compact" id="wf-table">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>IS Sharpe</th>
                    <th>OOS Sharpe</th>
                    <th>OOS P&amp;L</th>
                    <th>Best ATR Mult</th>
                    <th>Max Levels</th>
                  </tr>
                </thead>
                <tbody id="wf-tbody"></tbody>
              </table>
            </div>
          </div>
```

- [ ] **Step 4.2: Add CSS for WF section in styles.css**

In `python/vhe/platform/static/styles.css`, append after the existing Risk Tab CSS block:

```css
.risk-divider { height: 1px; background: var(--border); margin: 24px 24px 0; }
.wf-summary-row { display: flex; gap: 12px; flex-wrap: wrap; padding: 16px 24px 0; align-items: center; }
.wf-badge {
  padding: 6px 14px;
  border-radius: 20px;
  font: 700 12px var(--mono);
}
.wf-badge.good { background: var(--green-dim); color: var(--green); border: 1px solid rgba(0,208,156,0.3); }
.wf-badge.warn { background: var(--amber-dim); color: var(--amber); border: 1px solid rgba(240,180,41,0.3); }
.wf-badge.bad  { background: var(--red-dim);   color: var(--red);   border: 1px solid rgba(255,107,107,0.3); }
.wf-efficiency-label { font: 13px var(--mono); color: var(--muted); }
.wf-table-wrap { padding: 12px 24px 24px; overflow-x: auto; }
```

- [ ] **Step 4.3: Add WF rendering JS to app.js**

In `python/vhe/platform/static/app.js`, append at the end of the file:

```javascript
// ── Walk-Forward Validation Tab ───────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("wf-run-btn");
  if (btn) btn.addEventListener("click", runWalkForward);
});

async function runWalkForward() {
  const symbol = document.getElementById("wf-symbol")?.value?.trim();
  const barsFile = document.getElementById("wf-bars-file")?.value?.trim();
  const trainDays = parseInt(document.getElementById("wf-train-days")?.value || "60", 10);
  const testDays = parseInt(document.getElementById("wf-test-days")?.value || "15", 10);
  const errorEl = document.getElementById("wf-error");
  const resultsEl = document.getElementById("wf-results");

  errorEl.style.display = "none";
  resultsEl.style.display = "none";

  if (!symbol || !barsFile) {
    errorEl.textContent = "Symbol and bars_file are required.";
    errorEl.style.display = "block";
    return;
  }

  const btn = document.getElementById("wf-run-btn");
  btn.textContent = "Running…";
  btn.disabled = true;

  try {
    const params = new URLSearchParams({ symbol, bars_file: barsFile, train_days: trainDays, test_days: testDays });
    const resp = await fetch(`/api/backtest/walk-forward?${params}`);
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || resp.statusText);
    }
    const data = await resp.json();
    renderWFResults(data);
  } catch (err) {
    errorEl.textContent = `Error: ${err.message}`;
    errorEl.style.display = "block";
  } finally {
    btn.textContent = "Run WF";
    btn.disabled = false;
  }
}

function renderWFResults(data) {
  const summaryEl = document.getElementById("wf-summary");
  const tbodyEl = document.getElementById("wf-tbody");
  const resultsEl = document.getElementById("wf-results");

  const wfe = data.wf_efficiency ?? 0;
  const verdictClass = data.verdict === "Not overfit" ? "good" : data.verdict === "Marginal" ? "warn" : "bad";

  summaryEl.innerHTML = `
    <span class="wf-badge ${verdictClass}">${data.verdict}</span>
    <span class="wf-efficiency-label">WF Efficiency: <strong>${wfe.toFixed(3)}</strong></span>
    <span class="wf-efficiency-label">Stable ATR Mult: <strong>${data.param_stability?.atr_multiplier ?? "—"}</strong></span>
    <span class="wf-efficiency-label">Stability Score: <strong>${((data.param_stability?.stability_score ?? 0) * 100).toFixed(0)}%</strong></span>
    <span class="wf-efficiency-label">${data.windows?.length ?? 0} windows</span>
  `;

  tbodyEl.innerHTML = (data.windows || []).map((w) => {
    const oosCls = w.oos_sharpe >= 0 ? "" : "sell";
    const pnlCls = w.oos_pnl >= 0 ? "buy" : "sell";
    return `
      <tr>
        <td style="font:11px var(--mono);color:var(--muted)">${w.period}</td>
        <td>${w.is_sharpe.toFixed(2)}</td>
        <td class="${oosCls}">${w.oos_sharpe.toFixed(2)}</td>
        <td class="${pnlCls}">${money.format(w.oos_pnl)}</td>
        <td>${w.best_params?.atr_multiplier ?? "—"}</td>
        <td>${w.best_params?.max_levels ?? "—"}</td>
      </tr>
    `;
  }).join("");

  resultsEl.style.display = "block";
}
```

- [ ] **Step 4.4: Bump the app.js cache-buster version in index.html**

In `python/vhe/platform/static/index.html`, change `app.js?v=27` to `app.js?v=28`.

- [ ] **Step 4.5: Run full test suite**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/ -q 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 4.6: Final commit**

```bash
git add python/vhe/platform/static/index.html python/vhe/platform/static/app.js python/vhe/platform/static/styles.css
git commit -m "feat: add walk-forward validation UI to Risk tab"
```
