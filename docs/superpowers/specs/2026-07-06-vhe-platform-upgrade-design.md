# VHE Platform Upgrade — Design Spec
**Date:** 2026-07-06  
**Scope:** Monte Carlo Risk Engine + Walk-Forward Validation + React Migration + Google Auth

---

## Overview

Three features delivered in sequence, each building on the last:

1. **Monte Carlo Risk Engine** — statistical risk analysis on backtest trade logs
2. **Walk-Forward Validation** — rolling out-of-sample strategy validation
3. **React + Vite Migration + Google Auth + Virtual Portfolio** — modern frontend, user accounts, virtual capital scorecard

**Build order:** Features 1 and 2 ship against the existing vanilla JS dashboard. Feature 3 migrates the frontend and adds auth on top of the complete platform.

---

## Feature 1 — Monte Carlo Risk Engine

### Purpose

The existing backtester returns one P&L number. Monte Carlo returns a *distribution* of outcomes by resampling the trade log thousands of times, answering: "What is the realistic worst-case? How likely is ruin?"

### Files

| File | Action | Size |
|------|--------|------|
| `python/vhe/backtest/monte_carlo.py` | Create | ~180 LOC |
| `python/vhe/platform/server.py` | Modify — add endpoint | +30 LOC |
| `python/vhe/platform/static/app.js` | Modify — add Risk tab | +80 LOC |
| `python/vhe/platform/static/index.html` | Modify — add tab button | +5 LOC |
| `python/tests/test_monte_carlo.py` | Create | ~60 LOC |

### Algorithm

Bootstrap simulation over the trade list from `ledger.py`:

```python
class MonteCarloResult:
    var_95: float          # 5th percentile final equity (absolute loss floor)
    cvar_95: float         # Mean of bottom 5% (expected shortfall)
    p_ruin: float          # Fraction of sims where equity < 50% start capital
    drawdown_p95: float    # 95th percentile of max drawdowns (as fraction)
    kelly_fraction: float  # Optimal position size fraction
    pnl_percentiles: dict  # {p5, p25, p50, p75, p95}
    equity_curves: list    # 100 sampled curves for chart rendering

def run(trades, initial_capital, n_sims=10_000) -> MonteCarloResult:
    for _ in range(n_sims):
        sample = random.choices(trades, k=len(trades))  # with replacement
        equity = cumsum(initial_capital + [t.pnl for t in sample])
        record(final=equity[-1], drawdown=max_drawdown(equity), ruin=equity[-1] < initial_capital * 0.5)
```

Kelly fraction (standard formula):
```
b = avg_win / avg_loss   # gain-to-loss ratio
f* = win_rate - loss_rate / b   # = p - q/b
```
Clamped to [0, 0.25] — never recommend betting more than 25% of capital.

### API

```
POST /api/backtest/monte-carlo
Content-Type: application/json

{
  "symbol": "RELIANCE",
  "bars_file": "data/RELIANCE_2025.csv",
  "n_sims": 10000,
  "initial_capital": 75000
}

200 OK
{
  "var_95": -3200,
  "cvar_95": -4100,
  "p_ruin": 0.02,
  "drawdown_p95": 0.048,
  "kelly_fraction": 0.18,
  "pnl_percentiles": {"p5": -1800, "p25": 800, "p50": 2400, "p75": 3900, "p95": 5100},
  "equity_curves": [[75000, 76200, ...], ...],  // 100 curves × n_trades points (x-axis = trade index)
  "sim_count": 10000,
  "trade_count": 48
}
```

### UI (vanilla JS — Risk tab)

- Histogram: P&L distribution with VaR line marked
- Spaghetti chart: 100 equity curve overlays (grey, low opacity) with median highlighted
- Metrics table: VaR 95%, CVaR, P(ruin), Max Drawdown P95, Kelly fraction
- All rendered with Chart.js loaded from CDN (no build step)

### Error handling

- `400` if `bars_file` does not exist or produces < 10 trades
- `422` if `n_sims` > 100,000 (protect server from runaway requests)
- Computation runs synchronously — at 10k sims it completes in < 500ms (numpy vectorised)

---

## Feature 2 — Walk-Forward Validation Harness

### Purpose

Proves the grid strategy parameters are not curve-fitted by repeatedly optimising on training data and measuring performance on held-out test data. Walk-Forward Efficiency (WFE) > 0.5 is the target.

### Files

