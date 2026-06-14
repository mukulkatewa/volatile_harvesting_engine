const fmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const seenPrices = new Map();

const controls = [
  ["pause-button", "/api/control/pause"],
  ["resume-button", "/api/control/resume"],
  ["kill-button", "/api/control/kill"],
  ["demo-fill-button", "/api/control/demo-fill"],
  ["reset-paper-button", "/api/control/reset-paper"],
];

for (const [id, endpoint] of controls) {
  document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById(id);
    if (button) button.addEventListener("click", () => postControl(endpoint));
  });
}

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws/state`);

  socket.onopen = () => renderConnection(true);
  socket.onmessage = (event) => render(JSON.parse(event.data));
  socket.onclose = () => {
    renderConnection(false);
    setTimeout(connect, 1200);
  };
}

function render(payload) {
  const portfolio = payload.portfolio || {};
  renderConnection(payload.connected);
  document.getElementById("equity").textContent = money.format(portfolio.equity || 0);
  document.getElementById("cash").textContent = money.format(portfolio.cash || 0);
  setPnl("unrealized-pnl", portfolio.unrealized_pnl || 0);
  document.getElementById("mode-label").textContent = titleCase(payload.mode || "paper");
  renderRisk(payload.controls || {});
  renderTicker(payload.quotes);
  renderQuotes(payload.quotes);
  renderStrategies(payload.plans, payload.momentum_plans || {});
  renderPairs(payload.pair_plans || {});
  renderFills(payload.fills || []);
  renderPositions((portfolio.positions || []));
  renderEvents(payload.events || []);
}

async function postControl(endpoint) {
  const response = await fetch(endpoint, { method: "POST" });
  if (response.ok) render(await response.json());
}

function renderRisk(controls) {
  const label = document.getElementById("risk-label");
  const paused = controls.automation_paused;
  const killed = controls.kill_switch;
  const reject = controls.last_risk_reject;
  label.textContent = killed ? "Killed" : paused ? "Paused" : reject ? reject : "Clear";
  label.classList.toggle("sell", killed);
  label.classList.toggle("stale", paused || Boolean(reject));
  label.classList.toggle("buy", !killed && !paused && !reject);
}

function renderConnection(connected) {
  document.getElementById("connection-dot").classList.toggle("live", connected);
  document.getElementById("connection-label").textContent = connected ? "Live" : "Disconnected";
}

function setPnl(id, value) {
  const target = document.getElementById(id);
  target.textContent = money.format(value);
  target.classList.toggle("buy", value >= 0);
  target.classList.toggle("sell", value < 0);
}

function renderTicker(quotes) {
  document.getElementById("ticker").innerHTML = Object.values(quotes)
    .sort((a, b) => a.symbol.localeCompare(b.symbol))
    .map((quote) => `<div class="ticker-chip"><strong>${quote.symbol}</strong><span>${fmt.format(quote.ltp)}</span></div>`)
    .join("");
}

function renderQuotes(quotes) {
  document.getElementById("quotes-body").innerHTML = Object.values(quotes)
    .sort((a, b) => a.symbol.localeCompare(b.symbol))
    .map((quote) => {
      const previous = seenPrices.get(quote.symbol);
      const changed = previous !== undefined && previous !== quote.ltp;
      seenPrices.set(quote.symbol, quote.ltp);
      const ageClass = quote.age_ms > 2000 ? "stale" : "";
      return `
        <tr class="${changed ? "flash" : ""}">
          <td><strong>${quote.symbol}</strong></td>
          <td>${fmt.format(quote.ltp)}</td>
          <td>${quote.spread_bps === null ? "-" : fmt.format(quote.spread_bps)}</td>
          <td class="${ageClass}">${quote.age_ms}ms</td>
          <td>${fmt.format(quote.volume)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderStrategies(gridPlans, momentumPlans) {
  const symbols = [...new Set([...Object.keys(gridPlans), ...Object.keys(momentumPlans)])].sort();
  document.getElementById("strategy-plans").innerHTML = symbols
    .map((symbol) => {
      const grid = gridPlans[symbol];
      const momentum = momentumPlans[symbol];
      return `
        <article class="plan">
          <div class="plan-head"><strong>${symbol}</strong><span class="muted">${grid?.regime || "-"}</span></div>
          <div class="plan-meta">
            <div><span>Fair value</span><strong>${grid ? fmt.format(grid.fair_value) : "-"}</strong></div>
            <div><span>Grid spacing</span><strong>${grid ? fmt.format(grid.spacing) : "-"}</strong></div>
            <div><span>Momentum</span><strong class="${momentum?.enabled ? "buy" : "muted"}">${momentum?.enabled ? "Armed" : momentum?.reason || "-"}</strong></div>
          </div>
          <div class="levels">${(grid?.buy_levels || []).map((level) => `<span class="level">${fmt.format(level)}</span>`).join("")}</div>
        </article>
      `;
    })
    .join("");
}

function renderPairs(pairPlans) {
  const target = document.getElementById("pair-plans");
  const plans = Object.values(pairPlans);
  if (plans.length === 0) {
    target.innerHTML = `<article class="plan"><span class="muted">Waiting for both legs</span></article>`;
    return;
  }
  target.innerHTML = plans
    .sort((a, b) => a.pair_id.localeCompare(b.pair_id))
    .map((plan) => `
      <article class="plan">
        <div class="plan-head"><strong>${plan.pair_id}</strong><span class="${plan.enabled ? "buy" : "muted"}">${plan.action}</span></div>
        <div class="plan-meta">
          <div><span>Z-score</span><strong>${fmt.format(plan.zscore)}</strong></div>
          <div><span>Spread</span><strong>${fmt.format(plan.spread)}</strong></div>
          <div><span>Qty A/B</span><strong>${plan.quantity_a || 0}/${plan.quantity_b || 0}</strong></div>
        </div>
      </article>
    `)
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
    .map((fill) => `
      <article class="order">
        <div><strong class="${fill.side === "BUY" ? "buy" : "sell"}">${fill.side}</strong><span> ${fill.symbol}</span><p class="muted">${fill.reason}</p></div>
        <div><strong>${fmt.format(fill.price)}</strong><p class="muted">Qty ${fill.quantity}</p></div>
      </article>
    `)
    .join("");
}

function renderPositions(positions) {
  const body = document.getElementById("positions-body");
  if (positions.length === 0) {
    body.innerHTML = `<tr><td colspan="5" class="muted">No open positions</td></tr>`;
    return;
  }
  body.innerHTML = positions
    .map((position) => `
      <tr>
        <td><strong>${position.symbol}</strong></td>
        <td>${position.quantity}</td>
        <td>${fmt.format(position.avg_price)}</td>
        <td>${fmt.format(position.last_price)}</td>
        <td class="${position.unrealized_pnl >= 0 ? "buy" : "sell"}">${money.format(position.unrealized_pnl)}</td>
      </tr>
    `)
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
    .map((entry) => `
      <article class="event ${entry.severity}">
        <div><strong>${entry.category}</strong><p>${entry.message}</p></div>
        <time>${new Date(entry.timestamp).toLocaleTimeString("en-IN", { hour12: false })}</time>
      </article>
    `)
    .join("");
}

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
}

connect();
