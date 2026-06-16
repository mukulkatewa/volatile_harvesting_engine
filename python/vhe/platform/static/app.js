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

const controls = [
  ["pause-button", "/api/control/pause"],
  ["resume-button", "/api/control/resume"],
  ["kill-button", "/api/control/kill"],
  ["demo-fill-button", "/api/control/demo-fill"],
  ["reset-paper-button", "/api/control/reset-paper"],
];

document.addEventListener("DOMContentLoaded", () => {
  for (const [id, endpoint] of controls) {
    const button = document.getElementById(id);
    if (button) button.addEventListener("click", () => postControl(endpoint));
  }

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.panel));
  });

  tickClock();
  setInterval(tickClock, 1000);
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
  const portfolio = payload.portfolio || {};
  const capitalTotal = payload.capital?.total;
  renderConnection(payload.connected);
  document.getElementById("phase-label").textContent = payload.phase || "2";
  document.getElementById("mode-label").textContent = titleCase(payload.mode || "paper");
  document.getElementById("source-label").textContent = payload.source || "simulated";
  const equity = portfolio.equity ?? portfolio.cash ?? capitalTotal ?? 0;
  document.getElementById("equity").textContent = money.format(equity);
  document.getElementById("cash").textContent = money.format(portfolio.cash ?? capitalTotal ?? 0);
  setPnl("unrealized-pnl", portfolio.unrealized_pnl || 0);
  renderRisk(payload.controls || {});
  renderCapital(payload.capital || {});
  renderStrategyStatus(payload.strategy_status || {});
  renderFeedHealth(payload.feed_health || {}, payload.source);
  renderBars(payload.bars || {});
  renderTicker(payload.quotes || {}, payload.regimes || {});
  renderQuotes(payload.quotes || {}, payload.regimes || {}, payload.indicators || {});
  renderStrategies(payload.plans || {}, payload.momentum_plans || {}, payload.regimes || {});
  renderPairs(payload.pair_plans || {});
  renderPairTrades(payload.pair_trades || []);
  renderFills(payload.fills || []);
  renderPositions(portfolio.positions || []);
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

function renderRisk(controls) {
  const label = document.getElementById("risk-label");
  const paused = controls.automation_paused;
  const killed = controls.kill_switch;
  const reject = controls.last_risk_reject;
  label.textContent = killed ? "Killed" : paused ? "Paused" : reject ? reject : "Clear";
  label.className = "risk-pill";
  label.classList.add(killed ? "sell" : paused || reject ? "stale" : "buy");
}

function renderConnection(connected) {
  document.getElementById("connection-dot").classList.toggle("live", connected);
  document.getElementById("connection-label").textContent = connected ? "Live Feed" : "Disconnected";
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
  label.textContent = online
    ? feedSource.toUpperCase()
    : delayed
      ? "YFINANCE (~15M DELAY)"
      : feedSource === "kite"
        ? "KITE OFFLINE"
        : feedSource.toUpperCase();
  label.className = `feed-source ${online || delayed ? "buy" : feedSource === "kite" ? "stale" : "stale"}`;
  const age = health.last_tick_age_ms;
  tickAge.textContent = age == null ? "—" : `${age}ms`;
  tickAge.className = age != null && age > 3000 ? "sell" : "buy";
  const stale = health.stale_symbols || [];
  if (health.is_stale) {
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
    const ageClass = quote.age_ms > 2000 ? "stale" : "";

    row.querySelector(".sym").textContent = quote.symbol;
    row.querySelector(".ltp").textContent = fmt.format(quote.ltp);
    const regimeEl = row.querySelector(".regime");
    regimeEl.textContent = regime;
    regimeEl.className = `regime-pill regime ${regime}`;
    row.querySelector(".adx").textContent = typeof adx === "number" ? fmt.format(adx) : "—";
    row.querySelector(".spread").textContent = quote.spread_bps === null ? "—" : fmt.format(quote.spread_bps);
    const ageEl = row.querySelector(".age");
    ageEl.textContent = `${quote.age_ms}ms`;
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

function renderStrategyStatus(status) {
  const note = document.getElementById("edge-note");
  const chips = document.getElementById("strategy-status");
  if (!note || !chips) return;
  note.textContent = status.edge || "Waiting for market regime…";
  const items = [
    ["Regime", status.regime || "—", "wait"],
    ["Grid", status.grid || "OFF", status.grid === "ACTIVE" ? "on" : "off"],
    ["Momentum", status.momentum || "OFF", status.momentum === "ARMED" ? "on" : "off"],
    ["Pair", status.pair || "WAITING", status.pair && status.pair !== "WAIT" && status.pair !== "WAITING" ? "on" : "wait"],
  ];
  chips.innerHTML = items
    .map(([label, value, cls]) => `<span class="status-chip ${cls}">${label}: ${value}</span>`)
    .join("");
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
  if (positions.length === 0) {
    body.innerHTML = `<tr><td colspan="5" class="muted">No open positions</td></tr>`;
    return;
  }
  body.innerHTML = positions
    .map(
      (position) => `
      <tr>
        <td><strong>${position.symbol}</strong></td>
        <td class="mono">${position.quantity}</td>
        <td class="mono">${fmt.format(position.avg_price)}</td>
        <td class="mono">${fmt.format(position.last_price)}</td>
        <td class="mono ${position.unrealized_pnl >= 0 ? "buy" : "sell"}">${money.format(position.unrealized_pnl)}</td>
      </tr>
    `,
    )
    .join("");
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
