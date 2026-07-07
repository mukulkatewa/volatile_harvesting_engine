# VHE - Interview Preparation Document

> Everything you need to explain this project confidently in a technical interview. Covers system design, architecture decisions, tradeoffs, algorithms, and how to answer common interview questions about this project.

---

## Table of Contents

1. [30-Second Elevator Pitch](#1-30-second-elevator-pitch)
2. [Full System Design Overview](#2-full-system-design-overview)
3. [Component Deep Dives](#3-component-deep-dives)
4. [Key Algorithms Explained Simply](#4-key-algorithms-explained-simply)
5. [Architecture Tradeoffs](#5-architecture-tradeoffs)
6. [Database Design](#6-database-design)
7. [Real-Time Architecture (WebSocket)](#7-real-time-architecture-websocket)
8. [Authentication Design](#8-authentication-design)
9. [Backtesting and Risk Math](#9-backtesting-and-risk-math)
10. [Production Deployment](#10-production-deployment)
11. [What I Would Do Differently](#11-what-i-would-do-differently)
12. [Common Interview Questions and Answers](#12-common-interview-questions-and-answers)

---

## 1. 30-Second Elevator Pitch

**"I built a full-stack algorithmic trading platform for Indian stock markets from scratch. The backend is a Python/FastAPI async server that ingests live market quotes every 30 seconds, runs three quantitative strategies autonomously - a volatility-harvesting grid, a statistical arbitrage pair trade, and a momentum strategy - enforces real-time risk rules on every order, and streams live state to a React dashboard over WebSocket. I added a Monte Carlo simulation engine that runs up to 100,000 bootstrap simulations to compute VaR, CVaR, and probability of ruin, and a walk-forward validation system to test for strategy overfitting. It's deployed live on Oracle Cloud with Google OAuth authentication."**

---

## 2. Full System Design Overview

### High-Level Data Flow

```
                     NSE Market Data
                          |
              +-----------+----------+
              |           |          |
          yfinance    Simulated    Kite WS
          (free)      (offline)  (real-time)
              |           |          |
              +-----------+----------+
                          |
                    Quote Feed
                    (every 30s)
                          |
                          v
              +---------------------+
              |  IndicatorService   |
              |  EMA-20, ATR-14,    |
              |  ADX-14 per symbol  |
              +---------------------+
                          |
                          v
              +---------------------+
              |   RegimeService     |
              |  RANGE/TREND/CRASH  |
              +---------------------+
                          |
              +-----------+-----------+
              |           |           |
        SentimentService  |     BarAggregator
        (Reddit/HN/web)   |     (5-min OHLCV)
                          |
                          v
              +---------------------+
              | StrategyOrchestrator|
              |                     |
              | DynamicGrid  (70%)  |
              | PairSpread   (10%)  |
              | Momentum     (10%)  |
              | Reserve      (10%)  |
              +---------------------+
                          |
                    Orders (list)
                          |
                          v
              +---------------------+
              |    RiskGuard        |
              |  (filters orders)   |
              +---------------------+
                          |
                     Approved orders
                          |
                          v
              +---------------------+
              |  ExecutionEngine    |
              |  PaperBroker or     |
              |  KiteBroker         |
              +---------------------+
                          |
                     Fills + State
                          |
              +-----------+-----------+
              |                       |
         SQLite DB              WebSocket Broadcast
         (fills, events,        (to all browsers)
          sessions, users)
                                       |
                                  React Dashboard
                                  (live P&L, fills,
                                   quotes, events)
```

### Request Flow (Browser to Backend)

```
User clicks "Pause" button
        |
        v
fetch POST /api/control/pause
  + vhe_session cookie (httpOnly JWT)
        |
        v
FastAPI middleware: require_auth
  -> verify_token(cookie) -> UserClaims
        |
        v
pause_automation()
  -> runtime.risk_guard.automation_paused = True
  -> runtime.state.controls.automation_paused = True
  -> append_event("control", "Automation paused")
  -> _broadcast_state() -> sends JSON to all WS subscribers
        |
        v
Returns runtime.state.snapshot() as JSON
        |
        v
Browser updates UI state from response
```

---

## 3. Component Deep Dives

### PlatformRuntime - The Core Object

`PlatformRuntime` is a Python `@dataclass(slots=True)` that holds all shared state. It's a single instance created at server startup and shared across all requests.

**Why a single shared object?**
- Trading state must be consistent. If two requests each had their own copy of the portfolio, you'd get race conditions on position counts.
- asyncio is single-threaded within one event loop, so a shared object is safe without locks (for reads/writes that happen in the same coroutine). Only the background sentiment refresh uses a lock.

**The runtime owns:**
- `state: PlatformState` - the current snapshot sent over WebSocket (portfolio, quotes, fills, events, controls)
- `risk_guard: RiskGuard` - the stateful kill switch and pause flags
- `paper_broker: PaperBroker` - virtual positions and cash
- `subscribers: set[WebSocket]` - all live browser connections
- `sentiment_service: SentimentService` - refreshes in background every 15 min
- All strategy instances, indicator service, bar aggregator, database

### Quote Feed Pipeline

```
build_quote_feed() -> FeedBuildResult
    |
    + source = "yfinance"  -> YFinanceFeed
    + source = "simulated" -> SimulatedFeed
    + source = "kite"      -> KiteWebSocketFeed
    |
    async for quote in feed.stream():
        await _handle_quote(quote)

_handle_quote(quote):
    1. Update indicator_service.update(quote)
    2. Update bar_aggregator.push(quote)
    3. Update regime_service.classify(snapshot)
    4. Update sentiment gating (check score)
    5. Run strategy_orchestrator.process_quote(quote)
       -> generates orders
    6. For each order: risk_guard.evaluate(order, portfolio)
       -> approved orders go to execution_engine.submit()
    7. Update portfolio snapshot
    8. Broadcast state to all WebSocket subscribers
```

### Strategy Orchestrator - The Brain

The orchestrator runs all three strategies on every quote and collects their order proposals. This is a **pull model** - strategies don't place orders directly, they return order proposals to the orchestrator which then filters through the risk layer.

```python
# Simplified
def process_quote(quote):
    orders = []
    orders += grid_strategy.generate_orders(quote, indicators, regime)
    orders += pair_strategy.generate_orders(quotes, indicators)
    orders += momentum_strategy.generate_orders(quote, indicators, regime)

    for order in orders:
        decision = risk_guard.evaluate(order, portfolio)
        if decision.approved:
            fill = execution_engine.submit(order, quote)
            if fill:
                state.fills.append(fill)
```

---

## 4. Key Algorithms Explained Simply

### ATR-Driven Dynamic Grid

**Problem:** How do you decide how far apart to place buy orders?

**Solution:** Use the Average True Range (ATR) - a measure of how much the stock typically moves in a day. If a stock moves INR 20 on average (ATR = 20), place grid levels 20 * 0.45 = INR 9 apart. This way the grid automatically tightens for low-volatility stocks and widens for high-volatility ones.

```
ATR-14 = exponential moving average of:
  max(high-low, |high-prev_close|, |low-prev_close|)
  over 14 periods

Grid spacing = ATR_14 * atr_multiplier (0.45)
Buy level N  = fair_value - (N * spacing)
Fair value   = EMA-20 (exponential moving average of last 20 closes)
```

**Why EMA for fair value?** EMA weights recent prices more heavily than old ones. If a stock crashes from 3000 to 2500 quickly, the EMA at 2850 correctly shows the stock is below fair value - a buy signal. Simple moving average would lag too much.

**Why 0.45x ATR for spacing?** Calibrated from backtests. Tight enough to capture intraday swings (NSE typical intraday range is 1-3%), wide enough that levels don't fill too quickly and consume all capital.

### Market Regime Classifier

```
RANGE  -> ADX < 20   (choppy, sideways - grid works here)
TREND  -> ADX > 25   (strong directional move - momentum works here)
CRASH  -> intraday drawdown < -6% (circuit breaker - halt everything)
```

**ADX (Average Directional Index)** measures trend strength from 0-100. Low ADX = choppy. High ADX = strong trend. The direction doesn't matter for ADX - it just measures how "trendy" the market is.

**Why 20/25 thresholds?** Standard Wilder thresholds from technical analysis literature. 20 is "no trend", 25 is "trend starting". The 5-point gap creates a buffer zone so the strategy doesn't flip between RANGE and TREND on every small fluctuation.

### Pair Spread Z-Score

```
Step 1: Compute spread
spread = log(RELIANCE_price) - log(HDFCBANK_price)

Step 2: Standardize
z = (spread - historical_mean) / historical_std

Step 3: Trade
if z > +1.5: spread is too wide
  -> sell RELIANCE (overpriced vs HDFCBANK)
  -> buy HDFCBANK
  -> expect spread to mean-revert, Z returns to 0

if |z| < 0.25: close position (spread normalized)
```

**Why log prices?** Log returns are additive and handle different price scales. RELIANCE trades at ~2800, HDFCBANK at ~1700 - using raw prices would create a size mismatch.

**Why 1.5 sigma entry?** At 1.5 standard deviations, you have statistical evidence the spread is dislocated but not so extreme it means something fundamental changed. 2.0 sigma would give fewer, higher-confidence signals. 1.0 sigma would trade too often on noise.

### Monte Carlo Bootstrap

```
Historical trades: [+120, -45, +80, +200, -30, ...]  (N trades)

For each simulation i in 1..10000:
    Randomly resample N trades with replacement
    Simulate equity path: capital + cumsum(resampled_pnls)
    Record: final equity, max drawdown, did_ruin (equity < 50% of start)

Results:
    VaR_95 = 5th percentile of final equities
    CVaR_95 = mean of bottom 5% of final equities
    P(ruin) = count(did_ruin) / n_sims
    Kelly f = mean(pnl) / variance(pnl)  (simplified Kelly formula)
```

**Why bootstrap instead of parametric VaR?** Bootstrap makes no assumptions about the distribution of returns. Real trading P&L is not normally distributed - it has fat tails and skewness. Bootstrap captures the actual shape of your historical P&L.

### Walk-Forward Validation

**The problem with backtesting:** If you test 100 parameter combinations and pick the best one, you've found parameters that fit the historical data by luck. Walk-forward validation checks if good in-sample parameters are actually predictive out-of-sample.

```
Timeline: [---------- 6 months of data ----------]

Window 1:  [---Train 60d---][Test 15d]
Window 2:         [---Train 60d---][Test 15d]
Window 3:               [---Train 60d---][Test 15d]
(step = 15d, so windows overlap in training)

For each window:
  IS (in-sample): grid search {atr_mult: 0.30/0.45/0.60, levels: 3/5}
  Best IS params -> run on OOS (out-of-sample) period
  Record OOS Sharpe ratio

WF Efficiency = mean(OOS Sharpe) / mean(IS Sharpe)
```

If WF Efficiency > 0.5, the best in-sample parameters generalize well. If it's 0.1, you've overfit.

---

## 5. Architecture Tradeoffs

### Single Process vs Microservices

**Choice:** Single Python process with asyncio.

**Why:** For a personal trading terminal at this scale (17 symbols, 1 user), a single process is dramatically simpler. All components share memory - the orchestrator reads the latest indicator values directly without an HTTP call or message queue. The WebSocket broadcast is just iterating a set of socket objects.

**The cost:** You can't scale horizontally. If you needed to handle 1000 symbols with 100 concurrent users, you'd want the quote feed, strategies, and WebSocket server as separate services connected by a message broker (Kafka or Redis Pub/Sub).

**When would I change this?** If the platform needed to serve multiple independent trading accounts with different strategies, or if the indicator computation became a bottleneck (it's currently sub-millisecond per tick).

### SQLite vs PostgreSQL

**Choice:** SQLite.

**Why:** Single writer, personal tool, file-based (no separate process). SQLite handles thousands of writes per day trivially. The entire trading day of fills for 17 symbols at 30-second intervals is maybe 200-500 rows.

**The cost:** No concurrent writers (only one process writes anyway), no horizontal scaling, no native JSON operators (though SQLite 3.38+ has them). The current code opens a fresh connection per call which is inefficient but correct.

**When would I change this?** PostgreSQL if: multiple processes need to write (live trading servers + backfill jobs + API servers), if I need complex queries across many sessions, or if I needed connection pooling (SQLAlchemy + asyncpg).

### In-Memory State vs Database as Source of Truth

**Choice:** PlatformRuntime holds all state in memory. SQLite is an audit log, not the source of truth.

**Why:** Low latency. On every tick (every 30 seconds), the state needs to be broadcast to the browser. Reading from database on every tick would add 1-5ms of blocking I/O. In-memory reads are nanoseconds.

**The cost:** If the server crashes, in-memory state is lost. The position table in SQLite means you can reconstruct positions after a restart, but there's a brief inconsistency window.

**How it's handled:** On startup, `PlatformRuntime.bootstrap()` reloads open positions from the database. This is why the SQLite schema tracks open positions separately from fills.

### asyncio + FastAPI vs Django/Flask + Threads

**Choice:** asyncio event loop with FastAPI.

**Why:** The quote feed is I/O-bound (waiting for yfinance HTTP responses or Kite WebSocket messages). asyncio handles hundreds of concurrent WebSocket connections efficiently because coroutines yield during I/O waits instead of blocking a thread. FastAPI's dependency injection (`Depends(require_auth)`) makes auth middleware clean.

**The cost:** Blocking code in async handlers stalls the entire event loop. The backtest endpoints (Monte Carlo, walk-forward) are CPU-bound - they block for 2-5 seconds. Fixed by wrapping in `asyncio.to_thread()` so they run in a thread pool without blocking the event loop.

### WebSocket Push vs Polling

**Choice:** WebSocket push from server to all connected browsers on every state change.

**Why:** Trading UIs need sub-second updates. HTTP polling at 1-second intervals would generate constant load and still feel laggy. WebSocket keeps a persistent connection - state updates arrive within milliseconds of being triggered.

**The cost:** WebSocket connections are stateful. Dead connections must be detected and pruned. Current fix: the handler calls `await websocket.receive()` with a 30-second timeout - if the client disconnects, `receive()` raises and the `finally` block removes the socket from the subscriber set.

### Frontend: SPA vs SSR

**Choice:** Single Page Application (Vite + React, served as static files by FastAPI).

**Why:** The dashboard is highly interactive with live updates every few seconds. SSR would re-render the entire page on every state change. React's virtual DOM only updates the changed components when state updates arrive via WebSocket.

**How static files work:** `npm run build` outputs to `python/vhe/platform/static/`. FastAPI mounts that directory and serves `index.html` for all `/dashboard/*` and `/profile` routes (SPA fallback). The browser handles all routing client-side with React Router.

---

## 6. Database Design

### Tables

```sql
-- Users (from Google OAuth)
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    google_id TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    virtual_capital_inr INTEGER DEFAULT 75000,
    created_at TEXT NOT NULL
);

-- Every paper fill (immutable audit log)
CREATE TABLE fills (
    fill_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,           -- BUY / SELL
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    pnl REAL,
    reason TEXT,                  -- grid_buy / sentiment_halt / force_exit / etc.
    filled_at TEXT NOT NULL,
    session_id TEXT
);

-- Timestamped event log
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,       -- feed / risk / fill / control / sentiment
    message TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    ts TEXT NOT NULL
);

-- Trading session summaries
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    total_pnl REAL,
    fill_count INTEGER DEFAULT 0
);
```

### Key Design Decisions

**Why TEXT for timestamps?** ISO 8601 strings are human-readable in SQLite Browser and sort correctly as strings. SQLite has no native datetime type anyway.

**Why fill_id as TEXT primary key?** Generated as `f"{symbol}-{order_id}-{timestamp}"` so it's naturally unique and debuggable. Avoids needing a sequence generator.

**Why no foreign keys between fills and sessions?** SQLite foreign key enforcement is opt-in and off by default. The session_id is a denormalized string to avoid the complexity. Queries joining fills to sessions are rare (only in analytics).

---

## 7. Real-Time Architecture (WebSocket)

### How State Gets to the Browser

```
1. Quote arrives from yfinance (every 30s)
2. _handle_quote() processes the tick (indicators, regime, strategies, risk, execution)
3. runtime.state gets mutated with new portfolio snapshot, new fills, new events
4. _broadcast_state() is called:

   snapshot = state.snapshot()   # converts dataclasses to dict
   dead = set()
   for ws in runtime.subscribers:
       try:
           await ws.send_json(snapshot)
       except Exception:
           dead.add(ws)
   runtime.subscribers -= dead

5. Browser's WebSocket.onmessage fires
6. setState(JSON.parse(event.data)) triggers React re-render
7. React updates only the components that changed (virtual DOM diff)
```

### Connection Lifecycle

```
Browser connects:
  WebSocket handshake -> /ws/state
  server: accept(), add to subscribers
  server: send current state snapshot immediately
  server: loop { receive() with 30s timeout }
           -> TimeoutError = keepalive tick (client alive)
           -> WebSocketDisconnect = client gone

Browser disconnects:
  receive() raises exception
  finally: subscribers.discard(websocket)

Page refresh:
  Old connection closes -> removed from subscribers
  New connection opens -> added, gets fresh snapshot
```

### Why Full State on Every Tick vs Delta Updates

**Choice:** Send the entire state snapshot (~2-5 KB JSON) on every tick.

**Why:** Simplicity. Delta updates require the client to maintain an accumulator and handle out-of-order messages. If a message is missed, the client has stale state with no way to know. Full state means the client is always correct after any message.

**The cost:** 5 KB every 30 seconds = 167 bytes/second per client. For a personal tool with 2-3 concurrent users, this is negligible. At 10,000 concurrent users you'd switch to delta updates.

---

## 8. Authentication Design

### Flow

```
1. User clicks "Sign in with Google"
2. Browser: GET /auth/google/login
3. Server: check GOOGLE_CLIENT_ID is configured
4. Server: redirect 307 to Google OAuth URL
   https://accounts.google.com/o/oauth2/v2/auth
   ?client_id=...
   &redirect_uri=http://localhost:8765/auth/google/callback
   &response_type=code
   &scope=openid email profile

5. User approves on Google
6. Google: redirect to /auth/google/callback?code=XYZ

7. Server: exchange code for tokens
   POST https://oauth2.googleapis.com/token
   -> returns access_token + id_token

8. Server: decode id_token -> {google_id, email, name}
9. Server: database.upsert_user(google_id, email, name)
   -> INSERT OR REPLACE, get internal user_id

10. Server: create_token(user_id, email, name)
    -> JWT: {sub: user_id, email, name, exp: now+7days}
    -> signed with JWT_SECRET using HS256

11. Server: Set-Cookie: vhe_session=<jwt>; HttpOnly; SameSite=Lax; Max-Age=604800
12. Server: redirect 307 to /dashboard

13. Browser: loads /dashboard (React SPA)
14. React: GET /api/me with cookie (httpOnly, sent automatically)
15. Server: verify_token(cookie) -> UserClaims -> get user from DB
16. Browser: user is logged in, dashboard loads
```

### Security Decisions

**HttpOnly cookie vs localStorage:** HttpOnly cookies cannot be read by JavaScript, so XSS attacks cannot steal the session token. LocalStorage is readable by any script on the page.

**SameSite=Lax:** Cookies are sent on same-site requests and top-level cross-site navigations (like following a link). This prevents CSRF attacks where a malicious site tricks the browser into making authenticated requests.

**HS256 vs RS256:** HS256 (symmetric) is simpler - one secret, faster verification. RS256 (asymmetric) is needed when multiple services need to verify tokens independently without sharing a secret. For a single-service app, HS256 is fine.

**7-day expiry:** Balance between security (shorter = more secure) and UX (longer = less re-auth friction). No refresh token implemented - on expiry the user re-auths via Google.

---

## 9. Backtesting and Risk Math

### Event-Driven Backtester

The backtester replays historical OHLCV bars and simulates exactly how the live strategy would behave:

```
For each bar in historical data:
    1. Build a fake LiveQuote from OHLCV
    2. Update indicators (EMA, ATR, ADX)
    3. Classify regime
    4. Run strategy -> order proposals
    5. Simulate fills (price within bar's high-low range)
    6. Update portfolio

Output: list of TradeRecord (entry_price, exit_price, pnl, entry_time, exit_time)
```

**Why event-driven vs vectorized?** Event-driven simulates look-ahead bias prevention. You can only see data up to the current bar. Vectorized backtests that use the entire dataset at once can accidentally use future data to make current decisions (look-ahead bias), which inflates performance.

### Kelly Criterion

```
Kelly fraction = mean(pnl) / variance(pnl)

Interpretation:
  0.25 = bet 25% of capital per trade (full Kelly)
  In practice: use half-Kelly (0.125) to account for estimation error
```

Kelly tells you the theoretically optimal fraction of capital to risk on each trade given your historical win rate and payoff ratio. Values > 1 mean the strategy has edge but Kelly assumes perfect knowledge of future probabilities, so the displayed value is guidance, not a hard rule.

### VaR vs CVaR

```
VaR_95 = the loss you won't exceed in 95% of scenarios
         (5% of simulations end worse than this)

CVaR_95 = average loss in the worst 5% of scenarios
         (also called Expected Shortfall)
```

**Why CVaR matters more than VaR:** VaR says nothing about how bad the worst 5% can be. If VaR is -INR 5000, that's the boundary but the actual worst case could be -INR 50,000. CVaR captures the average of those tail scenarios, which is what determines your true risk of ruin.

---

## 10. Production Deployment

### Oracle Cloud Always Free

- **ARM64 Ampere A1 instance**: 4 vCPU, 24 GB RAM - generous for a Python server
- **No cost**: Oracle's Always Free tier doesn't expire for these specs
- **Why not AWS/GCP?** Free tier on AWS (t2.micro = 1 vCPU, 1 GB RAM) would be too constrained for yfinance polling + React SSR. Oracle's free tier is genuinely production-capable.

### nginx Configuration

```
client -> nginx (port 443, HTTPS) -> uvicorn (port 8765, HTTP)

nginx handles:
  - SSL termination (Let's Encrypt cert)
  - WebSocket upgrade (proxy_set_header Upgrade $http_upgrade)
  - Static file serving for /assets/* (could bypass FastAPI)
  - Rate limiting if needed
```

### DuckDNS

Free dynamic DNS. A cron job on the server pings `https://www.duckdns.org/update?token=xxx&domains=mukul-vhe` every 5 minutes to keep the DNS record pointing to the current public IP.

### systemd Service

```ini
[Service]
ExecStart=/home/ubuntu/vhe/.venv/bin/uvicorn vhe.platform.server:app
          --host 127.0.0.1 --port 8765 --app-dir python
Restart=always
RestartSec=5
```

`Restart=always` means if uvicorn crashes (yfinance network error, out of memory), it restarts within 5 seconds automatically.

---

## 11. What I Would Do Differently

### If This Were a Production Multi-User System

**1. Separate services**
```
Quote Feed Service -> Kafka -> Strategy Engine -> Order Router
                          |
                          -> TimeSeries DB (InfluxDB/TimescaleDB)
                          -> WebSocket Gateway (fan-out to users)
```
The current single-process design can't have the feed, strategies, and web server fail independently.

**2. Async SQLite / Switch to PostgreSQL**
All SQLite writes currently block the event loop. Would use asyncpg + PostgreSQL for proper async persistence.

**3. Per-user strategy instances**
Currently everyone sees the same paper portfolio. Real multi-user would need each user to have their own position state and risk limits.

**4. Better secrets management**
JWT_SECRET and Google OAuth keys are in `.env` files. In production these should come from a secrets manager (AWS Secrets Manager, HashiCorp Vault, or at minimum environment variables injected by the deployment system, never in files).

**5. Proper logging with structured output**
Currently events go to SQLite. In production: structured JSON logs -> CloudWatch/Datadog for alerting on fill failures, connection drops, and strategy errors.

**6. Rate limiting and circuit breakers on external APIs**
yfinance and Kite API calls have no retry/circuit-breaker logic. If yfinance is rate-limited, the feed silently falls back to simulated without alerting.

### Technical Debt That Exists

- SQLite connection opened and closed per call (should use a connection pool or WAL mode with a single shared connection)
- Blocking HTTP in `KiteBroker` for live order placement (should be `httpx.AsyncClient`)
- No metrics/observability (would add Prometheus counters for tick latency, fill rates, error rates)

---

## 12. Common Interview Questions and Answers

### "Walk me through what happens when the market opens at 9:15 AM"

"The uvicorn server has been running since boot. At 9:15 AM IST, the `market_session` logic detects the session is now in the TRADING phase. The yfinance feed starts returning real quotes for each of the 17 symbols. On the first tick for each symbol, the IndicatorService seeds EMA, ATR, and ADX values from the pre-market indicator warmup that happened earlier. The regime classifier reads the ADX - if it's below 20, it's RANGE, and the grid strategy arms. Orders start being generated. Every order passes through RiskGuard. Approved orders go to PaperBroker which immediately fills them at the tick price. The fill is appended to state, state is broadcast via WebSocket to any open browser tabs, and the fill is persisted to SQLite."

### "How do you prevent overfitting in the strategy?"

"Three ways. First, the walk-forward validation system - I only claim a parameter set is good if it also performs well on out-of-sample data it never saw during optimization. If WF efficiency is below 0.5, I don't trust the parameters. Second, the Monte Carlo simulation - instead of just reporting average P&L, I bootstrap 10,000 scenarios. If the 5th percentile equity (VaR 95%) is deeply negative, the strategy is too risky regardless of average performance. Third, the parameters themselves are economically motivated - ATR-based grid spacing adapts to actual volatility instead of being curve-fitted to a specific period."

### "How does the WebSocket scale to many users?"

"Currently, every connected browser gets the full state snapshot (about 3-5 KB) on every quote tick, which is every 30 seconds for yfinance. That's around 170 bytes/second per client. For a hundred concurrent users that's 17 KB/s total - completely trivial for a server. At 10,000 users it would be 1.7 MB/s which is still fine for a single server, but the Python asyncio single-threaded model would start to show latency as the send loop iterates through 10,000 sockets. At that scale I'd use a dedicated WebSocket gateway like Socket.IO or a Redis Pub/Sub fan-out where the gateway handles individual connections and the Python backend just publishes one message per tick."

### "Why did you choose Python over Go or Java for a trading system?"

"For a systematic quantitative strategy at this scale, Python is the right choice. The scientific ecosystem - pandas, numpy, yfinance - has no equivalent in Go or Java for financial data processing. Strategy logic is more about math and data manipulation than raw throughput. The bottleneck is the 30-second quote interval, not processing speed. The entire tick processing pipeline runs in milliseconds. If I needed microsecond-level HFT, Python would be wrong - but for EOD and intraday systematic trading, it's the industry standard for a reason."

### "What's the biggest technical challenge you faced?"

"The asyncio/event-loop issues. Python's asyncio requires all blocking I/O to be explicitly awaited. In early development, `sqlite3` database writes, yfinance HTTP calls, and even file reads were all blocking the event loop on every tick. The symptom was the WebSocket dashboard freezing for 2-3 seconds during data fetches. The fix was: yfinance calls moved to `asyncio.to_thread()`, SQLite writes happen synchronously but in a non-critical path after broadcast, and the backtest endpoints (which can take 2-5 seconds for Monte Carlo) also moved to thread pool execution. Understanding that asyncio is cooperative multitasking - code only yields control at `await` points - was key."

### "How do you handle the case where a symbol crashes during trading?"

"Three layers. First, the RegimeService detects the crash: if the intraday drawdown exceeds -6%, the symbol's regime switches to CRASH. The grid strategy immediately stops generating new buy orders for that symbol. Second, if the drawdown triggers the daily loss cap (-1% of capital at the portfolio level), the RiskGuard rejects all new orders with `daily_loss_limit`. Third, the kill switch can be manually activated from the dashboard which stops all new orders immediately but keeps existing positions open to exit naturally or be manually closed. The 15:10 IST force-exit ensures all positions are closed before market close regardless of what happened during the day."

### "Explain the pair trade. Why RELIANCE and HDFCBANK?"

"They're both large-cap, highly liquid NSE stocks that tend to move together because they're both driven by broad market factors (Sensex/Nifty). The pair spread - log(RELIANCE) minus log(HDFCBANK) - is historically mean-reverting around 0.50 with a standard deviation of 0.065. When the spread goes to 1.5 standard deviations away from the mean, that's statistically unusual. The trade bets it will revert. I calibrated the mean and std from 6 months of daily yfinance data. The risk is that the spread breaks structurally - like if RELIANCE gets hit by regulatory news while HDFCBANK doesn't. That's why there's a max Z-score of 3.0: if the spread goes to 3 sigma, I assume something fundamental changed and I exit rather than double down."

---

## Key Numbers to Remember

| Metric | Value |
|--------|-------|
| Paper capital | INR 75,000 |
| Symbols watched | 17 NSE large-caps |
| Tick interval | 30 seconds (yfinance) |
| Grid capital | 70% (INR 52,500) |
| Pair capital | 10% (INR 7,500) |
| Momentum capital | 10% (INR 7,500) |
| Reserve | 10% (INR 7,500) |
| Grid levels | Max 3 per symbol |
| ATR multiplier | 0.45x |
| Pair entry Z | 1.5 sigma |
| Pair exit Z | 0.25 sigma |
| Daily loss cap | -1% (-INR 750) |
| Max gross exposure | 75% of capital |
| Force exit time | 15:10 IST |
| Monte Carlo sims | Up to 100,000 |
| Walk-forward train | 60 days |
| Walk-forward test | 15 days |
| WF efficiency threshold | 0.5 = not overfit |
| Sentiment halt score | < -0.55 |
| Tests | 147 passing |
| Lines of Python | ~8,600 |
| Lines of TypeScript/React | ~3,000 |
