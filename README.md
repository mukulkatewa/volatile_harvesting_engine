# Volatility Harvesting Engine (VHE)

Personal systematic trading platform for Indian NSE cash equities — volatility harvesting via **dynamic grid**, **pair spread**, and **momentum** sleeves, with a live dashboard, paper broker, and Zerodha Kite integration path.

**Current setup (default):** Paper trading on **₹75,000** simulated capital, **yfinance** delayed quotes (~15 min), **12 large-cap NSE symbols**, aggressive paper fill mode for strategy validation.

---

## What this project does

VHE is a single-process trading terminal:

1. **Ingests quotes** (yfinance free tier, simulated, or Kite WebSocket when paid Connect is enabled)
2. **Computes indicators** (EMA, ATR, ADX) and classifies **market regime** (RANGE / TREND / CRASH)
3. **Runs strategies** automatically on each tick — no manual order clicks required
4. **Routes orders** through a **risk guard** → **paper broker** (or Kite in `live` mode)
5. **Streams state** to a dark trading UI at `http://127.0.0.1:8765`

```text
uvicorn vhe.platform.server:app
        │
        ├── FastAPI dashboard (UI + WebSocket)
        ├── Quote feed (yfinance / simulated / Kite)
        ├── Indicator + regime engine
        ├── Grid / momentum / pair strategies
        ├── Risk guard + paper broker
        └── SQLite audit log (data/vhe_platform.db)
```

---

## Quick start

```bash
git clone https://github.com/mukulkatewa/volatile_harvesting_engine.git
cd volatile_harvesting_engine

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Optional: add Zerodha keys for future live orders (not required for paper + yfinance)

uvicorn vhe.platform.server:app --host 127.0.0.1 --port 8765 --app-dir python
```

Open **http://127.0.0.1:8765** and hard-refresh (`Ctrl+Shift+R`) after updates.

Health check:

```bash
curl -s http://127.0.0.1:8765/api/state | python3 -m json.tool | head
```

---

## Configuration

### Environment (`.env`)

| Variable | Purpose |
|----------|---------|
| `KITE_API_KEY` | Zerodha app key (optional for free paper mode) |
| `KITE_API_SECRET` | Used for daily token exchange |
| `KITE_ACCESS_TOKEN` | Refreshed every morning (~6 AM IST expiry) |
| `VHE_LIVE_CONFIG` | Which live config YAML to load (see below) |

```bash
cp .env.example .env
```

### Live config profiles (`configs/`)

| File | Mode | Feed | Orders | When to use |
|------|------|------|--------|-------------|
| `live_free.yaml` | paper | yfinance in `strategies.yaml` | Paper | **Default free tier** — no paid Kite Connect |
| `live_paper.yaml` | paper | simulated | Paper | Offline / no network |
| `live_kite.yaml` | paper | kite | Paper | Paid Connect (~₹500/mo) for live quotes |
| `live_live.yaml` | live | kite | Real MIS via Kite | Production (after validation gates) |

Set in `.env`:

```env
VHE_LIVE_CONFIG=live_free.yaml
```

### Strategy config (`configs/strategies.yaml`)

| Section | What it controls |
|---------|------------------|
| `feed.symbols` | 12-stock watchlist (RELIANCE, HDFCBANK, ICICIBANK, INFY, TCS, SBIN, BHARTIARTL, ITC, LT, KOTAKBANK, BEL, TMPV) |
| `feed.source` | `yfinance` (free), `simulated`, or `kite` |
| `grid.*` | ATR grid spacing, seed deploy %, level sizing |
| `pair.*` | RELIANCE/HDFCBANK log-spread mean/std and z-score bands |
| `capital.*` | Bucket split: grid 70%, pair 10%, momentum 10%, reserve 10% |

**Paper stress-test settings** (in `live_free.yaml` + `strategies.yaml`):

- ₹75,000 paper capital, up to 5 active grid symbols
- 40% seed deploy on RANGE regime (immediate paper entry)
- Aggressive limit fills + full order quantity in paper broker
- 92% gross exposure cap, 28% per-symbol cap

---

## Dashboard

### Sidebar tabs

| Tab | Shows |
|-----|--------|
| **Terminal** | Equity, risk/exposure, capital buckets, quotes, positions |
| **Strategies** | Grid buy levels, momentum state, pair z-score monitor |
| **Execution** | Paper fill tape + pair ledger |
| **Activity** | Multi-session paper stats, strategy health, sentiment roadmap, event stream |

### Paper session stats (Activity tab)

- **Multi-session P&L** — cumulative across closed IST trading days
- **Today** — live session P&L, fills, minutes active, max deploy %
- **Strategy health** — automated verdict (`too_early`, `deployed`, `promising`, …)
- **Session table** — one row per paper session (auto-closes at 15:30 IST; Reset starts `YYYY-MM-DD-r2`)

API: `GET /api/stats/paper`

### News / sentiment (planned)

Not wired yet. **CRASH regime** covers sharp price stress today. Planned overlay: ingest news → per-symbol sentiment score → risk guard pauses or sizes down before grid submits orders.

### Header controls

| Button | Action |
|--------|--------|
| Pause | Stop new orders |
| Resume | Clear pause / kill |
| Kill | Emergency stop |
| Demo | One manual paper fill |
| Reset | Fresh ₹75k paper account (clears positions, grid seed state, risk flags) |

### Risk card meanings

