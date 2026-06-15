# How VHE Makes Money (Quant Reality)

This is not hype. This is how a prop-desk would explain the edge, when it activates, and what has to be true before you put real capital in.

---

## The core idea

VHE does **not** predict the market direction every day. It runs **conditional strategies**:

| Strategy | Market condition | What you earn | Risk |
|----------|------------------|---------------|------|
| **Adaptive ATR Grid** | RANGE (ADX < 20) | Small wins from intraday mean reversion | Trend day losses if regime wrong |
| **Pair Spread** | Cointegrated pair, \|z\| > 1.5 | Market-neutral reversion on spread | Cointegration break |
| **Momentum** | TREND_UP confirmed | Continuation after EMA stack | Whipsaw at trend end |

**Cash / kill switch** when regime is CRASH or feed is stale.

---

## Sleeve 1: Adaptive ATR Grid (primary PnL)

### Edge
Large-cap NSE names oscillate intraday around fair value (EMA50) on range days. You buy **below** fair value in ATR-spaced levels, sell back at mean.

### Example (₹25k account)
- Grid bucket: ₹12,500
- 2 symbols → ~₹2,250/symbol, 5 levels → ~₹450/level
- Stock at ₹1,000 → ~0 shares at level (integer rounding) — **this is why you scale capital to ₹50k–₹1L for meaningful grid depth**

### When it makes money
- ADX < 20 (range)
- Price dips to grid levels then reverts to fair value
- Multiple round-trips per session

### When it loses
- Trend day (grid keeps buying into fall)
- **Mitigation:** regime gate turns grid OFF in TREND_DOWN/CRASH

### Research basis
Fixed grids ≈ zero expectancy (Chen et al. 2025). VHE uses **dynamic reset + regime gate + finite depth**.

---

## Sleeve 2: Pair Spread (market-neutral)

### Edge
Two cointegrated stocks (e.g. HDFCBANK/KOTAKBANK) move together. When spread deviates (z-score > 1.5), you long underperformer / short outperformer intraday, exit near mean.

### When it makes money
- Spread mean-reverts within session
- Both legs liquid, tight spreads

### When it loses
- Sector shock breaks correlation
- **Mitigation:** hard stop at z = 3.0, EOD square-off

### Indian market note
Cash shorts are **intraday only** (MIS). Both legs must fill — Phase 2 reconciliation handles failed legs.

---

## Sleeve 3: Momentum fallback

### Edge
When grid is OFF and trend is confirmed (EMA20 > EMA50, ADX > 25), capture short continuation with ATR stop/target.

### Role
Prevents forcing grid in trends. Smaller capital bucket (15%).

---

## Capital allocation (₹25,000 v1)

| Bucket | Amount | Purpose |
|--------|--------|---------|
| Grid | ₹12,500 | Primary harvester |
| Pair | ₹6,250 | Neutral alpha |
| Momentum | ₹3,750 | Trend capture |
| Reserve | ₹2,500 | Buffer, never deployed |

---

## What you need before real money

### Phase 2 (now) — Order execution
- [ ] KiteBrokerAdapter places MIS limit orders
- [ ] Order reconciliation every 5s
- [ ] Failed-leg cleanup for pairs
- [ ] `mode: live` in `configs/live_live.yaml`

### Validation gates (non-negotiable)
- [ ] 60 sessions paper/live parity
- [ ] Max drawdown < 3% over 60 sessions
- [ ] Zero reconciliation mismatches
- [ ] Trade only 09:25–14:45, flat by 15:10

### Realistic expectations
- Academic NSE pair studies: ~15–25% annualized after costs (not 100%+)
- Grid: higher variance, needs range days
- **Start with ₹25k to test plumbing, scale to ₹50k–₹1L only after gates pass**

---

## Daily workflow to actually trade

```text
06:00  Refresh KITE_ACCESS_TOKEN in .env
06:05  vhe kite-download-instruments
09:00  Start platform (live_kite.yaml + feed.source=kite)
09:25  Strategies arm (after opening volatility settles)
09:25–14:45  Automated entries per regime
15:10  Forced square-off
18:00  vhe scan-daily for tomorrow's universe
```

---

## What the dashboard "Active Edge" panel shows

- **Regime:** RANGE → grid armed; TREND_UP → momentum; CRASH → cash
- **Grid ACTIVE:** buy levels placed below fair value
- **Pair WAIT:** watching z-score; enters at ±1.5

If equity shows ₹25,000 cash and no positions — **that's correct before first fill**. Strategies only trade when price hits grid levels or z-score thresholds.

---

See also: [ZERODHA_SETUP.md](./ZERODHA_SETUP.md), [VHE_STRATEGY_RESEARCH_AND_LIVE_PLATFORM_PLAN.md](./VHE_STRATEGY_RESEARCH_AND_LIVE_PLATFORM_PLAN.md)
