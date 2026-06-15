# Volatility Harvesting Engine

Personal systematic trading platform for Indian equity volatility harvesting (NSE cash, Zerodha Kite).

**Current mode:** Paper trading with simulated or live Kite quotes. Real order placement ships in Phase 2.

## Quick start (UI + all services)

VHE runs as **one process** — the dashboard server also runs the quote feed, strategies, risk guard, and paper broker. There is no separate worker to start.

```bash
# 1. Clone and enter project
cd volatile_harvesting_engine

# 2. Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Secrets (optional for simulated mode; required for live Kite feed)
cp .env.example .env
# Edit .env — see "How to get Zerodha keys" below

# 4. Start platform (simulated feed by default)
uvicorn vhe.platform.server:app --host 127.0.0.1 --port 8765 --app-dir python
```

Open: **http://127.0.0.1:8765**

API health check:

```bash
curl -s http://127.0.0.1:8765/api/state | head -c 200
```

---

## Where to put API keys

| File | Purpose |
|------|---------|
| `.env.example` | Template — safe to commit, no real secrets |
| `.env` | **Your real keys** — copy from example, never commit |

```bash
cp .env.example .env
```

Edit `.env`:

```env
KITE_API_KEY=abc123
KITE_API_SECRET=your_secret
KITE_ACCESS_TOKEN=daily_token_from_login
VHE_LIVE_CONFIG=live_kite.yaml
```

The server and `vhe` CLI load `.env` automatically on startup.

---

## How to get Zerodha Kite keys

### One-time setup

1. Go to **[Kite Connect Developer Console](https://developers.kite.trade/)**
2. Sign in with your **Zerodha** account
3. **Create new app** → note:
   - **API Key** → `KITE_API_KEY`
   - **API Secret** → `KITE_API_SECRET`
4. Set **Redirect URL** to `http://127.0.0.1`

### Every trading day (before 9:15 AM IST)

Access token expires daily (~6 AM IST). Refresh it:

```bash
source .venv/bin/activate

# Opens login URL — sign in with Zerodha PIN + 2FA
vhe kite-login-url

# After redirect, copy request_token from browser URL bar
vhe kite-exchange-token --request-token PASTE_TOKEN_HERE

# Put the printed access_token into .env:
# KITE_ACCESS_TOKEN=...
```

### Before live feed (instrument cache)

```bash
vhe kite-download-instruments --cache-dir data/raw/kite
```

### Enable live NSE quotes

1. In `configs/strategies.yaml` set `feed.source: kite`
2. In `.env` set `VHE_LIVE_CONFIG=live_kite.yaml`
3. Restart the server during market hours (09:15–15:30 IST)

Full guide: [`docs/ZERODHA_SETUP.md`](docs/ZERODHA_SETUP.md)

---

## What runs when you start the server

```text
uvicorn vhe.platform.server:app
        │
        ├── FastAPI dashboard (UI + WebSocket)
        ├── Quote feed (simulated OR Kite WebSocket)
        ├── Indicator + regime engine
        ├── Grid / momentum / pair strategies
        ├── Risk guard + paper broker
        └── SQLite audit log (data/vhe_platform.db)
```

---

## Other CLI commands (optional, not always running)

```bash
# NSE end-of-day data (evening, for scanner/backtest)
vhe data-ingest-nse --date 2026-06-15

# Rank symbols for tomorrow's watchlist
vhe scan-daily --as-of 2026-06-15

# Verify instrument tokens
vhe kite-token-map --date 2026-06-15 --cache-dir data/raw/kite
```

---

## Run tests

```bash
pytest python/tests
cargo check --manifest-path rust/Cargo.toml
```

---

## Dashboard controls

| Button | Action |
|--------|--------|
| Pause | Stop new orders via risk guard |
| Resume | Clear pause/kill |
| Kill | Emergency stop |
| Demo | One demo paper fill |
| Reset | Reset paper account |

---

## Project docs

- [`docs/ZERODHA_SETUP.md`](docs/ZERODHA_SETUP.md) — live feed + future live orders
- [`docs/VHE_STRATEGY_RESEARCH_AND_LIVE_PLATFORM_PLAN.md`](docs/VHE_STRATEGY_RESEARCH_AND_LIVE_PLATFORM_PLAN.md) — strategy + phases
- [`docs/VHE_RESEARCH_AND_BUILD_PLAN.md`](docs/VHE_RESEARCH_AND_BUILD_PLAN.md) — original build plan
