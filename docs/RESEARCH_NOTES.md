# VHE Research Notes

This file captures implementation-relevant research findings. Keep it factual and update it whenever the strategy or live engine design changes.

## 2026-06-14: Dynamic Grid And Live Feed Architecture

### Dynamic Grid Strategy

Reference:

- Dynamic Grid Trading Strategy: From Zero Expectation to Market Outperformance, Kai-Yuan Chen, Kai-Hsin Chen, Jyh-Shing Roger Jang, 2025.
- URL: https://arxiv.org/abs/2506.11921

Useful takeaway:

- Fixed grid spacing can behave like a zero-expectation strategy under simple assumptions.
- The useful idea is dynamic resetting: grid placement should adapt when market state changes instead of leaving stale orders around old price centers.
- VHE implementation implication: grid plans should be versioned/resettable, keyed by fair value, ATR spacing, and regime state.

### Regime Switching

Reference:

- Trading VIX Futures under Mean Reversion with Regime Switching, Jiao Li, 2016.
- URL: https://arxiv.org/abs/1605.07945

Useful takeaway:

- Mean reversion behavior depends on regime, and transaction costs affect participation boundaries.
- VHE implementation implication: grid strategy must be gated by range regime and must cancel or stop adding levels when trend/crash regime is detected.

### Momentum And Regime Change

Reference:

- Slow Momentum with Fast Reversion: A Trading Strategy Using Deep Learning and Changepoint Detection, Wood, Roberts, Zohren, 2021.
- URL: https://arxiv.org/abs/2105.13727

Useful takeaway:

- Momentum models can underperform around trend reversals unless regime change is handled explicitly.
- VHE implementation implication: the momentum fallback should not be added as a naive breakout module; it needs its own regime gate and kill conditions.

### Kite Live Feed Constraints

Reference:

- Kite Connect WebSocket documentation.
- URL: https://kite.trade/docs/connect/v3/websocket/

Useful takeaway:

- WebSocket is the primary market quote channel for live data.
- Subscription modes are `ltp`, `quote`, and `full`; `full` includes market depth.
- One WebSocket connection supports up to 3000 instruments, and one API key supports up to 3 WebSocket connections.
- Quote packets are binary and prices are paise-scaled for Indian equities.

Reference:

- Kite Connect Orders documentation.
- URL: https://kite.trade/docs/connect/v3/orders/

Useful takeaway:

- Order placement returns an order id but does not guarantee exchange execution.
- VHE implementation implication: live execution must reconcile order state from order book, order history, trades, and asynchronous postbacks.

## Current Engineering Decisions

- Build strategy decisions against internal quote/order dataclasses, not broker JSON.
- Keep simulated feed and Kite feed behind the same protocol.
- Use the simulated feed in the UI by default so the platform can be developed without market hours or broker credentials.
- Do not place live orders until order reconciliation, kill switch, and paper/live parity are implemented.

## 2026-06-15: Instrument Master And Trading Console UI

### Kite Instrument Master

Reference:

- Kite Connect Market quotes and instruments documentation.
- URL: https://kite.trade/docs/connect/v3/market-quotes/

Useful takeaway:

- Live WebSocket subscriptions use numeric `instrument_token` values, not tradingsymbol strings.
- VHE implementation implication: every live session must start from a validated instrument master map before subscribing to quotes.
- The parser should filter by `exchange == NSE`, `segment == NSE`, and `instrument_type == EQ` for the v1 cash-equity scope.

### Platform UI Direction

Useful takeaway:

- The dashboard should behave like a control surface, not a landing page.
- The first screen should show feed health, mode, quote latency, spread, current grid spacing, reset reason, and generated strategy intents.
- Motion should clarify live updates: connection pulse, row flash on quote changes, and staged panel entry are useful; decorative motion is not.


## 2026-06-15: Kite WebSocket Packet Parser

### Live Feed Parser

Reference:

- Kite Connect WebSocket documentation.
- URL: https://kite.trade/docs/connect/v3/websocket/

Useful takeaway:

- WebSocket quote packets are binary and start with a packet count followed by packet lengths and packet payloads.
- `ltp` packets are compact and only provide token plus last traded price.
- `quote` packets add OHLC, volume, average price, and buy/sell quantity.
- `full` packets add timestamps and 5 levels of bid/ask market depth.
- VHE implementation implication: the parser must be isolated, unit-tested with constructed binary payloads, and converted into internal `LiveQuote` objects before strategy code sees the data.

### Instrument Cache

Reference:

- Kite Connect Market quotes and instruments documentation.
- URL: https://kite.trade/docs/connect/v3/market-quotes/

Useful takeaway:

- The instrument dump is a large gzipped CSV regenerated daily.
- VHE implementation implication: cache instruments by trading date, validate required columns, and derive the NSE equity token map before subscribing to live feed.

## 2026-06-15: Momentum Fallback And Paper Execution

### Momentum Fallback

Useful takeaway:

- Momentum should be a regime-specific fallback, not a continuously active strategy.
- VHE implementation implication: momentum is armed only during `TREND_UP` with bullish EMA stack, and it emits paper intents before any live execution path exists.

### Paper Execution

Useful takeaway:

- Before any broker order placement, strategy intents must flow through a paper broker that owns cash, positions, fills, fees, and mark-to-market state.
- VHE implementation implication: the dashboard should show positions/PnL from the paper broker, not from strategy-side assumptions.
