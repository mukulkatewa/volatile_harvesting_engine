# Volatility Harvesting Engine: Research And Build Plan

Status: project reference v1
Market: Indian equities
Initial scope: intraday NSE cash equities
Default broker: Zerodha Kite Connect
Primary objective: convert volatility into cash with controlled risk

This is not a marketing plan, signal-selling plan, or "guaranteed profit" system. The target is to build a personal trading engine that can be researched, backtested, paper traded, audited, and only then deployed with small capital.

The strategy should not predict direction as its main edge. It should harvest deviations when markets are range-bound, switch off grids when markets trend, use momentum only when trend regime is confirmed, and move to cash during crash conditions.

## 1. Core Thesis

Pure fixed-grid trading is fragile because it assumes mean reversion forever. The engine should instead trade only when the market structure supports mean reversion, widen grid spacing when volatility expands, stop adding exposure after a fixed depth, and maintain reserve capital.

The first defensible version is a hybrid:

- 70% adaptive volatility/grid logic when market regime is range-bound.
- 30% momentum fallback when trend regime is confirmed.
- Cash mode when broad-market crash risk is high.
- Pair-grid research path using cointegrated stock spreads after the single-name intraday engine is stable.

The real edge is not "buy every dip". The edge is filtering when mean reversion is statistically more likely, sizing small enough to survive adverse moves, and refusing to average down infinitely.

## 2. Research Basis

### Dynamic Grid Trading

Research on dynamic grid trading argues that fixed grid spacing has weak expectancy and that adaptive reset rules can improve outcomes. The important takeaway for VHE is not to copy crypto results into Indian equities, but to adopt the robust principles:

- Grid distance should depend on current volatility.
- Grid center should reset when market condition changes.
- Strategy should not run continuously in all regimes.
- Risk control matters more than grid density.

Reference:

- "Dynamic Grid Trading Strategy: From Zero Expectation to Market Outperformance", arXiv, 2025: https://arxiv.org/abs/2506.11921

### Cointegration And Pair Trading

Indian-market pair-trading research supports testing cointegration-based pairs instead of blindly grid-trading individual stocks. Pair trading can reduce directional market exposure because the traded object is the spread, not the raw stock price.

For VHE, this supports a later "adaptive pair grid":

```text
spread = log(A) - beta * log(B)
```

Where `beta` is the hedge ratio estimated from rolling regression.

Reference:

- "Designing Efficient Pair-Trading Strategies Using Cointegration for the Indian Stock Market", arXiv, 2022: https://arxiv.org/abs/2211.07080

### Portfolio And Backtesting Risk

Backtest results can differ materially depending on how fees, slippage, fills, and order mechanics are modeled. VHE must not accept a strategy because it works in a simplistic close-to-close vectorized test. The acceptance gate must be an event-driven test with realistic transaction costs.

Reference:

- "Implementation Risk in Portfolio Backtesting: A Previously Unquantified Source of Error", arXiv, 2026: https://arxiv.org/abs/2603.20319

### Practical Broker And Market Constraints

Zerodha Kite Connect provides REST APIs for orders, historical candles, WebSocket market data, and postbacks/order updates. WebSocket streaming is the preferred live quote channel; order placement only confirms order registration, not execution, so live trading must reconcile fills and order states.

References:

- Kite Connect API docs: https://kite.trade/docs/connect/v3/
- Kite Connect orders: https://kite.trade/docs/connect/v3/orders/
- Kite Connect WebSocket: https://kite.trade/docs/connect/v3/websocket/
- Kite Connect historical candles: https://kite.trade/docs/connect/v3/historical/
- Zerodha charges: https://zerodha.com/charges/

## 3. India Market Constraints

### Initial Instrument Scope

VHE v1 should trade only:

- NSE cash equities.
- NIFTY 100 symbols first.
- Intraday MIS-style positions only.
- No penny stocks.
- No illiquid names.
- No symbols under heavy surveillance, repeated price bands, or abnormal corporate-action windows.

Avoid in v1:

- Overnight short cash-equity pair trades.
- Options grids.
- Futures grids.
- Small-cap and low-liquidity universes.
- News-event chasing.

