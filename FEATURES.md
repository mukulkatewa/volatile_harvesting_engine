# Planned Features

## Context

The engine already has: Dynamic ATR Grid, Pair Spread, Momentum, Market Regime
Classification, Sentiment Engine, Paper/Live Broker, Event-Driven Backtester,
Risk Guard, FastAPI server, React dashboard, SQLite audit log.

These two features will make it portfolio-complete and technically impressive
for SDE roles without scope creep.

---

## Feature 1 — Monte Carlo Risk Engine

### Why this?

Right now the backtester gives you *one* P&L number. Monte Carlo tells you the
*distribution* of outcomes — how likely is a 5% drawdown? What's the worst-case
loss at 95% confidence? This is how professional risk desks validate strategies,
and it shows statistical + systems thinking to an interviewer.

### What it does

Takes the trade log from any completed backtest run and repeatedly resamples it
(bootstrap / random shuffle) to produce a distribution of possible equity curves.

Outputs:
- P&L distribution histogram (mean, median, 5th/95th percentile)
- Max Drawdown distribution
- Value at Risk (VaR) at 95% and 99%
- Conditional VaR / Expected Shortfall (CVaR)
- Probability of ruin (equity < 50% of starting capital)
- Kelly Criterion position size recommendation

### Where it fits in the codebase

```
vhe/backtest/monte_carlo.py   ← new file, ~200 LOC
vhe/backtest/ledger.py        ← read trade list from here (already exists)
platform/server.py            ← add POST /api/backtest/monte-carlo endpoint
platform/static/              ← add MC results tab to dashboard
```

### Algorithm (bootstrap simulation)

```
input: trades[]  (each trade has pnl, entry_time, exit_time)
       n_sims = 10_000
       initial_capital = 75_000

for i in 1..n_sims:
    shuffled = random.sample(trades, len(trades))   # resample with replacement
    equity_curve = cumsum([initial_capital] + [t.pnl for t in shuffled])
    record: final_equity, max_drawdown, hit_ruin

output:
    VaR_95  = percentile(final_equities, 5)
    CVaR_95 = mean(final_equities where equity < VaR_95)
    drawdown_95 = percentile(max_drawdowns, 95)
    p_ruin  = count(hit_ruin) / n_sims
```

### API

```
POST /api/backtest/monte-carlo
{
  "symbol": "RELIANCE",
  "bars_file": "data/RELIANCE_2025.csv",
  "n_sims": 10000
}

Response:
{
  "var_95": -3200,
  "cvar_95": -4100,
  "p_ruin": 0.02,
  "drawdown_p95": 0.048,
  "kelly_fraction": 0.18,
  "pnl_percentiles": {"p5": -1800, "p50": 2400, "p95": 5100}
}
```

### Effort estimate: ~3–4 days

---

## Feature 2 — Walk-Forward Validation Harness

### Why this?

Any backtest on a fixed historical window can be overfit — the strategy
parameters happen to work on that specific data. Walk-forward validation
repeatedly trains on a rolling window and tests on out-of-sample data. It is
the standard way to prove a strategy isn't curve-fitted, and it is a very
clean systems engineering problem (pipeline, windowing, parallel jobs).

### What it does

Splits historical bar data into rolling Train/Test windows, runs the backtester
on each window, and aggregates out-of-sample performance metrics.

```
Window 1:  [Jan–Mar train] → [Apr test]
Window 2:  [Feb–Apr train] → [May test]
Window 3:  [Mar–May train] → [Jun test]
...
```

Outputs:
- Out-of-sample P&L per window
- Parameter stability report (did optimal ATR multiplier stay stable?)
- In-sample vs out-of-sample Sharpe ratio comparison
- Walk-forward efficiency ratio: OOS_sharpe / IS_sharpe (>0.5 = not overfit)

### Where it fits in the codebase

```
vhe/backtest/walk_forward.py   ← new file, ~250 LOC
vhe/backtest/engine.py         ← reuse EventDrivenBacktester (already exists)
vhe/backtest/optimiser.py      ← new: grid search over atr_multiplier, max_levels
platform/server.py             ← add GET /api/backtest/walk-forward
```

### Algorithm

```
input: bars_df, train_days=60, test_days=15, step_days=15
       param_grid = {atr_multiplier: [0.3, 0.45, 0.6], max_levels: [3, 5]}

windows = rolling_split(bars_df, train_days, test_days, step_days)

for window in windows:
    best_params = grid_search(window.train, param_grid)   # IS optimisation
    oos_result  = backtest(window.test, best_params)       # OOS validation
    record(window.start, best_params, oos_result.sharpe, oos_result.pnl)

wf_efficiency = mean(oos_sharpes) / mean(is_sharpes)
```

### API

```
GET /api/backtest/walk-forward?symbol=RELIANCE&train_days=60&test_days=15

Response:
{
  "windows": [
    {"period": "2025-01 to 2025-03", "is_sharpe": 1.4, "oos_sharpe": 0.9,
     "oos_pnl": 1840, "best_atr_mult": 0.45},
    ...
  ],
  "wf_efficiency": 0.64,
  "param_stability": {"atr_multiplier": 0.45, "stability_score": 0.82}
}
```

### Effort estimate: ~4–5 days

---

## Build order

1. **Monte Carlo first** — standalone, no dependencies on feature 2, and gives
   immediate visual output for the dashboard.
2. **Walk-forward second** — builds on Monte Carlo results to show the full
   validation story: backtest → MC risk → walk-forward proof.

Together these two features complete the full quantitative validation loop:
*strategy → backtest → risk distribution → out-of-sample proof*.
That loop is what separates a toy trading bot from a serious engineering project.
