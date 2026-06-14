# Volatility Harvesting Engine

Personal research and paper-trading platform for Indian equity volatility harvesting. Current execution mode is paper/simulated only. Do not wire this to real orders until live reconciliation, failed-leg cleanup, exchange rules, and EOD square-off controls are implemented and tested.

## What Is Built

- Adaptive grid strategy gated by regime and fair value.
- Momentum fallback strategy for trend-up regimes.
- Pair spread strategy using log spread, hedge ratio, z-score entry, mean-reversion exit, and hard-stop close.
- Paper broker with cash, positions, fees, simulated shorts, and atomic multi-leg pair batches.
- Live-style dashboard with simulated quote feed, controls, paper positions, fills, activity log, pair spread monitor, and pair trade ledger.
- Kite instrument and binary WebSocket parsing foundations.
- Python tests plus Rust crate checks.

## Requirements

- Python 3.12+
- Rust toolchain for the Rust crates
- Git

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
pip install -e '.[dev]'
```

## Run The Dashboard

```bash
. .venv/bin/activate
.venv/bin/uvicorn vhe.platform.server:app --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

The server starts in paper mode with simulated quotes for `RELIANCE`, `HDFCBANK`, `TATAMOTORS`, and `BEL`.

## API Smoke Check

```bash
curl -s http://127.0.0.1:8765/api/state
```

You should see `connected: true`, `mode: paper`, quotes, strategy plans, portfolio, pair plans, and pair trades.

## Run Tests

```bash
. .venv/bin/activate
.venv/bin/python -m pytest python/tests
cargo check --manifest-path rust/Cargo.toml
```

## Useful Controls

- `Pause`: stops automation through the risk guard.
- `Resume`: clears pause/kill state.
- `Kill`: blocks new orders.
- `₹`: creates a demo paper fill.
- `R`: resets paper cash, positions, fills, and pair ledger.

## Current Safety Status

This is not live-order ready. The next required live-trading phases are:

- Broker order-state reconciliation from order book, trades, order history, and postbacks.
- Failed-leg cleanup for pair orders because real exchanges do not provide atomic two-leg equity execution.
- Intraday short validation and end-of-day square-off rules for Indian cash equities.
- Persistent audit log and restart recovery.
- Walk-forward backtesting before any real capital.

## Project Docs

- `docs/VHE_RESEARCH_AND_BUILD_PLAN.md`: original research and build plan.
- `docs/RESEARCH_NOTES.md`: implementation-relevant research notes and decisions.