Reason: Indian retail cash short positions are intraday in normal brokerage workflows. A true overnight market-neutral pair trade needs futures, stock lending, or another structure. That adds margin, expiry, lot-size, and liquidity complexity. The safer first build is intraday cash equities.

### Universe

Default universe:

```text
NIFTY 100 = NIFTY 50 + NIFTY Next 50
```

V1 should use NIFTY 100, not NIFTY 200, because the project needs tight spreads and high turnover more than a large candidate list.

Expansion to NIFTY 200 is allowed only if a symbol passes all liquidity filters:

- Average traded value over 20 sessions is above threshold.
- Median live bid-ask spread is below threshold.
- Sufficient depth exists at top 5 levels.
- No repeated price-band hits.
- No abnormal volume gaps caused by news or corporate events.

### Trading Session Assumptions

Indian cash-equity regular market session:

```text
09:15 to 15:30 IST
```

VHE should avoid opening new positions during unstable periods:

- First 5 to 10 minutes after open.
- Last 20 minutes before close, except exits.
- Major scheduled event windows.
- Symbol-specific news shock windows.

Default forced square-off:

```text
15:10 IST
```

This gives time to reconcile partial fills, cancel open orders, and exit residual positions before broker auto-square-off risk.

## 4. Strategy Design

## 4.1 Daily Scanner

Run every evening after market data is available.

Inputs:

- OHLCV daily bars.
- Intraday OHLCV where available.
- Corporate-action-adjusted prices.
- Live spread/depth snapshots during trading day where available.
- Index data for NIFTY 50, NIFTY 100, and India VIX if available.

Indicators:

- ATR 14.
- ADX 14.
- EMA 20.
- EMA 50.
- Realized volatility 20.
- Volume percentile 20 or 60.
- Turnover percentile 20 or 60.
- Gap percentage.
- Range compression/expansion metrics.

Hard filters:

```text
close > 100
avg_turnover_20d >= configured minimum
median_spread_bps <= configured maximum
avg_volume_20d >= configured minimum
not in banned_symbols
not in active_corporate_action_window
not in repeated_price_band_window
```

Candidate score:

```text
volatility_score = percentile(ATR_14 / close, universe)
trend_penalty = percentile(ADX_14, universe)
range_score = 1 - trend_penalty
volume_score = percentile(avg_turnover_20d, universe)
gap_penalty = min(abs(today_gap_pct) / max_gap_pct, 1)

candidate_score =
    0.40 * volatility_score +
    0.30 * range_score +
    0.20 * volume_score -
    0.10 * gap_penalty
```

Selection:

- Keep top 10 scanner names.
- Trade max 2 to 4 symbols live in v1.
- Prefer symbols with high realized intraday oscillation and low directional trend.
- Exclude symbols with vertical news moves even if ATR is high.

## 4.2 Regime Detection

Regime is computed at two levels:

- Market regime using NIFTY 50/NIFTY 100.
- Symbol regime using each candidate stock.

Grid is allowed only when both market and symbol conditions are acceptable.

Regime rules:

```text
Range:
    ADX_14 < 20
    abs(price - EMA50) <= 3%
    realized_volatility not in crash spike zone
    breadth not collapsing

Trend Up:
    ADX_14 > 25
    EMA20 > EMA50
    price > EMA50

Trend Down:
    ADX_14 > 25
    EMA20 < EMA50
    price < EMA50

Crash:
    index intraday drawdown <= -1.5%
    OR market breadth collapse
    OR India VIX shock
    OR many universe names break previous day low with expanding volume
```

Action map:

```text
Range      -> Adaptive Grid ON
Trend Up   -> Grid OFF, Momentum ON
Trend Down -> Grid OFF, Cash or short-only intraday momentum if explicitly enabled
Crash      -> Cash, cancel all pending grid orders
```

Default v1:

- Enable range grid.
- Enable long-only trend momentum initially.
- Disable short-only momentum until paper tests prove stable.
- Always enable crash cash mode.

## 4.3 Adaptive Single-Stock Grid