| File | Action | Size |
|------|--------|------|
| `python/vhe/backtest/walk_forward.py` | Create | ~220 LOC |
| `python/vhe/backtest/optimiser.py` | Create | ~80 LOC |
| `python/vhe/platform/server.py` | Modify — add endpoint | +20 LOC |
| `python/vhe/platform/static/app.js` | Modify — add WF section to Risk tab | +60 LOC |
| `python/tests/test_walk_forward.py` | Create | ~50 LOC |

### Algorithm

```python
@dataclass
class WFWindow:
    period: str            # "2025-01 to 2025-03 | test: Apr"
    is_sharpe: float       # In-sample Sharpe after optimisation
    oos_sharpe: float      # Out-of-sample Sharpe (held-out)
    oos_pnl: float
    best_params: dict      # {"atr_multiplier": 0.45, "max_levels": 3}

def run(bars_df, train_days=60, test_days=15, step_days=15) -> WFResult:
    param_grid = {
        "atr_multiplier": [0.30, 0.45, 0.60],
        "max_levels": [3, 5],
    }
    for each window:
        best_params = grid_search(train_bars, param_grid, metric="sharpe")
        oos = backtest(test_bars, best_params)
        windows.append(WFWindow(...))
    
    wf_efficiency = mean(oos_sharpes) / mean(is_sharpes)
    verdict = "Not overfit" if wfe > 0.5 else "Marginal" if wfe > 0.3 else "Curve-fitted"
```

Param stability score: fraction of windows where best `atr_multiplier` matches the mode across all windows (1.0 = perfectly stable).

### API

```
GET /api/backtest/walk-forward?symbol=RELIANCE&train_days=60&test_days=15&step_days=15

200 OK
{
  "windows": [
    {
      "period": "2025-01-01 to 2025-03-02 | test: 2025-03-03 to 2025-03-18",
      "is_sharpe": 1.42,
      "oos_sharpe": 0.91,
      "oos_pnl": 1840,
      "best_params": {"atr_multiplier": 0.45, "max_levels": 3}
    }
  ],
  "wf_efficiency": 0.64,
  "verdict": "Not overfit",
  "param_stability": {"atr_multiplier": 0.45, "stability_score": 0.82}
}
```

### UI (vanilla JS — Risk tab, below MC section)

- Table: one row per window, IS Sharpe / OOS Sharpe / OOS P&L / Best Params
- WF Efficiency badge: green (>0.5), amber (0.3–0.5), red (<0.3)
- Param stability indicator per hyperparameter

### Error handling

- `400` if not enough bars for at least 2 windows
- `400` if `train_days + test_days > total_bar_count`
- Grid search runs all param combinations in parallel via `concurrent.futures.ThreadPoolExecutor`

---

## Feature 3 — React + Vite Migration + Google Auth + Virtual Portfolio

### Approach

Port the existing vanilla JS dashboard to React 18 + Vite + TypeScript. Add Google OAuth via a backend-driven flow. Add virtual portfolio tracking per user (scorecard overlay over the shared session).

### Frontend stack

| Package | Version | Purpose |
|---------|---------|---------|
| react + react-dom | ^18 | UI framework |
| vite | ^5 | Build tool |
| typescript | ^5 | Type safety |
| tailwindcss | ^3 | Styling (dark theme preserved) |
| react-router-dom | ^6 | Client-side routing |
| recharts | ^2 | Charts (MC histogram, equity curves, WF table) |
| @tanstack/react-query | ^5 | Server state + caching |

Font: IBM Plex Mono + IBM Plex Sans retained (Google Fonts CDN).