| Label | Meaning |
|-------|---------|
| **Clear** | Room to deploy more capital |
| **Deploying** | >65% of exposure cap used |
| **At Cap** | Gross exposure limit hit — grid pauses new buys until sells |

---

## Strategies (how money is made)

See [`docs/HOW_WE_MAKE_MONEY.md`](docs/HOW_WE_MAKE_MONEY.md) for full quant detail.

| Sleeve | When active | Edge |
|--------|-------------|------|
| **Dynamic ATR Grid** | RANGE (ADX low) | Buy below fair value in ATR-spaced levels, sell at mean |
| **Pair Spread** | RELIANCE vs HDFCBANK z-score | Market-neutral mean reversion on log spread |
| **Momentum** | TREND_UP | Continuation when grid is off |
| **Cash** | CRASH / kill switch | No new risk |

**Automatic execution:** Keep the server running during market hours (09:15–15:10 IST). The engine places paper orders when regime + price conditions are met. No button clicks needed except optional Reset/Demo.

**After market close (15:30 IST):** The feed stays on but switches to **monitoring mode** — no new orders, last available yfinance prices shown, dashboard shows **MARKET CLOSED**. Force square-off runs from **15:10** (`force_exit_time` in live config).

**Pair spread calibration:** `pair.mean` and `pair.std` must match the log-spread `log(RELIANCE) - log(HDFCBANK)`. Old values (`mean: -0.04`, `std: 0.006`) produced z≈94 and permanent STOP. Current values are calibrated from 6 months of daily NSE closes (~`mean: 0.5001`, `std: 0.0656`).

Recalibrate anytime:

```bash
source .venv/bin/activate
python3 - <<'PY'
import math, yfinance as yf, pandas as pd
a, b = "RELIANCE.NS", "HDFCBANK.NS"
d = yf.download([a, b], period="6mo", interval="1d", auto_adjust=True, progress=False)
s = pd.DataFrame({"a": d["Close"][a], "b": d["Close"][b]}).dropna()
spread = s["a"].map(math.log) - s["b"].map(math.log)
print(f"mean: {spread.mean():.4f}")
print(f"std:  {spread.std(ddof=1):.4f}")
print(f"current z: {(spread.iloc[-1]-spread.mean())/spread.std(ddof=1):.2f}")
PY
```

---

## Zerodha Kite setup

### One-time

1. [Kite Connect Developer Console](https://developers.kite.trade/) → create app
2. Set redirect URL to `http://127.0.0.1`
3. Copy API key + secret into `.env`

### Every trading day

```bash
vhe kite-login-url
vhe kite-exchange-token --request-token PASTE_FROM_REDIRECT_URL
# Update KITE_ACCESS_TOKEN in .env
vhe kite-download-instruments --cache-dir data/raw/kite
```

### Live quotes (paid Connect)

1. `configs/strategies.yaml` → `feed.source: kite`
2. `.env` → `VHE_LIVE_CONFIG=live_kite.yaml`
3. Restart server during 09:15–15:30 IST

Full guide: [`docs/ZERODHA_SETUP.md`](docs/ZERODHA_SETUP.md)

**Free tier limitation:** Kite Personal API can place orders but does **not** include live WebSocket quotes. Use **yfinance** for free delayed prices, or pay for Kite Connect for live data.

---

## Daily workflow (paper testing)

```text
09:00  Start server (uvicorn command above)
09:25  Watch Terminal — REGIME: RANGE, GRID: ACTIVE
       Strategies tab — buy levels vs LTP
       Execution tab — fills as grid trades
15:10  Force exit time (config) — square-off logic
18:00  Optional: vhe scan-daily for tomorrow's universe
```

---

## CLI commands

```bash
vhe data-ingest-nse --date 2026-06-15      # NSE bhavcopy
vhe scan-daily --as-of 2026-06-15          # Symbol scanner
vhe kite-login-url                         # Zerodha login
vhe kite-exchange-token --request-token …  # Daily token
vhe kite-download-instruments              # Instrument master
vhe kite-token-map --date 2026-06-15       # Token lookup
```

---

## Tests

```bash
pytest python/tests
```

67 tests covering feed, paper broker, risk guard, grid, pair spread, platform state, and runtime.

---

## Project docs

| Doc | Topic |
|-----|--------|
| [`docs/HOW_WE_MAKE_MONEY.md`](docs/HOW_WE_MAKE_MONEY.md) | Strategy economics and validation gates |
| [`docs/ZERODHA_SETUP.md`](docs/ZERODHA_SETUP.md) | Kite auth, feeds, live orders |
| [`docs/VHE_STRATEGY_RESEARCH_AND_LIVE_PLATFORM_PLAN.md`](docs/VHE_STRATEGY_RESEARCH_AND_LIVE_PLATFORM_PLAN.md) | Phase roadmap |
| [`docs/VHE_RESEARCH_AND_BUILD_PLAN.md`](docs/VHE_RESEARCH_AND_BUILD_PLAN.md) | Original research plan |

---

## Roadmap / not yet production

- [ ] 60-session paper/live parity before scaling capital
- [ ] Live fill reconciliation from Kite → dashboard positions
- [ ] Walk-forward backtest harness on intraday bars
- [ ] Paid Kite Connect for production-grade quote latency

**Do not switch to `live_live.yaml` with real money until validation gates in `HOW_WE_MAKE_MONEY.md` are met.**