Grid should not be centered at current price blindly. Use fair value.

Fair value:

```text
fair_value = EMA50
```

For intraday:

```text
fair_value = EMA50 on 5-minute or 15-minute candles
```

No-buy overextension rule:

```text
if price > fair_value * 1.03:
    no new grid buys
```

Undervaluation/range entry:

```text
allow grid if:
    regime == Range
    price <= fair_value * 1.01
    ADX_14 < 20
    spread_bps <= max_spread_bps
```

Grid spacing:

```text
raw_spacing = 0.35 * ATR_14
min_spacing = max(2 * tick_size, 2 * estimated_roundtrip_cost)
grid_spacing = max(raw_spacing, min_spacing)
```

If using intraday candles, ATR should be computed on the selected timeframe and converted consistently:

```text
ATR_14_5m for 5-minute execution
ATR_14_15m for 15-minute execution
daily ATR for overnight research only
```

Levels:

```text
level_1 = fair_value - 1 * grid_spacing
level_2 = fair_value - 2 * grid_spacing
...
level_5 = fair_value - 5 * grid_spacing
```

V1 maximum:

```text
max_levels = 5
```

Never allow infinite buys. Never use martingale sizing.

Position sizing:

```text
deployable_capital = total_capital * 0.75
reserve_capital = total_capital * 0.25
symbol_capital = min(deployable_capital * 0.10, configured_symbol_cap)
level_capital = symbol_capital / max_levels
quantity = floor(level_capital / level_price)
```

Exit logic:

```text
take_profit = entry_price + grid_spacing
mean_exit = fair_value
time_exit = 15:10 IST
stop_exit = max_adverse_move or regime flip
```

Exit priority:

1. Crash mode exit.
2. Daily loss stop.
3. Symbol stop.
4. Regime flip exit.
5. Time exit.
6. Profit target exit.

## 4.4 Momentum Fallback

Momentum is not the core product, but it prevents the engine from forcing grids during strong trends.

Default long momentum rule:

```text
market_regime == Trend Up
symbol_regime == Trend Up
price > EMA20 > EMA50
ADX_14 > 25
volume > avg_volume_20d
breakout above previous intraday range
```

Entry:

- Use limit order near breakout retest.
- Avoid market orders except emergency exits.
- Do not enter after 14:45 IST in v1.

Exit:

```text
stop = entry - 1.0 * ATR_intraday
target = entry + 1.5 * ATR_intraday
trail = EMA20 or ATR trail
time_exit = 15:10 IST
```

Sizing:

```text
risk_per_trade <= 0.25% of total capital in paper/live v1
```

## 4.5 Adaptive Pair Grid

This is the research-heavy alpha path and should be built after the single-name engine and backtester are stable.

Candidate sectors:

- Banking: HDFC Bank, ICICI Bank, Axis Bank, Kotak Bank.
- Auto: Tata Motors, M&M, Maruti.
- Energy: ONGC, Oil India, BPCL, HPCL.
- Similar sector pairs from NIFTY 100 only.

Pair discovery:

```text
for each sector:
    generate pairs
    run cointegration test on training window
    estimate hedge ratio beta using rolling OLS
    compute spread = log(A) - beta * log(B)
    compute half-life of mean reversion
    keep pairs with stable beta and acceptable half-life
```

Pair filters:

```text
p_value <= 0.05
half_life between 1 and 20 trading days for swing research
intraday spread mean reversion visible for intraday deployment
both legs liquid
both legs have tight spreads
borrow/short constraints handled by intraday square-off
```

Pair-grid signal:

```text
zscore = (spread - rolling_mean) / rolling_std

if zscore >= +1.5:
    short A intraday, long B intraday

if zscore <= -1.5:
    long A intraday, short B intraday

exit near zscore == 0
```

Pair-grid levels:

```text
level_1 = abs(zscore) >= 1.5
level_2 = abs(zscore) >= 2.0
level_3 = abs(zscore) >= 2.5
max_pair_levels = 3 in v1
hard_stop = abs(zscore) >= 3.0
```

