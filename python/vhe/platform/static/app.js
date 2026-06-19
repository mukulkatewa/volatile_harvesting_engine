const fmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const moneyCompact = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", notation: "compact", maximumFractionDigits: 1 });

const seenPrices = new Map();
const quoteRows = new Map();
const tickerChips = new Map();
let wsOpen = false;
let pendingPayload = null;
let renderFrame = null;
let lastCapitalKey = "";
let lastServerTimeMs = null;
let lastPayload = null;

const controls = [
  ["pause-button", "/api/control/pause"],
  ["resume-button", "/api/control/resume"],
  ["kill-button", "/api/control/kill"],
  ["demo-fill-button", "/api/control/demo-fill"],
  ["reset-paper-button", "/api/control/reset-paper"],
  ["sentiment-refresh-button", "/api/sentiment/refresh"],
];

document.addEventListener("DOMContentLoaded", () => {
  for (const [id, endpoint] of controls) {
    const button = document.getElementById(id);
    if (button) button.addEventListener("click", () => postControl(endpoint));
  }

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      switchView(button.dataset.panel);
    });
  });

  tickClock();
  setInterval(tickClock, 1000);
  setInterval(tickQuoteAges, 1000);
  connect();
  setInterval(pollState, 3000);
});

function scheduleRender(payload) {
  pendingPayload = payload;
  if (renderFrame !== null) return;
  renderFrame = requestAnimationFrame(() => {
    renderFrame = null;
    if (pendingPayload) render(pendingPayload);
    pendingPayload = null;
  });
}

