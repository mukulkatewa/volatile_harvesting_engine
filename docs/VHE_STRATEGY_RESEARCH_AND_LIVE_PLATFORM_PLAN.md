# VHE Strategy Research & Live Platform Overhaul Plan

**Status:** Senior quant research + implementation blueprint  
**Date:** 2026-06-15  
**Market:** NSE cash equities (intraday MIS)  
**Broker:** Zerodha Kite Connect  
**Capital target (v1):** ₹25,000–₹1,00,000 personal account  

This document is written from the perspective of what a senior quant at a prop/HFT desk would actually recommend for **retail-scale systematic trading in India** — not what Instagram “algo traders” claim, and not what Jane Street does with co-located FPGA parsers.

It supersedes the tactical ordering in `VHE_RESEARCH_AND_BUILD_PLAN.md` by prioritizing **live platform infrastructure first**, then layering validated strategies on top. The existing codebase is a good research prototype; this plan describes the overhaul required to trade real money safely.

---

## Implementation Progress

| Phase | Status | Completed |
|-------|--------|-----------|
| **0 — Foundation** | ✅ Complete | 2026-06-15 |
| 1 — Live Market Data | 🔜 Next | — |
| 2 — Order Execution | Pending | — |
| 3 — Strategy Live Wiring | Pending | — |
| 4 — Pair Discovery | Pending | — |
| 5 — Live Micro-Capital | Pending | — |
| 6 — Walk-Forward Backtest | Parallel | — |

### Phase 0 deliverables (shipped)

- `config/loader.py` — loads `live_paper.yaml` + `strategies.yaml` at runtime
- `execution/capital.py` — bucket allocator (grid 50% / pair 25% / momentum 15% / reserve 10%)
- `platform/services/` — `IndicatorService`, `RegimeService`, `StrategyOrchestrator`
- `platform/runtime.py` — `PlatformRuntime` replaces god-object `server.py` logic
- `storage/db.py` — SQLite audit log + fill persistence
- `server.py` refactored to thin FastAPI control plane
- Trading terminal UI — dark Zerodha-style layout, capital bars, regime pills, IST clock, panel navigation
- 43 tests passing (config, capital, indicators, storage, platform)

