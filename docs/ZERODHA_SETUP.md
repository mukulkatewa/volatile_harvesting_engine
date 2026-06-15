# Zerodha Kite Connect Setup for VHE

This guide explains how VHE gets **real NSE/BSE market data** and how **real order placement** will work. Read this before putting money on the platform.

---

## The short answer

| What you want | How VHE does it | Direct NSE/BSE? |
|---------------|-----------------|-----------------|
| Live quotes (LTP, OHLC, depth) | **Zerodha Kite WebSocket** | ❌ No — retail cannot connect to exchange feeds directly |
| Place/cancel orders | **Zerodha Kite REST API** (Phase 2) | ❌ No — orders go through your broker |
| End-of-day history | NSE bhavcopy + Kite historical API | NSE bhavcopy is free; intraday candles via Kite |

**You need a Zerodha account with Kite Connect enabled.** There is no legal retail path to bypass the broker and connect straight to NSE/BSE for live trading.

BSE symbols are also available through Kite if you subscribe to BSE instrument tokens — v1 focuses on **NSE cash equities**.

---

## Architecture: data vs execution

```text
┌─────────────┐     WebSocket (quotes)      ┌──────────────────┐
│  NSE / BSE  │ ◄──── Zerodha servers ─────►│  VHE Platform    │
└─────────────┘                             │  (your machine)  │
                                            │                  │
┌─────────────┐     REST (orders/fills)     │  Strategy Engine │
│  Exchange   │ ◄──── Zerodha Kite API ────►│  Risk Guard      │
└─────────────┘                             │  Dashboard       │
                                            └──────────────────┘
```

**Phase 1 (now):** Live quotes via Kite WebSocket → strategies → paper broker.  
**Phase 2 (next):** Same quotes, but approved intents go to `KiteBrokerAdapter` → real MIS orders on your Zerodha account.

---

## Step 1 — Create a Kite Connect app

1. Log in to [Kite Connect developer console](https://developers.kite.trade/).
2. Create an app (personal use is fine).
3. Note your **API Key** and **API Secret**.
4. Set redirect URL to `http://127.0.0.1` (or your chosen callback).

---

## Step 2 — Set credentials (daily)

Access tokens expire at **~6 AM IST** each day. You must refresh daily.

### Option A: `.env` file (recommended)

```bash
cp .env.example .env
```

Edit `.env`:

```env
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
KITE_ACCESS_TOKEN=your_daily_access_token
VHE_LIVE_CONFIG=live_kite.yaml
```

VHE loads `.env` automatically when you start the server or run `vhe` CLI commands.

### Option B: export in terminal

```bash
export KITE_API_KEY="your_api_key"
export KITE_API_SECRET="your_api_secret"
```

Then get today's access token:

```bash
# Print login URL, open in browser, login with Zerodha credentials
vhe kite-login-url

# After redirect, copy request_token from URL (?request_token=...)
vhe kite-exchange-token --request-token YOUR_REQUEST_TOKEN

# Put printed token in .env as KITE_ACCESS_TOKEN=...
```

Never commit `.env` — it is gitignored.

---

## Step 3 — Cache instrument master (daily, before market open)

Kite WebSocket subscribes by numeric `instrument_token`, not symbol name.

```bash
# Download today's instrument CSV using your access token
vhe kite-download-instruments --cache-dir data/raw/kite

# Verify token map for your symbols
vhe kite-token-map --date 2026-06-15 --cache-dir data/raw/kite
```

---

## Step 4 — Enable live Kite feed in VHE

1. In `configs/strategies.yaml`, set:
   ```yaml
   feed:
     source: kite
   ```

2. Start the platform with Kite live config:
   ```bash
   # In .env: VHE_LIVE_CONFIG=live_kite.yaml
   source .venv/bin/activate
   uvicorn vhe.platform.server:app --host 127.0.0.1 --port 8765 --app-dir python
   ```

3. Open the dashboard — **Feed Health** should show `KITE` during market hours (09:15–15:30 IST).

If credentials or instrument cache are missing, VHE **falls back to simulated feed** and logs a warning (configurable via `feed.fallback_to_simulated`).

---

## How real trades will work (Phase 2 preview)

When Phase 2 ships, the flow will be:

```text
Strategy intent (BUY RELIANCE 10 @ 2850 LIMIT)
        ↓
RiskGuard (capital, exposure, daily loss, kill switch)
        ↓
KiteBrokerAdapter.place_order(
    exchange=NSE,
    tradingsymbol=RELIANCE,
    transaction_type=BUY,
    quantity=10,
    product=MIS,          # intraday
    order_type=LIMIT,
    price=2850,
    tag="vhe_grid_l2"
)
        ↓
OrderStateMachine tracks: SENT → ACK → PARTIAL_FILL → FILLED
        ↓
Reconciler polls kite.orders() + kite.trades() every 5s
        ↓
Position store updated → dashboard shows real PnL
```

**Safety rules already in place:**
- Kill switch on stale quotes (>3s)
- Daily loss limit
- Paper mode until you explicitly set `mode: live` in config
- Forced square-off target: 15:10 IST

**Zerodha limits:** ~3 orders/second for individual accounts — plenty for our grid strategy (max ~5 levels × 2 symbols).

---

## SEBI / compliance note

Personal API trading on your own Zerodha account with **<10 orders/second** does not require exchange algo registration. Do not use this platform to trade others' money or sell signals without proper registration.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Feed shows SIMULATED | Check `feed.source`, `KITE_*` env vars, market hours |
| Missing instrument tokens | Run `vhe kite-download-instruments` |
| Token expired | Re-run `kite-login-url` + `kite-exchange-token` |
| Stale quote kill switch | Check internet; Kite WS reconnects automatically |
| No quotes outside 09:15–15:30 | Normal — NSE cash market closed |

---

## References

- [Kite Connect v3 docs](https://kite.trade/docs/connect/v3/)
- [WebSocket market data](https://kite.trade/docs/connect/v3/websocket/)
- [Placing orders](https://kite.trade/docs/connect/v3/orders/)
- [VHE Strategy Plan](./VHE_STRATEGY_RESEARCH_AND_LIVE_PLATFORM_PLAN.md)
