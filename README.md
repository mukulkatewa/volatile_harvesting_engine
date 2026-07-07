# Volatility Harvesting Engine (VHE)

> A full-stack, production-deployed systematic trading platform for Indian NSE equities - volatility harvesting via ATR-driven dynamic grids, pair spread arbitrage, and momentum breakouts, with real-time WebSocket dashboard, Monte Carlo risk engine, walk-forward validation, and Google OAuth authentication.

**Live Demo:** [https://mukul-vhe.duckdns.org/](https://mukul-vhe.duckdns.org/)

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6)](https://typescriptlang.org)
[![Tests](https://img.shields.io/badge/Tests-147%20passing-success)](./python/tests)

---

## What It Does

VHE is a single-process algorithmic trading terminal that runs fully autonomously after start-up:

1. **Ingests live quotes** - yfinance (free, ~15 min delay), simulated tick generator, or Zerodha Kite WebSocket (real-time, paid)
2. **Computes indicators** - EMA-20, ATR-14, ADX-14 updated on every tick
3. **Classifies market regime** - RANGE / TREND / CRASH per symbol using ADX thresholds and intraday drawdown
4. **Runs strategies automatically** - no manual clicks; orders fire on each quote tick
5. **Enforces risk rules** - kill switch, daily loss cap, gross exposure limit, per-symbol exposure cap, sentiment halt
6. **Routes through paper or live broker** - aggressive fill model for validation, or Zerodha MIS for real capital
7. **Streams state via WebSocket** to a React dashboard with live P&L, fills, quotes, and event log
8. **Persists everything** to SQLite - fills, events, sessions, users

---

## Architecture

```
Browser (React + Vite + Three.js)
    |
    | HTTPS / WSS
    v
FastAPI Server (uvicorn, asyncio)
    |
    +-- /api/*          REST endpoints (state, config, sentiment, backtest)
    +-- /ws/state       WebSocket - pushes full JSON state on every tick
    +-- /auth/google/*  Google OAuth 2.0 flow -> HS256 JWT httpOnly cookie
    |
    +-- PlatformRuntime (single shared object, slots=True dataclass)
            |
            +-- Quote Feed (yfinance / simulated / Kite WS)
            |       |
            |       v  (every 30s tick)
            +-- IndicatorService    EMA-20, ATR-14, ADX-14 per symbol
            +-- RegimeService       RANGE / TREND / CRASH classifier
            +-- SentimentService    Reddit + HN + last30days bridge
            |
            +-- StrategyOrchestrator
            |       +-- DynamicGridStrategy   70% capital
            |       +-- PairSpreadStrategy    10% capital
            |       +-- MomentumStrategy      10% capital
            |       +-- CapitalAllocator      10% reserve
            |
            +-- RiskGuard -> ExecutionEngine -> PaperBroker / KiteBroker
            +-- PlatformDatabase (SQLite - fills, events, sessions, users)
            +-- WebSocket broadcast to all connected browser sessions
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12, FastAPI, uvicorn, asyncio |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS |
| **Charts** | Recharts |
| **3D / WebGL** | Three.js (shader-based laser animation on landing page) |
| **Auth** | Google OAuth 2.0 + python-jose JWT (HS256, 7-day httpOnly cookie) |
| **Database** | SQLite via Python stdlib `sqlite3` |
| **Market Data** | yfinance (free), Zerodha Kite Connect WebSocket (paid) |
| **Risk Maths** | numpy, pandas |
| **Tests** | pytest - 147 tests |
| **Deployment** | Oracle Cloud Always Free, DuckDNS, nginx, systemd |

---

## Strategies

### 1. ATR-Driven Dynamic Grid (70% of capital)

Places a grid of buy limit orders below fair value (EMA-20), spaced by `ATR-14 x multiplier`. Only arms when regime = RANGE. Harvests mean-reversion moves intraday. Force-exits all positions at 15:10 IST before market close.

```
Fair value (EMA-20):  2847
ATR-14:                 18
Multiplier:           0.45
Spacing:             8.1 pts

Grid:
  2847  [Fair Value - no buys above this]
  2839  [Buy Level 1]
  2831  [Buy Level 2]
  2823  [Buy Level 3]  <- max 3 levels
  2855  [Sell target = FV + min_harvest_pct]
```

Regime gating: Grid buys only in RANGE. In TREND it lets momentum run. In CRASH it halts entirely (ADX > 25 = TREND, intraday drawdown < -6% = CRASH).

### 2. Pair Spread Arbitrage (10% of capital)

Trades the log-spread between RELIANCE and HDFCBANK. Entry when Z-score exceeds 1.5, exit when it reverts to 0.25. Calibrated from 6 months of NSE daily history.

```
Spread = log(RELIANCE_price) - log(HDFCBANK_price)
Z-score = (spread - 0.5001) / 0.0656

Entry:  Z > +1.5  -> sell RELIANCE, buy HDFCBANK (spread too wide)
        Z < -1.5  -> buy RELIANCE, sell HDFCBANK (spread too narrow)
Exit:   |Z| < 0.25
```

### 3. Momentum Breakout (10% of capital)

ATR-based position sizing. Enters on breakout signal with a risk-per-trade cap of INR 187.50 and maximum INR 11,250 capital per trade.

---

## Risk Engine

Every order passes through `RiskGuard` before touching the broker. Orders are rejected silently and logged - they never reach execution:

| Rule | Threshold |
|------|-----------|
| Kill switch | Manual toggle, surfaced on dashboard |
| Daily loss cap | -1% of starting capital |
| Gross exposure | 75% of portfolio maximum |
| Single symbol cap | 30% of portfolio per symbol |
| Symbol quantity | 100 shares max per open position |
| Sentiment halt | Block buys when social score < -0.55 |

---

## Monte Carlo Risk Analysis

Runs N simulations (default 5,000, max 100,000) by bootstrapping historical trade P&L sequences with replacement:

- **VaR 95%** - worst loss at 95th percentile
- **CVaR 95%** - expected loss beyond VaR (tail conditional expectation)
- **P(Ruin)** - probability of drawdown exceeding 50%
- **Kelly fraction** - optimal position size from Kelly criterion
- **Drawdown P95** - 95th percentile of maximum drawdown across simulations
- Equity curve fan chart with median highlighted

---

## Walk-Forward Validation

Prevents overfitting by rolling train-test splits across the full history:

```
|--- Train 60d ---|-- Test 15d --|--- Train 60d ---|-- Test 15d --|
       IS period       OOS               IS               OOS

Per window:
  1. Grid search over {atr_multiplier: [0.30, 0.45, 0.60], max_levels: [3, 5]}
  2. Pick best in-sample Sharpe ratio params
  3. Run those params on out-of-sample period
  4. Record OOS Sharpe and P&L

Final metrics:
  WF Efficiency = mean(OOS Sharpe) / mean(IS Sharpe)
    > 0.5  = Not overfit
    0.3-0.5 = Marginal
    < 0.3  = Overfit
```

---

## Sentiment Engine

Aggregates social signals from multiple sources with exponential time decay (half-life 12 hours):

| Source | Coverage |
|--------|----------|
| Reddit | `/r/IndiaInvestments`, `/r/SecurityAnalysis`, stock ticker mentions |
| Hacker News | Ticker mentions in titles and comments |
| last30days-skill | Deep web, YouTube, X search (optional external bridge) |

Score range: -1.0 (very negative) to +1.0 (very positive). Scores below -0.55 trigger a `HALT` action that blocks new buys for that symbol.

---

## Dashboard

| Tab | Content |
|-----|---------|
| **Terminal** | Live equity, session P&L, gross exposure, risk alerts, control buttons, live quote table with regime |
| **Strategies** | Per-symbol grid plans, pair spread Z-score live, momentum signals |
| **Execution** | Real-time paper fill tape with timestamps |
| **Activity** | Timestamped event log - feed, risk, fill, and control events |
| **Risk** | Monte Carlo panel + Walk-Forward validation with equity curve chart |

---

## Quick Start

```bash
git clone https://github.com/mukulkatewa/volatile_harvesting_engine.git
cd volatile_harvesting_engine

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Edit .env: fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, JWT_SECRET
# Zerodha keys are optional - paper mode works without them

uvicorn vhe.platform.server:app --host 127.0.0.1 --port 8765 --app-dir python
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765)

**Frontend dev (hot reload):**

```bash
cd frontend
npm install
npm run dev   # proxies /api, /auth, /ws to backend on :8765
```

**Run tests:**

```bash
pytest python/tests/ -q   # 147 tests, ~8 seconds
```

---

## Configuration

### Environment Variables (`.env`)

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_CLIENT_ID` | For login | OAuth 2.0 client ID from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | For login | OAuth 2.0 client secret |
| `JWT_SECRET` | For login | Random hex: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `KITE_API_KEY` | Live mode only | Zerodha Connect API key |
| `KITE_API_SECRET` | Live mode only | Zerodha Connect API secret |
| `KITE_ACCESS_TOKEN` | Live mode only | Daily session token (refresh every morning) |
| `VHE_LIVE_CONFIG` | Optional | Config profile file (default: `live_free.yaml`) |

### Live Config Profiles

| Profile | Feed | Orders | Use When |
|---------|------|--------|----------|
| `live_free.yaml` | yfinance | Paper | Default - no paid keys needed |
| `live_paper.yaml` | Simulated | Paper | Offline / no network |
| `live_kite.yaml` | Kite WebSocket | Paper | Paid Connect for live NSE quotes |
| `live_live.yaml` | Kite WebSocket | Real MIS | Production live trading |

---

## Project Structure

```
volatile_harvesting_engine/
├── python/vhe/
│   ├── platform/           FastAPI server, runtime orchestration, state model
│   ├── strategies/         DynamicGrid, PairSpread, Momentum, Regime classifier
│   ├── execution/          RiskGuard, PaperBroker, KiteBroker, ExecutionEngine
│   ├── backtest/           EventDrivenBacktester, MonteCarlo, WalkForward, Optimiser
│   ├── live/               Quote feeds (yfinance, Kite WS, simulated), BarAggregator
│   ├── indicators/         EMA, ATR, ADX streaming computation
│   ├── sentiment/          Collectors (Reddit, HN, last30days), scoring, service
│   ├── analytics/          PaperStats, SessionTracker
│   ├── auth/               Google OAuth, JWT utils, FastAPI middleware
│   ├── storage/            SQLite persistence layer
│   ├── config/             YAML loader, Pydantic config models
│   └── scanner/            Daily NSE large-cap stock scanner
├── frontend/src/
│   ├── components/
│   │   ├── auth/           LandingPage (Three.js WebGL hero), ProtectedRoute
│   │   ├── dashboard/      Terminal, Strategies, Execution, Activity tabs
│   │   ├── layout/         DashboardLayout, Sidebar, Header
│   │   ├── risk/           MonteCarloPanel, WalkForwardPanel with Recharts
│   │   ├── profile/        ProfilePage (virtual capital settings)
│   │   └── ui/             LaserFlow (WebGL shader), Button (shadcn-style)
│   ├── hooks/              useWebSocket (reconnecting WS + postControl), useAuth
│   ├── api/                client.ts - typed fetch wrapper with error extraction
│   └── types/              api.ts - VHEState, User, MonteCarloResult, WFResult
├── configs/                YAML strategy + live profile configs
├── python/tests/           147 pytest tests
└── pyproject.toml
```

---

## Deployment

Running on **Oracle Cloud Always Free** (ARM64 Ampere A1, 4 vCPU / 24 GB RAM):

- **nginx** - HTTPS termination, reverse proxy to uvicorn on port 8765
- **DuckDNS** - Dynamic DNS pointing `mukul-vhe.duckdns.org` to OCI public IP
- **systemd** - Auto-restart on failure, starts on boot
- **Static assets** - Built by Vite into `python/vhe/platform/static/`, served directly by FastAPI

```bash
# On the server
systemctl start vhe
systemctl status vhe
journalctl -u vhe -f
```

---

## License

MIT