function tickClock() {
  const now = new Date();
  const ist = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
  const pad = (n) => String(n).padStart(2, "0");
  document.getElementById("ist-clock").textContent = `${pad(ist.getHours())}:${pad(ist.getMinutes())}:${pad(ist.getSeconds())}`;
}

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws/state`);

  socket.onopen = () => {
    wsOpen = true;
    renderConnection(true);
  };
  socket.onmessage = (event) => scheduleRender(JSON.parse(event.data));
  socket.onclose = () => {
    wsOpen = false;
    renderConnection(false);
    setTimeout(connect, 1200);
  };
}

function render(payload) {
  lastPayload = payload;
  if (payload.server_time) {
    lastServerTimeMs = Date.parse(payload.server_time);
  }
  const portfolio = payload.portfolio || {};
  const capitalTotal = payload.capital?.total;
  renderConnection(payload.connected);
  document.getElementById("phase-label").textContent = payload.phase || "2";
  document.getElementById("mode-label").textContent = titleCase(payload.mode || "paper");
  document.getElementById("source-label").textContent = payload.source || "simulated";
  const equity = portfolio.equity ?? portfolio.cash ?? capitalTotal ?? 0;
  document.getElementById("equity").textContent = money.format(equity);
  renderPortfolioBreakdown(portfolio);
  renderRisk(payload.controls || {}, portfolio);
  renderCapital(payload.capital || {});
  renderStrategyStatus(payload.strategy_status || {});
  renderCommandStrip(payload);
  renderFeedHealth(payload.feed_health || {}, payload.source);
  renderMarketSession(payload.market_session || {});
  renderBars(payload.bars || {});
  renderTicker(payload.quotes || {}, payload.regimes || {});
  renderQuotes(payload.quotes || {}, payload.regimes || {}, payload.indicators || {});
  renderStrategies(payload.plans || {}, payload.momentum_plans || {}, payload.regimes || {});
  renderPairs(payload.pair_plans || {});
  renderPairTrades(payload.pair_trades || []);
  renderFills(payload.fills?.length ? payload.fills : payload.portfolio?.fills || []);
  renderPositions(portfolio.positions || []);
  renderPaperStats(payload.paper_stats || {});
  renderSentiment(payload.sentiment || payload.paper_stats?.sentiment || {});
  renderEvents(payload.events || []);
}

function switchView(viewId) {
  if (!viewId) return;
  document.querySelectorAll(".nav-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.panel === viewId);
  });
  document.querySelectorAll(".view").forEach((el) => {
    el.classList.toggle("active", el.dataset.view === viewId);
  });
  document.querySelector(".main")?.scrollTo({ top: 0, behavior: "smooth" });
}

async function pollState() {
  const quoteCount = document.getElementById("quotes-body")?.children.length || 0;
  if (wsOpen && quoteCount > 0) return;
  try {
    const response = await fetch("/api/state");
    if (response.ok) scheduleRender(await response.json());
  } catch {
    // ignore transient network errors
  }
}

async function postControl(endpoint) {
  const response = await fetch(endpoint, { method: "POST" });
  if (response.ok) scheduleRender(await response.json());
}

const RISK_LABELS = {
  gross_exposure_limit: "At Cap",
  symbol_exposure_limit: "Symbol Cap",
  daily_loss_limit: "Loss Limit",
  symbol_quantity_limit: "Qty Limit",
  kill_switch_active: "Killed",
  automation_paused: "Paused",
  sentiment_halt: "Sentiment Halt",
};

function renderRisk(controls, portfolio = {}) {
  const label = document.getElementById("risk-label");
  const sub = document.getElementById("risk-sub");
  const paused = controls.automation_paused;
  const killed = controls.kill_switch;
  const reject = controls.last_risk_reject;
  const exposurePct = Number(portfolio.gross_exposure_pct ?? 0);
  const maxExposurePct = Number((portfolio.max_gross_exposure_pct ?? 0.85) * 100);

  let text = "Clear";
  let klass = "buy";
  if (killed) {
    text = "Killed";
    klass = "sell";
  } else if (paused) {
    text = "Paused";
    klass = "stale";
  } else if (exposurePct >= maxExposurePct - 0.5) {
    text = "At Cap";
    klass = "stale";
  } else if (reject === "symbol_exposure_limit" && exposurePct < maxExposurePct * 0.85) {
    text = exposurePct >= maxExposurePct * 0.65 ? "Deploying" : "Clear";
    klass = exposurePct >= maxExposurePct * 0.65 ? "buy" : "buy";
  } else if (reject && reject !== "gross_exposure_limit") {
    text = RISK_LABELS[reject] || "Guarded";
    klass = "stale";
  } else if (exposurePct >= maxExposurePct * 0.65) {
    text = "Deploying";
    klass = "buy";
  }

  label.textContent = text;
  label.className = "risk-pill";
  label.classList.add(klass);
  if (sub) {
    sub.textContent = `Exposure ${exposurePct.toFixed(0)}% of ${maxExposurePct.toFixed(0)}% cap`;
  }
}

function renderConnection(connected) {
  const phase = lastPayload?.market_session?.phase;
  const closed = phase === "closed" || phase === "pre_market";
  document.getElementById("connection-dot").classList.toggle("live", connected);
  if (connected && closed) {
    document.getElementById("connection-label").textContent = "Feed On (Market Closed)";
  } else {
    document.getElementById("connection-label").textContent = connected ? "Live Feed" : "Disconnected";
  }
}

function renderMarketSession(session) {
  const badge = document.getElementById("session-badge");
  if (!badge) return;
  const phase = session.phase || "open";
  const labels = {
    open: "SESSION OPEN",
    force_exit: "SQUARE-OFF",
    closed: "MARKET CLOSED",
    pre_market: "PRE-MARKET",
  };
  badge.textContent = labels[phase] || phase.toUpperCase();
  badge.className = `session-badge ${phase}`;
}

function staleThresholdMs(source, health) {
  if (health?.market_closed) return 120_000;
  if (source === "yfinance") return 30_000;
  return 3_000;
}

function tickQuoteAges() {
  if (!lastPayload?.quotes) return;
  const source = lastPayload.source;
  const threshold = staleThresholdMs(source, lastPayload.feed_health);
  for (const quote of Object.values(lastPayload.quotes)) {
    const row = quoteRows.get(quote.symbol);
    if (!row) continue;
    const ageMs = quoteAgeMs(quote);
    const ageEl = row.querySelector(".age");
    if (!ageEl) continue;
    ageEl.textContent = `${ageMs}ms`;
    ageEl.className = `mono age ${ageMs > threshold ? "stale" : ""}`;
  }
}

function renderPortfolioBreakdown(portfolio) {
  const initialCash = Number(portfolio.initial_cash ?? 0);
  const cash = Number(portfolio.cash ?? 0);
  const equity = Number(portfolio.equity ?? cash);
  const invested = Number(portfolio.gross_exposure ?? Math.max(equity - cash, 0));
  const unrealized = Number(portfolio.unrealized_pnl ?? 0);
  const realized = Number(portfolio.realized_pnl ?? 0);
  const fees = Number(portfolio.fees_paid ?? 0);
  const totalPnl = initialCash > 0 ? equity - initialCash : unrealized + realized;

  document.getElementById("cash").textContent = money.format(cash);
  document.getElementById("invested").textContent = money.format(invested);
  document.getElementById("initial-cash").textContent = money.format(initialCash);
  document.getElementById("fees-paid").textContent = money.format(fees);
  setPnl("unrealized-pnl", unrealized);
  setPnl("realized-pnl", realized);
  setPnl("total-pnl", totalPnl);
}

function quoteAgeMs(quote) {
  if (quote.timestamp) {
    const ts = Date.parse(quote.timestamp);
    if (!Number.isNaN(ts)) {
      return Math.max(0, Date.now() - ts);
    }
  }
  return Math.max(0, Number(quote.age_ms) || 0);
}

function setPnl(id, value) {
  const target = document.getElementById(id);
  target.textContent = money.format(value);
  target.classList.toggle("buy", value >= 0);
  target.classList.toggle("sell", value < 0);
}

function renderFeedHealth(health, source) {
  const label = document.getElementById("feed-source-label");
  const tickAge = document.getElementById("feed-tick-age");
  const staleLabel = document.getElementById("feed-stale-label");
  const feedSource = source || health.source || "—";
  const online = feedSource === "kite" && health.connected !== false;
  const delayed = feedSource === "yfinance" && health.connected !== false;
  const closed = health.market_closed;
  label.textContent = closed
    ? "CLOSED — LAST CLOSE"
    : online
      ? feedSource.toUpperCase()
      : delayed
        ? "YFINANCE (~15M DELAY)"
        : feedSource === "kite"
          ? "KITE OFFLINE"
          : feedSource.toUpperCase();
  label.className = `feed-source ${closed ? "stale" : online || delayed ? "buy" : "stale"}`;
  const age = health.last_tick_age_ms;
  const threshold = staleThresholdMs(feedSource, health);
  tickAge.textContent = age == null ? "—" : `${age}ms`;
  tickAge.className = age != null && age > threshold ? "sell" : "buy";
  const stale = health.stale_symbols || [];
  if (closed) {
    staleLabel.textContent = "Session closed — prices are last available";
    staleLabel.className = "muted";
  } else if (health.is_stale) {
    staleLabel.textContent = stale.length ? `Stale: ${stale.join(", ")}` : "Feed stale";
    staleLabel.className = "sell";
  } else {
    staleLabel.textContent = "All symbols fresh";
    staleLabel.className = "muted";
  }
}

function renderBars(bars) {
  const target = document.getElementById("bars-grid");
  const symbols = Object.keys(bars).sort();
  if (symbols.length === 0) {
    target.innerHTML = `<div class="empty-state"><span>Building bars from live ticks…</span></div>`;
    return;
  }
  target.innerHTML = symbols
    .map((symbol) => {
      const bar = bars[symbol];
      return `
        <article class="strategy-card">
          <div class="strategy-head"><strong>${symbol}</strong><span class="muted">${bar.interval_minutes}m</span></div>
          <div class="strategy-meta">
            <div><span>O / H</span><strong>${fmt.format(bar.open)} / ${fmt.format(bar.high)}</strong></div>
            <div><span>L / C</span><strong>${fmt.format(bar.low)} / ${fmt.format(bar.close)}</strong></div>
            <div><span>Volume</span><strong>${fmt.format(bar.volume)}</strong></div>
          </div>
        </article>
      `;
    })
    .join("");
}

function bucketMoney(amount) {
  const value = amount || 0;
  if (value >= 1000) return `₹${(value / 1000).toFixed(1)}K`;
  return money.format(value);
}

function renderCapital(capital) {
  const target = document.getElementById("capital-bars");
  const totalLabel = document.getElementById("capital-total");
  if (!capital.total) {
    if (lastCapitalKey !== "loading") {
      target.innerHTML = `<div class="muted">Loading buckets…</div>`;
      lastCapitalKey = "loading";
    }
    if (totalLabel) totalLabel.textContent = "—";
    return;
  }
  const key = JSON.stringify(capital);
  if (key === lastCapitalKey) {
    if (totalLabel) totalLabel.textContent = money.format(capital.total);
    return;
  }
  lastCapitalKey = key;
  if (totalLabel) totalLabel.textContent = money.format(capital.total);
  const rows = [
    ["grid", "Grid", capital.grid, capital.grid_pct],
    ["pair", "Pair", capital.pair, capital.pair_pct],
    ["momentum", "Mom", capital.momentum, capital.momentum_pct],
    ["reserve", "Res", capital.reserve, capital.reserve_pct],
  ];
  target.innerHTML = rows
    .map(
      ([cls, label, amount, pct]) => `
        <div class="capital-row">
          <label>${label}</label>
          <div class="bar-track"><div class="bar-fill ${cls}" style="width:${Math.round((pct || 0) * 100)}%"></div></div>
          <strong title="${money.format(amount || 0)}">${bucketMoney(amount)}</strong>
        </div>
      `,
    )
    .join("");
}

function flashRow(row, direction) {
  if (!direction) return;
  row.classList.remove("flash-up", "flash-down");
  row.classList.add(direction);
}

function renderTicker(quotes, regimes) {
  const container = document.getElementById("ticker");
  const items = Object.values(quotes).sort((a, b) => a.symbol.localeCompare(b.symbol));
  const active = new Set();

  for (const quote of items) {
    active.add(quote.symbol);
    let chip = tickerChips.get(quote.symbol);
    if (!chip) {
      chip = document.createElement("div");
      chip.className = "ticker-chip";
      chip.innerHTML = `
        <div><strong class="sym"></strong><div class="muted regime" style="font-size:10px;margin-top:4px"></div></div>
        <span class="ltp"></span>
      `;
      container.appendChild(chip);
      tickerChips.set(quote.symbol, chip);
    }

    const previous = seenPrices.get(quote.symbol);
    const direction = previous === undefined ? "" : quote.ltp > previous ? "up" : quote.ltp < previous ? "down" : "";
    seenPrices.set(quote.symbol, quote.ltp);

    chip.querySelector(".sym").textContent = quote.symbol;
    chip.querySelector(".regime").textContent = regimes[quote.symbol] || "—";
    chip.querySelector(".ltp").textContent = fmt.format(quote.ltp);
    chip.classList.remove("up", "down");
    if (direction) chip.classList.add(direction);
  }

  for (const [symbol, chip] of tickerChips) {
    if (!active.has(symbol)) {
      chip.remove();
      tickerChips.delete(symbol);
      seenPrices.delete(symbol);
    }
  }
}

function renderQuotes(quotes, regimes, indicators) {
  const tbody = document.getElementById("quotes-body");
  const items = Object.values(quotes).sort((a, b) => a.symbol.localeCompare(b.symbol));
  const active = new Set();

  for (const quote of items) {
    active.add(quote.symbol);
    let row = quoteRows.get(quote.symbol);
    if (!row) {
      row = document.createElement("tr");
      row.innerHTML = `
        <td><strong class="sym"></strong></td>
        <td class="mono ltp"></td>
        <td><span class="regime-pill regime"></span></td>
        <td class="mono adx"></td>
        <td class="mono spread"></td>
        <td class="mono age"></td>
      `;
      tbody.appendChild(row);
      quoteRows.set(quote.symbol, row);
    }

    const previous = seenPrices.get(`table-${quote.symbol}`);
    if (previous !== undefined && quote.ltp !== previous) {
      flashRow(row, quote.ltp > previous ? "flash-up" : "flash-down");
    }
    seenPrices.set(`table-${quote.symbol}`, quote.ltp);

    const regime = regimes[quote.symbol] || "UNKNOWN";
    const adx = indicators[quote.symbol]?.adx_14;
    const threshold = staleThresholdMs(lastPayload?.source, lastPayload?.feed_health);
    const ageMs = quoteAgeMs(quote);
    const ageClass = ageMs > threshold ? "stale" : "";

    row.querySelector(".sym").textContent = quote.symbol;
    row.querySelector(".ltp").textContent = fmt.format(quote.ltp);
    const regimeEl = row.querySelector(".regime");
    regimeEl.textContent = regime;
    regimeEl.className = `regime-pill regime ${regime}`;
    row.querySelector(".adx").textContent = typeof adx === "number" ? fmt.format(adx) : "—";
    row.querySelector(".spread").textContent = quote.spread_bps === null ? "—" : fmt.format(quote.spread_bps);
    const ageEl = row.querySelector(".age");
    ageEl.textContent = `${ageMs}ms`;
    ageEl.className = `mono age ${ageClass}`;
  }

  for (const [symbol, row] of quoteRows) {
    if (!active.has(symbol)) {
      row.remove();
      quoteRows.delete(symbol);
      seenPrices.delete(`table-${symbol}`);
    }
  }
}

function renderCommandStrip(payload) {
  const strip = document.getElementById("command-strip");
  if (!strip) return;
  const regimes = payload.regimes || {};
  const summary = payload.strategy_status?.regime_summary || {};
  const rangeCount = summary.RANGE || Object.values(regimes).filter((r) => r === "RANGE").length;
  const unknownCount = summary.UNKNOWN || Object.values(regimes).filter((r) => r === "UNKNOWN").length;
  const trendCount = (summary.TREND_UP || 0) + (summary.TREND_DOWN || 0);
  const sentiment = payload.sentiment || payload.paper_stats?.sentiment || {};
  const fills = (payload.fills || payload.portfolio?.fills || []).length;
  const session = payload.paper_stats?.current_session;
  const pnl = session?.total_pnl ?? (payload.portfolio?.equity || 0) - (payload.portfolio?.initial_cash || 0);

  strip.innerHTML = `
    <span class="cmd-chip ${sentiment.status === "halt" ? "sell" : sentiment.status === "elevated" ? "stale" : "buy"}">
      Sentiment · ${sentiment.status || "—"}${sentiment.last30days_available ? " · L30✓" : ""}
    </span>
    <span class="cmd-chip buy">RANGE ${rangeCount}</span>
    <span class="cmd-chip ${unknownCount ? "stale" : "muted"}">UNK ${unknownCount}</span>
    <span class="cmd-chip ${trendCount ? "on" : "muted"}">TREND ${trendCount}</span>
    <span class="cmd-chip">Fills ${fills}</span>
    <span class="cmd-chip ${Number(pnl) >= 0 ? "buy" : "sell"}">Session ${money.format(pnl || 0)}</span>
    <span class="cmd-chip muted">${(sentiment.sources_active || []).join(" · ") || "no buzz sources"}</span>
  `;
}

function renderStrategyStatus(status) {
  const note = document.getElementById("edge-note");
  const chips = document.getElementById("strategy-status");
  if (!note || !chips) return;
  note.textContent = status.edge || "Waiting for market regime…";
  const summary = status.regime_summary || {};
  const summaryText = Object.keys(summary).length
    ? Object.entries(summary).map(([k, v]) => `${k}:${v}`).join(" ")
    : "";
  const items = [
    ["Regime", status.regime || "—", status.regime === "RANGE" ? "on" : status.regime === "UNKNOWN" ? "wait" : "off"],
    ["Grid", status.grid || "OFF", status.grid === "ACTIVE" ? "on" : "off"],
    ["Momentum", status.momentum || "OFF", status.momentum === "ARMED" ? "on" : "off"],
    ["Pair", status.pair || "WAITING", status.pair && status.pair !== "WAIT" && status.pair !== "WAITING" ? "on" : "wait"],
  ];
  chips.innerHTML =
    items.map(([label, value, cls]) => `<span class="status-chip ${cls}">${label}: ${value}</span>`).join("") +
    (summaryText ? `<span class="status-chip muted">${summaryText}</span>` : "");
}

function renderStrategies(gridPlans, momentumPlans, regimes) {
  const symbols = [...new Set([...Object.keys(gridPlans), ...Object.keys(momentumPlans)])].sort();
  const target = document.getElementById("strategy-plans");
  if (symbols.length === 0) {
    target.innerHTML = `<div class="empty-state"><span>Waiting for feed…</span></div>`;
    return;
  }
  target.innerHTML = symbols
    .map((symbol) => {
      const grid = gridPlans[symbol];
      const momentum = momentumPlans[symbol];
      const regime = regimes[symbol] || grid?.regime || "—";
      return `
        <article class="strategy-card">
          <div class="strategy-head">
            <strong>${symbol}</strong>
            <span class="regime-pill ${regime}">${regime}</span>
          </div>
          <div class="strategy-meta">
            <div><span>Fair value</span><strong>${grid ? fmt.format(grid.fair_value) : "—"}</strong></div>
            <div><span>Spacing</span><strong>${grid ? fmt.format(grid.spacing) : "—"}</strong></div>
            <div><span>Momentum</span><strong class="${momentum?.enabled ? "buy" : "muted"}">${momentum?.enabled ? "Armed" : momentum?.reason || "—"}</strong></div>
          </div>
          <div class="levels">${(grid?.buy_levels || []).map((level) => `<span class="level">${fmt.format(level)}</span>`).join("")}</div>
          ${grid?.reset_reason ? `<p class="muted" style="margin-top:10px;font-size:11px">Reset: ${grid.reset_reason}</p>` : ""}
        </article>
      `;
    })
    .join("");
}

function renderPairs(pairPlans) {
  const target = document.getElementById("pair-plans");
  const plans = Object.values(pairPlans);
  if (plans.length === 0) {
    target.innerHTML = `<div class="empty-state"><span>Waiting for both legs</span></div>`;
    return;
  }
  target.innerHTML = plans
    .sort((a, b) => a.pair_id.localeCompare(b.pair_id))
    .map((plan) => `
      <article class="strategy-card">
        <div class="strategy-head"><strong>${plan.pair_id}</strong><span class="${plan.enabled ? "buy" : "muted"}">${plan.action}</span></div>
        <div class="strategy-meta">
          <div><span>Z-score</span><strong class="${Math.abs(plan.zscore) >= 1.5 ? "buy" : ""}">${fmt.format(plan.zscore)}</strong></div>
          <div><span>Spread</span><strong>${fmt.format(plan.spread)}</strong></div>
          <div><span>Qty A/B</span><strong>${plan.quantity_a || 0}/${plan.quantity_b || 0}</strong></div>
        </div>
        <p class="muted" style="margin-top:10px;font-size:11px">${plan.reason}</p>
      </article>
    `)
    .join("");
}

function renderPairTrades(trades) {
  const target = document.getElementById("pair-trades");
  if (trades.length === 0) {
    target.classList.add("empty-state");
    target.innerHTML = "<span>No pair trades yet</span>";
    return;
  }
  target.classList.remove("empty-state");
  target.innerHTML = trades
    .slice()
    .reverse()
    .map(
      (trade) => `
      <article class="tape-item">
        <div><strong class="${trade.status === "CLOSED" ? "buy" : "stale"}">${trade.status}</strong><p>${trade.pair_id} · ${trade.trade_id}</p></div>
        <div><strong class="${trade.realized_pnl >= 0 ? "buy" : "sell"}">${money.format(trade.realized_pnl || 0)}</strong></div>
      </article>
    `,
    )
    .join("");
}

function renderFills(fills) {
  const target = document.getElementById("fills");
  if (fills.length === 0) {
    target.classList.add("empty-state");
    target.innerHTML = "<span>No fills yet</span>";
    return;
  }
  target.classList.remove("empty-state");
  target.innerHTML = fills
    .slice()
    .reverse()
    .map(
      (fill) => `
      <article class="tape-item">
        <div><strong class="${fill.side === "BUY" ? "buy" : "sell"}">${fill.side}</strong><p>${fill.symbol} · ${fill.reason || "—"}</p></div>
        <div><strong class="mono">${fmt.format(fill.price)}</strong><p>Qty ${fill.quantity}</p></div>
      </article>
    `,
    )
    .join("");
}

function renderPositions(positions) {
  const body = document.getElementById("positions-body");
  const foot = document.getElementById("positions-foot");
  if (positions.length === 0) {
    body.innerHTML = `<tr><td colspan="5" class="muted">No open positions</td></tr>`;
    if (foot) foot.innerHTML = "";
    return;
  }
  let invested = 0;
  let unrealized = 0;
  body.innerHTML = positions
    .map((position) => {
      const marketValue = Number(position.market_value ?? position.quantity * position.last_price);
      const pnl = Number(position.unrealized_pnl ?? 0);
      invested += marketValue;
      unrealized += pnl;
      return `
      <tr>
        <td><strong>${position.symbol}</strong></td>
        <td class="mono">${position.quantity}</td>
        <td class="mono">${fmt.format(position.avg_price)}</td>
        <td class="mono">${fmt.format(position.last_price)}</td>
        <td class="mono ${pnl >= 0 ? "buy" : "sell"}">${money.format(pnl)}</td>
      </tr>
    `;
    })
    .join("");
  if (foot) {
    foot.innerHTML = `
      <tr class="positions-total">
        <td><strong>Total</strong></td>
        <td class="mono">${positions.length}</td>
        <td colspan="2" class="mono">Invested ${money.format(invested)}</td>
        <td class="mono ${unrealized >= 0 ? "buy" : "sell"}">${money.format(unrealized)}</td>
      </tr>
    `;
  }
}

const HEALTH_LABELS = {
  too_early: "Too early",
  promising: "Promising",
  needs_review: "Needs review",
  deployed: "Deployed",
  idle: "Idle",
};

function renderPaperStats(stats) {
  const target = document.getElementById("paper-stats");
  if (!target) return;
  if (!stats || !stats.current_session) {
    target.classList.add("empty-state");
    target.innerHTML = "<span>Collecting session data…</span>";
    return;
  }
  const killed = lastPayload?.controls?.kill_switch;
  const killBanner = killed
    ? `<div class="stats-alert sell">Kill switch is ON — trading blocked. Click <strong>Resume</strong> in the header (feed is healthy).</div>`
    : "";
  target.classList.remove("empty-state");
  const multi = stats.multi_session || {};
  const current = stats.current_session || {};
  const health = stats.strategy_health || {};
  const sentiment = stats.sentiment || {};
  const sentimentStatus = sentiment.status || "not_configured";
  const sentimentKlass =
    sentimentStatus === "halt" ? "sell" : sentimentStatus === "elevated" ? "stale" : sentimentStatus === "clear" ? "buy" : "muted";
  const sessions = stats.sessions || [];
  const breakdown = current.strategy_breakdown || {};
  const verdict = HEALTH_LABELS[health.verdict] || health.verdict || "—";

  target.innerHTML = `
    ${killBanner}
    <div class="stats-grid">
      <article class="stats-card">
        <span>Multi-session</span>
        <strong class="${Number(multi.cumulative_pnl) >= 0 ? "buy" : "sell"}">${money.format(multi.cumulative_pnl || 0)}</strong>
        <p>${multi.sessions_count || 0} closed · win ${multi.win_rate_pct || 0}% · fees ${money.format(multi.total_fees || 0)}</p>
      </article>
      <article class="stats-card">
        <span>Today (${current.session_id || "—"})</span>
        <strong class="${Number(current.total_pnl) >= 0 ? "buy" : "sell"}">${money.format(current.total_pnl || 0)}</strong>
        <p>${current.minutes_active || 0}m · ${current.fill_count || 0} fills · ${current.max_exposure_pct || 0}% max deploy</p>
      </article>
      <article class="stats-card">
        <span>Strategy health</span>
        <strong class="stale">${verdict}</strong>
        <p>${health.summary || "—"}</p>
      </article>
      <article class="stats-card">
        <span>News / sentiment</span>
        <strong class="${sentimentKlass}">${sentimentStatus === "not_configured" ? "Starting" : sentimentStatus}</strong>
        <p>${sentiment.headline || "—"}</p>
      </article>
    </div>
    <div class="stats-detail">
      <div class="stats-breakdown">
        <h3>Current sleeve activity</h3>
        <p>Grid ${breakdown.grid || 0} · Pair ${breakdown.pair || 0} · Momentum ${breakdown.momentum || 0} · Exits ${health.grid_exits || 0}</p>
        <ul class="stats-notes">
          ${(health.notes || []).map((note) => `<li>${note}</li>`).join("")}
        </ul>
      </div>
      <div class="stats-sentiment">
        <h3>Buzz overlay</h3>
        <p class="muted">${sentiment.detail || ""}</p>
        <p class="muted">Sources: ${(sentiment.sources_active || []).join(", ") || "pending"} · last30days: ${sentiment.last30days_available ? "connected" : "not found"} · refresh ${sentiment.last_refresh_at ? new Date(sentiment.last_refresh_at).toLocaleTimeString("en-IN") : "—"}</p>
      </div>
    </div>
    <div class="table-wrap">
      <table class="data-table compact">
        <thead>
          <tr><th>Session</th><th>Status</th><th>P&L</th><th>Fills</th><th>Max deploy</th><th>Grid</th></tr>
        </thead>
        <tbody>
          ${sessions
            .map(
              (row) => `
            <tr>
              <td><strong>${row.session_id}</strong></td>
              <td>${row.status}</td>
              <td class="mono ${Number(row.total_pnl) >= 0 ? "buy" : "sell"}">${money.format(row.total_pnl || 0)}</td>
              <td class="mono">${row.fill_count || 0}</td>
              <td class="mono">${row.max_exposure_pct || 0}%</td>
              <td class="mono">${(row.strategy_breakdown || {}).grid || 0}</td>
            </tr>
          `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderSentiment(sentiment) {
  const target = document.getElementById("sentiment-panel");
  if (!target) return;
  const symbols = sentiment.symbols || {};
  const entries = Object.entries(symbols).sort((a, b) => Number(a[1].score) - Number(b[1].score));
  if (!entries.length) {
    target.classList.add("empty-state");
    target.innerHTML = `<span>${sentiment.headline || "Waiting for first sentiment refresh…"}</span>`;
    return;
  }
  target.classList.remove("empty-state");
  target.innerHTML = `
    <div class="sentiment-head">
      <strong class="${sentiment.status === "halt" ? "sell" : sentiment.status === "elevated" ? "stale" : "buy"}">${titleCase(sentiment.status || "clear")}</strong>
      <span class="muted">${sentiment.headline || ""}${sentiment.last30days_engine_path ? ` · engine: ${sentiment.last30days_engine_path.split("/").slice(-2).join("/")}` : ""}</span>
    </div>
    <div class="table-wrap">
      <table class="data-table compact">
        <thead>
          <tr><th>Symbol</th><th>Score</th><th>Buzz</th><th>Status</th><th>Action</th><th>Top signal</th></tr>
        </thead>
        <tbody>
          ${entries
            .map(([symbol, row]) => {
              const top = (row.top_items || [])[0];
              const score = Number(row.score || 0);
              const scoreKlass = score <= -0.55 ? "sell" : score <= -0.25 ? "stale" : "buy";
              return `
                <tr>
                  <td><strong>${symbol}</strong></td>
                  <td class="mono ${scoreKlass}">${score.toFixed(2)}</td>
                  <td class="mono">${row.buzz_volume || 0}</td>
                  <td>${row.status || "clear"}</td>
                  <td>${row.action || "allow"}</td>
                  <td class="muted">${top ? `[${top.source}] ${top.title}` : "—"}</td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderEvents(events) {
  const target = document.getElementById("events");
  if (events.length === 0) {
    target.classList.add("empty-state");
    target.innerHTML = "<span>No events yet</span>";
    return;
  }
  target.classList.remove("empty-state");
  target.innerHTML = events
    .slice()
    .reverse()
    .map(
      (entry) => `
      <article class="event-item ${entry.severity}">
        <div><strong>${entry.category}</strong><p>${entry.message}</p></div>
        <time>${new Date(entry.timestamp).toLocaleTimeString("en-IN", { hour12: false })}</time>
      </article>
    `,
    )
    .join("");
}

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
}