**Still open from Phase 0:** full position restore on restart (fills/events persist; paper positions reset on boot — acceptable for v0).

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Reality Check: HFT vs What We Can Actually Do in India](#2-reality-check-hft-vs-what-we-can-actually-do-in-india)
3. [What Top Firms and YC-Style Startups Actually Trade](#3-what-top-firms-and-yc-style-startups-actually-trade)
4. [Academic & Empirical Research Synthesis](#4-academic--empirical-research-synthesis)
5. [Our Strategy Stack (Ranked by Edge + Feasibility)](#5-our-strategy-stack-ranked-by-edge--feasibility)
6. [Strategy Specifications (Math + Rules)](#6-strategy-specifications-math--rules)
7. [Capital Allocation Model](#7-capital-allocation-model)
8. [Current Codebase Assessment](#8-current-codebase-assessment)
9. [Target Architecture (Live-First Overhaul)](#9-target-architecture-live-first-overhaul)
10. [Phased Implementation Plan](#10-phased-implementation-plan)
11. [Go-Live Checklist (Non-Negotiable)](#11-go-live-checklist-non-negotiable)
12. [What We Are NOT Building (Scope Guard)](#12-what-we-are-not-building-scope-guard)
13. [References](#13-references)

---

## 1. Executive Summary

### The thesis

**Edge in retail Indian equities does not come from speed.** It comes from:

1. **Regime filtering** — only harvest volatility when mean reversion is structurally likely.
2. **Volatility-adaptive sizing** — grid spacing and position size tied to ATR, not fixed rupee ladders.
3. **Hard capital ceilings** — finite grid depth, reserve bucket, daily loss kill switch.
4. **Market-neutral pair spreads** — trade the residual, not directional beta.
5. **Execution discipline** — limit orders, reconciliation, EOD square-off, no martingale.

### What we are building

A **personal systematic trading platform** that:

- Ingests live NSE quotes via Zerodha Kite WebSocket
- Runs 2–3 concurrent strategy sleeves on a small capital base
- Routes orders through a risk-gated execution layer with full audit trail
- Squares off all positions by 15:10 IST
- Starts with **minimum live capital** (₹25k) and scales only after 60+ live/paper-parity sessions

### Strategy allocation (v1 live)

| Sleeve | Capital | When active | Expected role |
|--------|---------|-------------|---------------|
| Adaptive ATR Grid | 50% | RANGE regime, scanner-approved symbols | Primary PnL driver |
| Pair Spread (z-score) | 25% | Cointegrated pairs, intraday only | Market-neutral alpha |
| Momentum fallback | 15% | TREND_UP confirmed | Trend capture when grid is off |
| Reserve (cash) | 10% | Always | Drawdown buffer + margin headroom |

### Critical insight from research

> **Fixed grid trading has ~zero expected value after fees under naive assumptions** (Chen et al., 2025). Profitability requires dynamic reset, regime gating, and finite depth — which is exactly what VHE's `DynamicGridStrategy` attempts. Do not deploy without these guards.

---

## 2. Reality Check: HFT vs What We Can Actually Do in India

### What true HFT firms do (not available to us)

| Capability | HFT Desk | Retail VHE |
|------------|----------|--------------|
| Co-location at NSE/BSE | Yes (microseconds) | No (milliseconds via internet) |
| Direct exchange feed (ITCH/FIX) | Yes | No (broker API only) |
| Order rate | 1000s/sec | Zerodha: **3 orders/sec** individual |
| Market making with inventory skew | Avellaneda-Stoikov at microsecond scale | Not viable at our latency |
| Cross-exchange latency arb (NSE vs BSE) | Yes | Theoretical only; fees eat edge |
| FPGA/kernel-bypass networking | Standard | Not applicable |

**Zerodha's own documentation** states that internet-based trading is hundreds of times slower than co-located HFT. Less than 0.05% of Zerodha customers use APIs at all.

### What SEBI allows for retail (2026 framework)

- Personal API trading via Kite Connect: **legal, no exchange algo registration** if <10 orders/second
- Zerodha rate limit: 3 orders/sec — well within exemption
- All algos used commercially (selling signals, managing client money) require exchange approval + algo-ID
- **We are building for personal account only** — simpler compliance path

### Our realistic latency budget

```
Kite WebSocket tick → Python/Rust parser → Strategy → Risk → REST order → Exchange
         ~50-200ms total round-trip (internet, not co-lo)
```

This means our strategies must be profitable at **5-minute to intraday horizons**, not tick-level market making. That is a feature, not a bug — it filters out competition from true HFT.

### Honest expected performance range

Based on Indian pair-trading research (QuantInsti EPAT, 2015–2025):

- Cointegrated pair strategies: **~34% annualized** in academic backtests with ₹5L/pair, but with significant drawdown periods
- Win rate ~63% on fixed z-score thresholds
- **After realistic slippage + MIS costs, expect 15–25% annualized** on a well-filtered portfolio — not 100%+

Grid strategies on single names are **higher variance**. Treat grid as the primary harvester but size conservatively.

---

## 3. What Top Firms and YC-Style Startups Actually Trade

### Tier 1: Prop/HFT desks (Jane Street, Citadel, HRT, Optiver)

**Strategies they run that we can learn from (but not replicate):**

| Strategy | Core mechanism | VHE adaptation |
|----------|----------------|----------------|
| Statistical arbitrage | Cointegrated pairs, Kalman hedge ratios, z-score | ✅ Pair spread module — add rolling OLS + discovery |
| Market making | Avellaneda-Stoikov reservation price + inventory skew | ❌ Latency-dependent; skip for v1 |
| Momentum / factor | Cross-sectional ranking, regime detection | ✅ Momentum fallback with ADX/EMA gate |
| Volatility harvesting | Short-vol / grid-like mean reversion in range | ✅ Adaptive ATR grid — our core product |
| Latency arbitrage | Cross-venue price diff | ❌ Not viable retail India |

**Architecture patterns worth stealing:**

1. **Intent → Risk → Execution** separation (already in VHE design)
2. **Order state machine** with reconciliation (missing in VHE today)
3. **Kill switch** on feed staleness, daily loss, reconciliation mismatch
4. **Deterministic replay** — same code path for backtest and live
5. **Pre-trade risk inline** — no order leaves without capital/spread/regime checks

### Tier 2: Quant startups / systematic funds (Two Sigma style, smaller)

- Multi-strategy portfolio with **correlation-aware capital allocation**
- Walk-forward validation before any parameter goes live
- **OU process fitting** for half-life and mean-reversion speed
- Regime detection (HMM or rule-based ADX/VIX gates)
- Kelly-fraction or fixed-fraction position sizing, never full Kelly

### Tier 3: India retail algo platforms (Tradetron, Streak, AlgoTest)

- Signal + execution separation
- Paper trading with broker-parity fills
- MIS intraday product focus
- Strategy marketplace (not our goal — personal engine only)
- **Lesson:** They succeed on UX + reliability, not exotic alpha. Our edge is custom strategy logic + full control.

### What YC fintech/trading startups typically build

YC-backed trading infra companies (e.g. Alpaca-style brokers, QuantConnect-style platforms) focus on:

1. **API-first broker connectivity** — we have Kite Connect
2. **Paper/live parity** — VHE paper broker exists but needs fill model alignment
3. **Audit and compliance logs** — VHE needs persistent storage
4. **Simple strategy DSL or Python SDK** — we have Python strategies already

They do **not** typically ship proprietary alpha. Alpha is the user's job. Our job is the **execution and risk platform**.

---

## 4. Academic & Empirical Research Synthesis

### 4.1 Dynamic Grid Trading (Chen, Chen, Jang — arXiv:2506.11921, 2025)

**Finding:** Traditional bounded grid ≈ zero expected value. Dynamic Grid Trading (DGT) that resets when price breaches boundaries outperforms static grid and buy-and-hold on BTC/ETH (2021–2024).

**VHE implication:**
- ✅ Already implemented: `DynamicGridStrategy._reset_reason()` on fair-value shift
- ⚠️ Missing: upper-bound reset logic, profit reinvestment tracking
- ⚠️ Crypto results ≠ NSE equities — must validate on NIFTY 100 5m data
- **Non-negotiable:** Never run grid without regime gate (ADX < 20)

### 4.2 Grid spacing and ATR (Wilder ATR + MDPI 2025 HF grid paper)

**Finding:** Grid interval should be calibrated to characteristic oscillation amplitude. ATR(14) × 0.35–0.50 is literature-standard. Spacing must exceed round-trip transaction costs.

**VHE implication:**
```text
grid_spacing = max(0.35 × ATR_14, 2 × tick_size, 2 × round_trip_cost_inr)
```

Current code uses `max(atr * 0.35, 0.05)` — the ₹0.05 floor is too low for ₹500+ stocks. Fix: compute min_spacing from actual cost model.

### 4.3 QuantPedia grid primer — intraday reset discipline

**Finding:** Grid profits require **intraday oscillation**, not intraday trend. Multi-day losing streaks occur when price trends within the session. Daily reset (square-off) is mandatory for intraday MIS.

**VHE implication:** 15:10 IST forced exit is correct. Do not carry grid inventory overnight in v1.

### 4.4 Cointegration pair trading — Indian market (arXiv:2211.07080; QuantInsti EPAT 2015–2025)

**Finding:** Sector-clustered pairs on NSE large-caps show tradeable cointegration. Engle-Granger + ADF with Benjamini-Hochberg FDR control reduces false positives.

**Validated pairs from EPAT research:**
- HDFCBANK vs KOTAKBANK
- HEROMOTOCO vs ULTRACEMCO (sector mismatch — treat cautiously)
- HCLTECH vs ICICIBANK

**Execution rules that worked:**
- Entry: |z| > 1.5
- Exit: z crosses 0 (or |z| < 0.5)
- Stop: |z| > 3.0
- Costs: 5 bps per leg per side minimum
- **One-day signal lag** to avoid look-ahead

**VHE implication:** Replace hardcoded RELIANCE/HDFCBANK demo with discovered pairs. Add FDR-controlled universe scan.

### 4.5 Implementation risk in backtesting (arXiv:2603.20319, 2026)

**Finding:** Vectorized backtests overstate returns vs event-driven simulation with realistic fills.

**VHE implication:** `backtest/engine.py` event-driven path is correct architecture. Do not trust scanner scores until walk-forward validated. Live platform first, but **do not scale capital** without 60-day paper parity.

### 4.6 Regime switching and momentum (Wood et al. 2021; Li 2016)

**Finding:** Mean reversion strategies fail in trend regimes. Momentum fails at changepoints. Explicit regime detection is not optional.

**VHE implication:** Wire `RegimeDetector` into live loop. Remove `_simulated_regime()` hack in `server.py`.

---

## 5. Our Strategy Stack (Ranked by Edge + Feasibility)

### Priority 1: Adaptive ATR Grid (single-name, intraday)

**Why first:** Already 80% coded. Highest trade frequency. Works in India's high-intraday-volatility large-caps (Tata Motors, Reliance, HDFC Bank on range days).

**Edge source:** Short-term overreaction mean reversion within session, gated by ADX.

**Failure modes:**
- Trend day → multiple losing grid levels → **regime gate prevents this**
- Gap open → stale fair value → **no trade first 10 min rule**
- Low liquidity → wide spread → **spread_bps filter**

### Priority 2: Pair Spread (z-score, intraday market-neutral)

**Why second:** Lower directional risk. Academic support on NSE. Complements grid (grid is long-biased; pairs can short one leg intraday).

**Edge source:** Cointegrated spread mean reversion.

**Failure modes:**
- Cointegration breakdown → **rolling re-test weekly, hard stop z=3**
- Leg execution asymmetry → **atomic batch with timeout cancel**
- One leg fails → **failed-leg cleanup protocol**

### Priority 3: Momentum Fallback (trend sleeve)

**Why third:** Lower win rate, higher payoff asymmetry. Only armed in TREND_UP. Prevents "grid in a trend" losses.

**Edge source:** Short-term continuation after EMA stack + breakout confirmation.

**Failure modes:** Whipsaw at trend end → time exit + ATR stop.

### Not in v1: Options vol selling, futures grid, overnight pairs, ML signals

---

## 6. Strategy Specifications (Math + Rules)

### 6.1 Daily Scanner (evening batch)

**Universe:** NIFTY 100  
**Run time:** After 18:00 IST (post bhavcopy availability)

**Hard filters:**
```text
close > ₹100
avg_turnover_20d >= ₹5 Cr/day
median_spread_bps <= 15 bps (from live samples)
not in surveillance/ban list
no active corporate action window
```

**Score (same as current `scanner/daily.py`):**
```text
score = 0.40 × ATR%_percentile
      + 0.30 × (1 - ADX_percentile)
      + 0.20 × turnover_percentile
      - 0.10 × gap_penalty
```

**Output:** Top 10 candidates → human or auto-select top 2–4 for next session.

### 6.2 Regime Detector

**Inputs per symbol + market index (NIFTY 50):**

```text
RANGE:       ADX_14 < 20 AND |price - EMA50| / EMA50 <= 3%
TREND_UP:    ADX_14 > 25 AND EMA20 > EMA50 AND price > EMA50
TREND_DOWN:  ADX_14 > 25 AND EMA20 < EMA50 AND price < EMA50
CRASH:       NIFTY50 intraday DD <= -1.5% OR VIX spike > 20% daily
```

**Action map:**
```text
RANGE      → Grid ON,  Pair ON,  Momentum OFF
TREND_UP   → Grid OFF, Pair ON*, Momentum ON  (*pair entries only if spread z extreme)
TREND_DOWN → Grid OFF, Pair ON*, Momentum OFF (v1: no short momentum)
CRASH      → ALL OFF, cancel pending, flatten
```

**Implementation target:** Replace `server.py:_simulated_regime()` with `RegimeDetector` fed by rolling 5m candles.

### 6.3 Adaptive ATR Grid — full spec

**Fair value:**
```text
fair_value = EMA_50 on 5-minute bars (intraday)
```

**Spacing:**
```text
raw_spacing = 0.35 × ATR_14(5m)
min_spacing = max(2 × tick_size, 2 × estimated_roundtrip_cost / avg_qty)
grid_spacing = max(raw_spacing, min_spacing)
```

**Buy levels (max 5):**
```text
level_n = fair_value - n × grid_spacing   for n = 1..5
```

**Entry conditions (ALL must be true):**
```text
regime == RANGE
market_regime != CRASH
price <= fair_value × 1.01
price > fair_value × 0.97  (not too far below — avoid falling knife)
time between 09:25 and 14:45 IST
spread_bps <= 15
no existing position at this level
```

**Exit conditions (priority order):**
```text
1. CRASH regime → market exit all
2. Daily loss limit hit → flatten
3. |z| of position PnL vs ATR stop → exit level
4. Regime → TREND_DOWN/TREND_UP → no new buys; exit at fair_value
5. price >= fair_value → mean reversion exit (limit)
6. time >= 15:10 IST → forced square-off
```

**Dynamic reset (from DGT paper):**
```text
if |fair_value - last_grid_center| >= grid_spacing:
    cancel stale limit orders
    recompute all levels from new fair_value
    log reset_reason = "fair_value_shift"
```

**Current code gap:** `orders_from_plan()` fires when `ltp <= price` — live needs **resting limit orders** at levels, not tick-triggered market simulation.

### 6.4 Pair Spread — full spec

**Spread definition:**
```text
spread_t = log(P_A) - β × log(P_B)
β = OLS hedge ratio on 60-day rolling window (re-fit weekly)
```

**Z-score:**
```text
μ_t = rolling_mean(spread, window=60 bars of 5m)
σ_t = rolling_std(spread, window=60 bars)
z_t = (spread_t - μ_{t-1}) / σ_{t-1}   # one-bar lag, no look-ahead
```

**Entry:**
```text
|z| >= 1.5 AND |z| < 3.0 AND regime != CRASH AND no open pair
z > 0 → SHORT A, LONG B
z < 0 → LONG A, SHORT B
```

**Scaled entry (pair grid — phase 2):**
```text
level 1: |z| >= 1.5 → 33% of pair capital
level 2: |z| >= 2.0 → 33% of pair capital
level 3: |z| >= 2.5 → 34% of pair capital
```

**Exit:**
```text
|z| <= 0.25 → mean reversion exit (both legs)
|z| >= 3.0  → hard stop (both legs)
time >= 15:10 → forced exit
leg failure timeout 30s → cancel unfilled, flatten filled leg
```

**Pair discovery pipeline (new module):**
```text
1. Sector cluster (GICS or NSE industry)
2. Correlation filter: |ρ| > 0.70 on 120d returns
3. Engle-Granger cointegration: p < 0.05
4. Benjamini-Hochberg FDR at 5% across all pairs
5. Half-life filter: 1 < HL < 20 trading days
6. Liquidity filter: both legs pass scanner hard filters
7. Output: ranked pair list with β, μ, σ, half_life, p_value
```

### 6.5 Momentum Fallback — full spec

**Arm conditions:**
```text
regime == TREND_UP (symbol AND market)
price > EMA20 > EMA50
ADX > 25
volume_today > 0.8 × avg_volume_20d
time < 14:45 IST
```

**Entry:** Limit buy at breakout retest or EMA20 touch  
**Stop:** entry - 1.0 × ATR_14(5m)  
**Target:** entry + 1.5 × ATR_14(5m)  
**Size:** risk_inr = 0.25% × total_capital; qty = floor(risk_inr / (entry - stop))

---

## 7. Capital Allocation Model

### 7.1 Bucket structure

```text
total_capital = account_equity (live) or configured cap (paper)

reserve_bucket     = 10%  → never deployed, margin buffer
grid_bucket        = 50%  → split across max 2 symbols
pair_bucket        = 25%  → split across max 1 active pair (2 legs)
momentum_bucket    = 15%  → max 1 position

deployable = total_capital - reserve_bucket
```

### 7.2 Per-symbol grid allocation

```text
symbol_capital = min(grid_bucket / n_active_symbols, deployable × 0.10)
level_capital  = symbol_capital / max_levels   # max_levels = 5
quantity_n     = floor(level_capital / level_price)
```

### 7.3 Per-pair allocation

```text
pair_capital = pair_bucket
leg_capital  = pair_capital / 2
qty_A = floor(leg_capital / price_A)
qty_B = floor(leg_capital / price_B)   # hedge-adjusted: qty_B × β ≈ qty_A × price_A / price_B
```

### 7.4 Risk limits (portfolio level)

| Limit | Value | Action |
|-------|-------|--------|
| Max daily loss | 1.0% of capital | Kill switch, flatten all |
| Max symbol loss | 0.5% of capital | Flatten symbol |
| Max gross exposure | 75% of deployable | Reject new intents |
| Max open orders/symbol | 5 | Reject |
| Max order rate | 2/sec (self-imposed, under Zerodha 3/sec) | Queue + throttle |

### 7.5 Current code gap

`DynamicGridConfig.symbol_capital = 18_750` and `PairConfig.leg_capital = 5_000` are **hardcoded constants**. `configs/live_paper.yaml` defines buckets but **is never loaded**. Phase 1 must implement `CapitalAllocator` service.

---

## 8. Current Codebase Assessment

### What is solid (keep, refactor in place)

| Component | Path | Status |
|-----------|------|--------|
| Dynamic grid logic | `python/vhe/strategies/dynamic_grid.py` | ✅ Core math correct |
| Pair spread logic | `python/vhe/strategies/pair_spread.py` | ✅ Z-score rules correct |
| Momentum | `python/vhe/strategies/momentum.py` | ✅ Regime-gated |
| Regime detector | `python/vhe/strategies/regime.py` | ✅ Not wired to server |
| Paper broker | `python/vhe/execution/paper.py` | ✅ Atomic pair batches |
| Risk guard | `python/vhe/execution/risk.py` | ✅ Basic checks |
| Kite binary parser | `python/vhe/live/kite_binary.py` | ✅ Tested |
| NSE bhavcopy ingest | `python/vhe/data/nse.py` | ✅ Works |
| Daily scanner | `python/vhe/scanner/daily.py` | ✅ Works |
| Event backtester | `python/vhe/backtest/engine.py` | ✅ Correct pattern |
| Dashboard | `python/vhe/platform/server.py` | ✅ Good control UI |

### What is broken or missing (overhaul targets)

| Gap | Severity | Impact |
|-----|----------|--------|
| `KiteWebSocketFeed` raises `NotImplementedError` | 🔴 Critical | No live data |
| No Kite order placement | 🔴 Critical | Cannot trade |
| No order reconciliation | 🔴 Critical | Blind to fills |
| `_simulated_regime()` hack in server | 🔴 Critical | Wrong strategy activation |
| Config YAML not loaded at runtime | 🟠 High | Params drift from docs |
| Static pair β/μ/σ | 🟠 High | Stale signals |
| No pair discovery module | 🟠 High | Manual pair selection |
| No `CapitalAllocator` | 🟠 High | Oversizing risk |
| No persistent state/audit DB | 🟠 High | Restart loses state |
| Rust `vhe-live` is stub | 🟡 Medium | OK for v1 if Python execution is reliable |
| Intraday candle pipeline missing | 🟡 Medium | ATR/EMA on live uses stale daily |
| `duckdb` declared, unused | 🟢 Low | Wire in Phase 3 |

### Architecture smell to fix

`server.py` is a **god object** — feed loop, strategy orchestration, risk, execution, and API in one file. Overhaul splits into:

```text
FeedService → IndicatorService → StrategyOrchestrator → RiskEngine → ExecutionEngine → StateStore
```

---

## 9. Target Architecture (Live-First Overhaul)

### 9.1 Layer diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│                        CONTROL PLANE (FastAPI)                   │
│  Dashboard │ Kill Switch │ Config Hot-Reload │ Activity Audit   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      LIVE TRADING DAEMON                         │
│  ┌──────────┐  ┌─────────────┐  ┌──────────────────────────┐   │
│  │FeedSvc   │→ │IndicatorSvc │→ │StrategyOrchestrator      │   │
│  │Kite WS   │  │5m bars, ATR │  │Grid│Pair│Momentum│Regime │   │
│  └──────────┘  └─────────────┘  └───────────┬──────────────┘   │
│                                              │ intents           │
│  ┌──────────────────────────────────────────▼──────────────┐  │
│  │ RiskEngine (pre-trade) + CapitalAllocator                  │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                              │ approved intents                  │
│  ┌──────────────────────────▼───────────────────────────────┐  │
│  │ ExecutionEngine                                             │  │
│  │  OrderStateMachine │ Reconciler │ Throttle │ Idempotency   │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────▼───────────────────────────────┐  │
│  │ BrokerAdapter (Kite REST + postbacks)                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      DATA PLANE (async batch)                    │
│  NSE bhavcopy │ Kite historical │ Scanner │ PairDiscovery       │
│  Storage: Parquet (raw) + SQLite (orders/positions/audit)       │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 Order state machine (new — most critical component)

```text
NEW → RISK_APPROVED → SENT → ACKNOWLEDGED → PARTIAL_FILL → FILLED
                              ↓                ↓
                           REJECTED         CANCELLED
                              ↓
                          EXPIRED (TTL)
```

Every state transition logged with timestamp + broker order_id. Reconciler polls `kite.orders()` + `kite.trades()` every 5s and on postback webhook.

### 9.3 Feed protocol (already designed — implement it)

```python
# Existing protocol in live/feed.py — implement KiteWebSocketFeed
class QuoteFeed(Protocol):
    async def stream(self) -> AsyncIterator[LiveQuote]: ...
```

Subscription flow:
```text
1. Load instrument cache (kite_instruments.py) — daily
2. Map symbol → instrument_token
3. Connect WS, subscribe mode=quote (OHLCV + volume, not just ltp)
4. Parse binary → LiveQuote (kite_binary.py)
5. BarAggregator: tick → 5m OHLCV bars → IndicatorService
```

### 9.4 Config loading (fix immediately)

All runtime params from YAML:
```text
configs/live_paper.yaml   → paper mode
configs/live_live.yaml    → live mode (new file)
configs/scanner.yaml      → scanner weights
configs/strategies.yaml   → grid/pair/momentum params (new file)
```

Use existing `vhe/config/models.py` — extend Pydantic models, load in daemon startup.

### 9.5 Persistence (SQLite for v1)

Tables:
```text
orders          (order_id, broker_id, symbol, side, qty, price, state, strategy_id, ts)
fills           (fill_id, order_id, qty, price, ts)
positions       (symbol, qty, avg_price, strategy_id, updated_at)
audit_log       (event_type, payload_json, ts)
daily_pnl       (date, realized, unrealized, strategy_id)
pair_stats      (pair_id, beta, mu, sigma, half_life, p_value, as_of_date)
scanner_results (date, symbol, score, rank)
```

SQLite is sufficient for personal account. Migrate to Postgres only if multi-account.

### 9.6 Python vs Rust decision (pragmatic)

| Component | v1 language | Rationale |
|-----------|-------------|-----------|
| Feed + parse | Python | Parser done; async with asyncio |
| Strategy | Python | Fast iteration |
| Risk | Python | Must match backtest exactly |
| Order router | Python | Kite REST is HTTP-bound anyway |
| Reconciler | Python | Async polling |
| Kill switch | Python | Same process, <1ms decision |
| Future: hot path | Rust | Only if Python profiling shows bottleneck |

**Do not block live trading on Rust migration.** Python is fine at 3 orders/sec.

---

## 10. Phased Implementation Plan

> **User priority:** Live platform first, validate strategies with real quotes and small capital, backtest in parallel.

### Phase 0 — Foundation Cleanup (Week 1) ✅ COMPLETE

**Goal:** Config-driven, testable modules without changing strategy math.

| Task | Files | Status |
|------|-------|--------|
| Split `server.py` into services | `platform/services/`, `platform/runtime.py` | ✅ |
| Load all YAML configs | `config/loader.py`, `configs/strategies.yaml` | ✅ |
| Implement `CapitalAllocator` | `execution/capital.py` | ✅ |
| Wire `RegimeDetector` | `platform/services/regime_service.py` | ✅ |
| SQLite schema + migrations | `storage/db.py` | ✅ |
| Terminal UI overhaul | `platform/static/*` | ✅ |

**Exit criteria:** Dashboard runs on simulated feed with config-driven params; restart preserves audit events. ✅

### Phase 1 — Live Market Data (Week 2)

**Goal:** Real Kite WebSocket quotes in dashboard.

| Task | Files | Done when |
|------|-------|-----------|
| Implement `KiteWebSocketFeed` | `live/kite.py` | Streams quote mode for 4 symbols |
| BarAggregator (5m) | `live/bars.py` | OHLCV bars from ticks |
| IndicatorService on live bars | `indicators/service.py` | ATR, ADX, EMA updated per bar |
| Feed health metrics | `platform/state.py` | Staleness alarm >3s |
| Instrument cache daily job | CLI cron | Token map always fresh |

**Exit criteria:** Dashboard shows live RELIANCE/HDFCBANK quotes during market hours with <500ms latency.

### Phase 2 — Order Execution + Reconciliation (Week 3–4)

**Goal:** Place real MIS orders with full state tracking. **Start with ₹1–2 orders manually supervised.**

| Task | Files | Done when |
|------|-------|-----------|
| `KiteBrokerAdapter` | `execution/kite_broker.py` | place/modify/cancel MIS |
| `OrderStateMachine` | `execution/order_fsm.py` | All transitions logged |
| `Reconciler` | `execution/reconciler.py` | Positions match broker |
| Postback webhook handler | `platform/webhooks.py` | Fill events update state |
| Idempotency keys | `execution/order_fsm.py` | No duplicate orders on retry |
| Kill switch | `execution/kill_switch.py` | Flatten + cancel on trigger |
| Order throttle | `execution/throttle.py` | Max 2 orders/sec |

**Exit criteria:** Manual test — place 1 MIS limit order, verify fill in dashboard, restart server, position still correct.

### Phase 3 — Strategy Live Wiring (Week 5)

**Goal:** Grid strategy places resting limit orders on live feed.

| Task | Files | Done when |
|------|-------|-----------|
| Resting order manager | `execution/order_manager.py` | Grid levels = open limits |
| Grid reset cancels stale | `strategies/dynamic_grid.py` | DGT reset works live |
| EOD square-off job | `execution/eod.py` | All flat by 15:10 |
| Paper/live mode switch | `configs/live_*.yaml` | Same code path |
| Strategy intent audit | `storage/db.py` | Every intent logged |

**Exit criteria:** Paper mode on live quotes for 5 sessions; orders match intents; EOD flat.

### Phase 4 — Pair Discovery + Live Pair Trading (Week 6–7)

**Goal:** Data-driven pairs, not hardcoded.

| Task | Files | Done when |
|------|-------|-----------|
| `pairs/discovery.py` | Engle-Granger + FDR | Weekly pair report |
| Rolling β/μ/σ | `pairs/stats.py` | Stats refresh daily |
| Pair grid levels | `strategies/pair_spread.py` | 3-level entry |
| Failed-leg cleanup | `execution/pair_executor.py` | 30s timeout flatten |
| Exclude pair symbols from grid | `strategy_orchestrator.py` | No cross-strategy conflict |

**Exit criteria:** Pair discovery runs on NIFTY 100; top pair paper-traded live for 10 sessions.

### Phase 5 — Live Micro-Capital Deployment (Week 8+)

**Goal:** Real money, minimum size.

| Parameter | Value |
|-----------|-------|
| Capital | ₹25,000 |
| Max symbols | 2 |
| Max grid levels | 3 (not 5) |
| Strategies | Grid only initially |
| Supervision | Manual kill switch ready |

**Scale gates (all must pass before increasing capital):**

```text
□ 60 sessions paper/live parity (PnL delta < 5%)
□ Max drawdown < 3% over 60 sessions
□ Zero reconciliation mismatches over 60 sessions
□ Win rate > 45% on grid round-trips
□ Sharpe > 0.5 on rolling 20-session window
```

### Phase 6 — Backtest + Walk-Forward (Parallel, Week 3 onward)

**Goal:** Validate parameters, not gate live platform.

| Task | Files | Done when |
|------|-------|-----------|
| Kite historical ingest (5m) | `data/kite_historical.py` | 2 years NIFTY 100 |
| Walk-forward harness | `backtest/walk_forward.py` | Train/test splits |
| Pair backtest | `backtest/pair.py` | Costs included |
| Parameter sensitivity report | `reports/` | ATR mult, z thresholds |

---

## 11. Go-Live Checklist (Non-Negotiable)

Before enabling `mode: live` in config:

```text
□ Kite WebSocket feeds quotes with <3s staleness for all traded symbols
□ Instrument token map validated for today
□ RegimeDetector uses live 5m bars, not simulated
□ CapitalAllocator enforces bucket limits
□ Every order has strategy_id + idempotency key
□ Reconciler runs every 5s; positions match kite.positions()
□ Kill switch tested: feed disconnect → flatten within 30s
□ EOD job tested: all positions flat by 15:10
□ Daily loss limit tested: mock loss → trading paused
□ Pair atomic execution: failed leg → cleanup verified
□ Audit log persists across restart
□ Manual override: pause/resume/kill from dashboard
□ SEBI compliance: personal account, <10 OPS
□ Zerodha MIS product type confirmed for all orders
□ Square-off buffer before broker auto-square-off (15:10 vs ~15:20)
```

---

## 12. What We Are NOT Building (Scope Guard)

| Item | Why not |
|------|---------|
| True HFT / market making | Latency uncompetitive |
| Options strategies | Margin + greeks complexity |
| Overnight positions | MIS only in v1 |
| Multi-user SaaS | Personal engine |
| ML/RL signals | No edge proven yet; add in v2 if walk-forward supports |
| Selling signals / managing others' money | SEBI registration required |
| NSE direct connection | Must use broker API |
| Crypto grid | Different microstructure; DGT paper is crypto |

---

## 13. References

### Academic papers
1. Chen, K-Y., Chen, K-H., Jang, J-S.R. (2025). *Dynamic Grid Trading Strategy: From Zero Expectation to Market Outperformance.* arXiv:2506.11921
2. *Designing Efficient Pair-Trading Strategies Using Cointegration for the Indian Stock Market.* arXiv:2211.07080
3. *Implementation Risk in Portfolio Backtesting.* arXiv:2603.20319 (2026)
4. Wood, B., Roberts, S., Zohren, S. (2021). *Slow Momentum with Fast Reversion.* arXiv:2105.13727
5. Li, J. (2016). *Trading VIX Futures under Mean Reversion with Regime Switching.* arXiv:1605.07945
6. Zhu, Y. (2024). *Examining Pairs Trading.* Yale Economics Working Paper

### Indian market empirical
7. QuantInsti EPAT: *Cointegrated Pairs Trading Strategy in Indian Equity Market (2015–2025)*
8. Mann217/Pairs-Trading GitHub: Indian equities cointegration pipeline

### Industry / regulatory
9. Zerodha Kite Connect v3 docs: https://kite.trade/docs/connect/v3/
10. Zerodha Z-Connect: Algo trading platforms overview
11. SEBI retail algo framework (2025–2026): <10 OPS exemption for personal API use
12. QuantPedia: *A Primer on Grid Trading Strategy*

### Architecture
13. QuantInsti: *Automated Trading Systems: Design, Architecture & Low Latency*
14. Brenndoerfer: *Quant Trading Systems: Architecture & Infrastructure*

---

## Appendix A: File Change Map (Overhaul)

```text
NEW  python/vhe/platform/services/feed_service.py
NEW  python/vhe/platform/services/indicator_service.py
NEW  python/vhe/platform/services/strategy_orchestrator.py
NEW  python/vhe/execution/kite_broker.py
NEW  python/vhe/execution/order_fsm.py
NEW  python/vhe/execution/reconciler.py
NEW  python/vhe/execution/capital.py
NEW  python/vhe/execution/order_manager.py
NEW  python/vhe/execution/eod.py
NEW  python/vhe/execution/kill_switch.py
NEW  python/vhe/live/bars.py
NEW  python/vhe/pairs/discovery.py
NEW  python/vhe/pairs/stats.py
NEW  python/vhe/storage/db.py
NEW  configs/live_live.yaml
NEW  configs/strategies.yaml

REFACTOR  python/vhe/platform/server.py        → thin API layer
REFACTOR  python/vhe/live/kite.py              → implement WebSocket
REFACTOR  python/vhe/strategies/pair_spread.py  → rolling stats
REFACTOR  python/vhe/config/models.py           → full config schema
REFACTOR  python/vhe/execution/risk.py          → use CapitalAllocator

KEEP  python/vhe/strategies/dynamic_grid.py     → logic sound
KEEP  python/vhe/strategies/momentum.py
KEEP  python/vhe/strategies/regime.py
KEEP  python/vhe/live/kite_binary.py
KEEP  python/vhe/backtest/engine.py
```

---

## Appendix B: Example Session Timeline (Live Trading Day)

```text
08:45  Daemon starts, loads config, validates instrument cache
09:00  Kite WS connects, subscribes to scanner top-2 symbols + pair legs
09:15  Market open — no new positions (opening volatility filter)
09:25  RegimeDetector active, grid resting limits placed if RANGE
09:30–14:45  Normal trading window
       - Grid: limit buys at ATR levels, sell at fair_value
       - Pair: enter if |z| > 1.5
       - Momentum: enter if TREND_UP breakout
14:45  No new entries
15:00  Cancel all unfilled limits
15:10  Forced square-off all positions
15:15  Reconciliation check, daily PnL recorded
18:00  Evening scanner runs, tomorrow's universe written to DB
```

---

*This document should be updated in `RESEARCH_NOTES.md` whenever a strategy parameter or live execution rule changes.*