### Directory structure

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx              # Router setup
│   ├── api/                 # Typed fetch wrappers for all FastAPI endpoints
│   ├── components/
│   │   ├── auth/            # LoginPage, AuthCallback, ProtectedRoute
│   │   ├── dashboard/       # Terminal, Strategies, Execution, Activity (ported)
│   │   ├── risk/            # MonteCarloPanel, WalkForwardPanel
│   │   ├── profile/         # UserProfile, VirtualPortfolio
│   │   └── layout/          # Sidebar, Header, SessionClock
│   ├── hooks/
│   │   ├── useWebSocket.ts  # WS connection (replaces vanilla WS logic)
│   │   └── useAuth.ts       # Auth state, user context
│   └── types/               # API response types
├── index.html
├── vite.config.ts
├── tailwind.config.ts
└── tsconfig.json
```

Build output: `frontend/dist/` → served by FastAPI from `/static/` and `/`.

### Routes

| Path | Component | Auth Required |
|------|-----------|---------------|
| `/` | `LandingPage` | No |
| `/auth/callback` | `AuthCallback` | No |
| `/dashboard` | `Dashboard` | Yes |
| `/dashboard/risk` | `Dashboard` (Risk tab) | Yes |
| `/profile` | `ProfilePage` | Yes |

### Google OAuth flow (backend-driven)

```
Client                    FastAPI                    Google
  │                          │                          │
  │── GET /auth/google/login ─►                         │
  │                          │── redirect ─────────────►│
  │◄────────────────── 302 ──│                          │
  │── redirects to Google ──────────────────────────────►
  │◄── user approves ───────────────────────────────────│
  │    browser → GET /auth/google/callback?code=...     │
  │──────────────────────────►                          │
  │                          │── POST /token ──────────►│
  │                          │◄── id_token + profile ──│
  │                          │── upsert user in DB      │
  │                          │── issue JWT (httpOnly cookie, 7d)
  │◄── 302 /dashboard ───────│
```

JWT payload: `{ sub: user_id, email, name, exp }`  
Cookie: `vhe_session`, httpOnly, SameSite=Lax, Secure in prod.

### Backend additions

**`python/vhe/auth/`** (new package):
- `google_oauth.py` — `get_login_url()`, `exchange_code(code) -> GoogleProfile`
- `jwt_utils.py` — `create_token(user)`, `verify_token(token) -> UserClaims`
- `middleware.py` — FastAPI dependency `require_auth(request) -> UserClaims`

**`python/vhe/platform/server.py`** additions:
```python
GET  /auth/google/login      → redirect to Google
GET  /auth/google/callback   → exchange code, set cookie, redirect /dashboard
POST /auth/logout            → clear cookie
GET  /api/me                 → return current user (or 401)
PUT  /api/me/capital         → update virtual_capital_inr
```

**`python/vhe/storage/db.py`** addition:
```sql
CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    google_id           TEXT UNIQUE NOT NULL,
    email               TEXT UNIQUE NOT NULL,
    name                TEXT,
    virtual_capital_inr INTEGER NOT NULL DEFAULT 75000,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
```

### Virtual portfolio model

- On first login, user is created with `virtual_capital_inr = 75000`.
- Profile page allows changing this (₹25k–₹500k range).
- Dashboard shows a "Your Portfolio" widget: `₹75,000 → ₹X` using session P&L %.
  - Formula: `user_equity = virtual_capital × (1 + session_pnl_pct)`
- No per-user trade execution — the engine runs one shared session.

### New Python dependencies

```toml
authlib = "^1.3"
python-jose = {extras = ["cryptography"], version = "^3.3"}
```

### Environment variables (`.env`)

```
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
JWT_SECRET=...          # random 32-byte hex, generated at setup
JWT_ALGORITHM=HS256
```

---

## Testing strategy

| Layer | Approach |
|-------|----------|
| MC engine | Unit tests: deterministic RNG seed, verify VaR/Kelly formula correctness |
| Walk-forward | Unit tests: synthetic bar data, verify window counts and WFE calculation |
| Auth | FastAPI TestClient: mock Google OAuth response, verify JWT cookie set |
| Virtual portfolio | Unit test: P&L % formula, capital update endpoint |
| React components | None required (visual testing in browser is sufficient for portfolio) |

---

## Build sequence

```
Phase 1 — MC Engine (3 days)
  1. monte_carlo.py + tests
  2. POST /api/backtest/monte-carlo endpoint
  3. Risk tab + MC charts in vanilla JS dashboard

Phase 2 — Walk-Forward (3 days)
  4. optimiser.py + walk_forward.py + tests
  5. GET /api/backtest/walk-forward endpoint
  6. WF table + efficiency badge in Risk tab

Phase 3 — React + Auth (5 days)
  7. Scaffold Vite + React + Tailwind project in frontend/
  8. Port existing dashboard tabs to React components
  9. WebSocket hook (replaces vanilla WS)
  10. Google OAuth backend (auth package + DB migration)
  11. Auth routes + JWT middleware
  12. Landing page + login flow
  13. Profile page + virtual portfolio widget
  14. Risk tab (MC + WF) ported to React with Recharts
  15. Vite build integrated into FastAPI static serving
```

---

## Out of scope

- Per-user trade execution / isolated paper sessions
- Email/password auth (Google only)
- Mobile responsive design
- Production deployment / HTTPS / domain setup
- Real money integration