Important: pair-grid must be intraday-only in v1 because one leg may be short. Overnight pair trading requires F&O or other structures and is out of initial live scope.

## 5. Risk Management

Risk management is part of the strategy, not an optional wrapper.

Capital buckets:

```text
total_capital = 100%
grid_bucket = 50%
momentum_bucket = 25%
reserve_bucket = 25%
```

For initial live deployment:

```text
live_capital_cap = INR 25,000
reserve_capital >= 25%
max_symbols = 2
max_open_orders_per_symbol = 5
max_grid_levels_per_symbol = 5
```

Portfolio limits:

```text
max_daily_loss = 1.0% of live capital
max_symbol_loss = 0.5% of live capital
max_strategy_loss = 0.75% of live capital
max_gross_exposure = 75% of capital
max_single_symbol_exposure = 10% of deployable capital
```

Kill switch triggers:

- Broker API disconnect while orders are open.
- WebSocket stale quote beyond configured seconds.
- Repeated rejected orders.
- Fill reconciliation mismatch.
- Daily loss limit hit.
- Exchange/broker abnormal behavior.
- Market regime flips to crash.

Order safety:

- Prefer limit orders for entries.
- Use market orders only for emergency exits or forced square-off.
- Every order must have a client tag and strategy ID.
- Every fill must reconcile to an internal position.
- Duplicate order prevention must be enforced by idempotency key.

## 6. Backtesting Specification

Backtesting must happen in stages.

### Stage 1: Indicator Correctness

Test ATR, ADX, EMA, z-score, hedge ratio, and volatility percentile against known outputs.

Acceptance:

- No lookahead.
- Indicators only use data available at that timestamp.
- Daily scanner uses previous close data for next-day candidate list.

### Stage 2: Vectorized Research

Use Python for fast parameter exploration.

Recommended tools:

- pandas.
- numpy.
- polars where useful.
- numba for heavy loops.
- vectorbt for quick portfolio and parameter sweeps.
- statsmodels for regression and cointegration.
- scipy/sklearn for stats and validation.

Use this only for discovery, not final approval.

### Stage 3: Event-Driven Backtest

Build a custom event-driven simulator because grid trading is path-dependent.

Simulator must model:

- Limit order placement.
- Partial fills.
- Bid-ask spread.
- Slippage.
- Brokerage.
- STT.
- Exchange transaction charges.
- GST.
- SEBI charges.
- Stamp duty.
- Intraday square-off.
- Rejected orders.
- Latency assumptions.
- Order cancellation and replacement.

Minimum fill model:

```text
buy limit fills if low <= limit_price
sell limit fills if high >= limit_price
fill_price includes configured slippage
partial_fill_ratio depends on candle volume and order size
```

More conservative fill model:

```text
buy limit fills only if low < limit_price - spread_buffer
sell limit fills only if high > limit_price + spread_buffer
```

### Stage 4: Walk-Forward Validation

Do not optimize once on all data.

Use rolling windows:

```text
train: 12 months
validate: 3 months
test: next 3 months
roll forward
```

For each window:

- Select symbols using only prior data.
- Select pairs using only prior data.
- Fit beta using only prior data.
- Optimize parameters only on train/validation.
- Report performance only on test.

Market periods to explicitly inspect:

- 2019 normal market.
- 2020 COVID crash and recovery.
- 2021 liquidity rally.
- 2022 drawdown/high inflation period.
- 2023 range/trend mix.
- 2024-2026 current market regimes where data is available.

### Stage 5: Robustness And Stress Tests

Required tests:

- Double slippage.
- Double brokerage/cost approximation.
- Missed fill simulation.
- Delayed entry by 1 candle.
- Delayed exit by 1 candle.
- Random order rejection.
- WebSocket stale data simulation.
- Top candidate removed.
- Worst 10 trading days isolated.
- Parameter perturbation around best settings.

Acceptance:

- Strategy must not depend on one exact parameter.
- Strategy must remain acceptable after conservative costs.
- Max drawdown must stay under configured cap.
- Profit factor and Sharpe should not collapse under small perturbations.

### Metrics

Report every run with:

- CAGR where relevant.
- Absolute PnL.
- Daily PnL distribution.
- Max drawdown.
- Calmar ratio.
- Sharpe ratio.
- Sortino ratio.
- Win rate.
- Average win.
- Average loss.
- Profit factor.
- Expectancy per trade.
- Turnover.
- Cost as percent of gross profit.
- Slippage impact.
- Exposure time.
- Worst day.
- Worst symbol.
- Regime-wise performance.

## 7. Data Plan

Chosen assumption: free-first data.

This means:

- Start with NSE public reports/bhavcopy for daily OHLCV.
- Use Zerodha historical candles where available for authenticated research.
- Use live collected Zerodha WebSocket data to build your own intraday database.
- Later buy clean intraday historical data if free data is insufficient.

Data sources:

- NSE public historical reports and security-wise archives.
- NSE index historical data.
- Zerodha instrument master.
- Zerodha historical candle API.
- Zerodha WebSocket live ticks/quotes.
- Optional future vendor: TrueData, Global Datafeeds, or another licensed Indian market data vendor.

Storage layout:

```text
data/
  raw/
    nse_bhavcopy/
    kite_historical/
    kite_ticks/
  processed/
    ohlcv_1d/
    ohlcv_1m/
    ohlcv_5m/
    indicators/
  research/
    scans/
    backtests/
    reports/
```

Preferred file format:

```text
Parquet partitioned by source/timeframe/symbol/date
```

Research query engine:

```text
DuckDB
```

Live state DB:

```text
PostgreSQL or SQLite for v1 paper mode
PostgreSQL/TimescaleDB when running full live observability
```

Data quality checks:

- Missing dates.
- Missing candles.
- Duplicate bars.
- OHLC consistency.
- Corporate actions.
- Symbol changes.
- Sudden split-like jumps.
- Zero-volume candles.
- Invalid high/low ranges.
- Outlier spread/depth snapshots.

## 8. System Architecture

```text
Market Data
    |
    v
Data Normalizer
    |
    v
Daily Scanner
    |
    v
Indicator Engine
    |
    v
Regime Detector
    |
    +---- Range -----> Adaptive Grid Engine
    |
    +---- Trend -----> Momentum Engine
    |
    +---- Crash -----> Cash / Kill Switch
    |
    v
Risk Engine
    |
    v
Order Router
    |
    v
Broker Adapter
    |
    v
Audit Log + Dashboard
```

Core services:

- `data-ingestor`: downloads/records market data.
- `scanner`: creates watchlists.
- `research-backtester`: runs vectorized and event-driven tests.
- `strategy-engine`: generates intents.
- `risk-engine`: approves, rejects, resizes, or kills intents.
- `execution-engine`: places, modifies, cancels, and reconciles orders.
- `paper-broker`: simulates live execution from real quotes.
- `dashboard`: shows positions, PnL, regime, orders, and kill switch state.

Important design rule:

```text
strategy generates intent
risk engine approves intent
execution engine sends broker order
broker fills update position
strategy never mutates positions directly
```

## 9. Tech Stack

Chosen stack: hybrid now.

### Python Research Layer

Use Python because the research workflow needs fast iteration and strong quant libraries.

Core:

- Python 3.12+.
- pandas.
- numpy.
- polars.
- duckdb.
- pyarrow.
- numba.
- scipy.
- statsmodels.
- scikit-learn.
- vectorbt for early parameter sweeps.
- matplotlib/plotly for reports.

Responsibilities:

- Data ingestion scripts.
- Indicator calculation.
- Candidate scanner.
- Cointegration tests.
- Parameter sweeps.
- Walk-forward backtesting.
- Report generation.

### Rust Live Layer

Use Rust for live execution because runtime safety and predictable behavior matter more than research convenience once money is involved.

Core crates:

- tokio for async runtime.
- reqwest for REST.
- tokio-tungstenite for WebSocket.
- serde for JSON.
- sqlx for DB.
- tracing for logs.
- chrono/time for timestamps.
- rust_decimal for money values.
- clap for CLI.

Responsibilities:

- Kite WebSocket quote ingestion.
- Order router.
- Risk engine.
- Position reconciliation.
- Kill switch.
- Audit logging.
- Paper/live mode execution parity.

### Interface Between Python And Rust

Use config and database boundaries, not direct language embedding in v1.

```text
Python writes:
    candidate lists
    strategy configs
    indicator snapshots
    research reports

Rust reads:
    approved universe
    risk config
    strategy parameters
    latest scanner output

Rust writes:
    live quotes
    orders
    fills
    positions
    risk events
    PnL snapshots
```

This keeps live trading deterministic and research flexible.

### Suggested Repository Structure

```text
volatile_harvesting_engine/
  docs/
    VHE_RESEARCH_AND_BUILD_PLAN.md
  configs/
    scanner.yaml
    backtest_grid_intraday.yaml
    backtest_pair_grid.yaml
    live_paper.yaml
    live_live.yaml
  python/
    vhe/
      data/
      indicators/
      scanner/
      backtest/
      pairs/
      reports/
    tests/
  rust/
    crates/
      vhe-live/
      vhe-core/
      vhe-kite/
      vhe-risk/
  data/
    raw/
    processed/
  reports/
  scripts/
```

## 10. APIs And Commands

Python CLI:

```text
vhe data ingest-nse --from 2019-01-01 --to 2026-06-14
vhe data ingest-kite --symbols configs/universe_nifty100.yaml --timeframe 5m
vhe scan daily --date YYYY-MM-DD --universe nifty100
vhe backtest grid --config configs/backtest_grid_intraday.yaml
vhe backtest pair-grid --config configs/backtest_pair_grid.yaml
vhe report --run-id RUN_ID
```

Rust live CLI:

```text
vhe-live --mode paper --config configs/live_paper.yaml
vhe-live --mode live --capital-cap 25000 --config configs/live_live.yaml
vhe-live kill-switch --reason "manual stop"
vhe-live reconcile --date YYYY-MM-DD
```

Strategy intent schema:

```json
{
  "strategy_id": "grid_intraday_v1",
  "symbol": "TATAMOTORS",
  "side": "BUY",
  "order_type": "LIMIT",
  "price": 950.25,
  "quantity": 10,
  "reason": "range_grid_level_2",
  "max_loss": 125.0,
  "expires_at": "2026-06-14T15:10:00+05:30"
}
```

Risk decision schema:

```json
{
  "intent_id": "uuid",
  "approved": true,
  "final_quantity": 10,
  "risk_checks": [
    "capital_ok",
    "spread_ok",
    "daily_loss_ok",
    "regime_ok"
  ]
}
```

## 11. Build Roadmap

### Phase 0: Repo Bootstrap

Deliverables:

- Project structure.
- Python package skeleton.
- Rust workspace skeleton.
- Config files.
- Basic documentation.
- Makefile or task runner.

Acceptance:

- `python -m pytest` runs.
- `cargo test` runs.
- Example config loads.

### Phase 1: Data Foundation

Deliverables:

- NSE daily bhavcopy downloader/parser.
- Zerodha instrument master loader.
- Symbol master.
- NIFTY 100 universe loader.
- Parquet writer.
- Data quality reports.

Acceptance:

- Can build adjusted daily OHLCV dataset.
- Can query a symbol's full daily history.
- Can detect missing/invalid bars.

### Phase 2: Indicators And Scanner

Deliverables:

- ATR 14.
- ADX 14.
- EMA 20/50.
- Volume/turnover percentiles.
- Candidate scoring.
- Daily scanner report.

Acceptance:

- Scanner produces ranked candidate list.
- No future data leakage.
- Indicators have unit tests.

### Phase 3: Backtesting Engine

Deliverables:

- Vectorized quick research backtester.
- Event-driven grid backtester.
- Cost model.
- Slippage model.
- Walk-forward runner.
- HTML/Markdown report.

Acceptance:

- Can backtest 2019-2026 daily where data exists.
- Can backtest intraday where clean intraday data exists.
- Reports include regime-wise PnL and transaction-cost impact.

### Phase 4: Strategy Engines

Deliverables:

- Adaptive grid engine.
- Momentum fallback engine.
- Pair discovery engine.
- Pair-grid research engine.
- Risk rules.

Acceptance:

- Strategies produce deterministic intents from historical bars.
- Risk engine can reject unsafe intents.
- Backtest and paper-trading logic share strategy rules.

### Phase 5: Paper Trading

Deliverables:

- Kite WebSocket quote ingestion.
- Paper broker.
- Order simulation.
- Position reconciliation.
- Dashboard/log report.

Acceptance:

- 30 trading days paper-only.
- Fill simulation compared against live quotes.
- No unreconciled positions.
- Kill switch tested.

### Phase 6: Limited Live

Deliverables:

- Zerodha order router.
- Live risk engine.
- Emergency exit.
- End-of-day reconciliation.
- Daily report.

Acceptance:

- Capital cap: INR 25,000.
- Max symbols: 2.
- Manual kill switch works.
- No capital increase until 30 live days are reviewed.

## 12. Testing Matrix

### Unit Tests

- ATR calculation.
- ADX calculation.
- EMA calculation.
- Candidate score.
- Regime classification.
- Grid level generation.
- Capital allocation.
- Risk limit rejection.
- Pair spread/z-score.
- Hedge ratio estimation.

### Integration Tests

- Load raw data and write Parquet.
- Run scanner from stored data.
- Run one backtest from config.
- Generate report.
- Paper broker consumes quote stream.
- Risk engine rejects oversized order.
- Execution engine reconciles partial fills.

### Simulation Tests

- Broker disconnect.
- WebSocket stale data.
- Duplicate order intent.
- Order rejected.
- Partial fill then cancel.
- Crash regime flip.
- End-of-day forced exit.
- Daily loss limit.

### Acceptance Tests Before Real Money

All must pass:

- At least 30 trading days of paper trading.
- No unresolved order/position reconciliation errors.
- Backtest profitable after realistic costs.
- Conservative slippage test still acceptable.
- Walk-forward results stable across regimes.
- Daily loss stop validated.
- Manual kill switch validated.
- Live capital cap enforced in code.

## 13. Live Deployment Rules

Never deploy full capital first.

Initial live:

```text
capital = INR 25,000
max_symbols = 2
max_open_positions = 2
max_grid_levels = 5
reserve >= 25%
mode = live only after paper mode passes
```

Daily live process:

1. Run scanner after previous close.
2. Review generated watchlist.
3. Start paper/live engine before market open.
4. No new entries in first 5 to 10 minutes.
5. Monitor risk dashboard.
6. Force exits by 15:10 IST.
7. Reconcile orders/fills.
8. Generate daily report.
9. Disable next-day trading if reconciliation fails.

Capital scale-up rule:

```text
Only increase capital after:
    30 live trading days
    positive net expectancy
    no critical execution errors
    drawdown below threshold
    manual review of worst trades
```

## 14. Open Risks

This project can still fail even if implemented correctly.

Main risks:

- Regime detector misclassifies trend as range.
- Intraday spread and slippage destroy grid edge.
- Backtest fill assumptions are too optimistic.
- Free data quality is insufficient for serious intraday testing.
- Pair relationships break during sector news.
- Zerodha/API connectivity fails during volatile periods.
- Small capital makes brokerage/cost drag proportionally large.
- Over-optimization creates fake edge.

Risk response:

- Use conservative costs.
- Use small capital.
- Use hard max levels.
- Use daily loss stop.
- Keep reserve capital.
- Paper trade first.
- Review worst-case trades, not only averages.

## 15. Immediate Next Implementation Steps

After this document, build in this order:

1. Create repo skeleton for Python and Rust.
2. Implement data ingestion and symbol master.
3. Implement indicators with tests.
4. Implement daily scanner and candidate report.
5. Implement event-driven backtester.
6. Implement adaptive grid backtest.
7. Add cost/slippage model.
8. Add paper broker.
9. Add Rust live shell with risk engine and kill switch.
10. Integrate Kite only after research path is testable.

Do not start with live trading. Do not start with UI. Do not start with options. The first objective is a trustworthy research and backtesting pipeline.

