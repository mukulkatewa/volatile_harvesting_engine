const fmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const seenPrices = new Map();

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
  renderConnection(payload.connected);
  document.getElementById("feed-source").textContent = payload.source;
  document.getElementById("symbol-count").textContent = Object.keys(payload.quotes).length;
  document.getElementById("order-count").textContent = payload.orders.length;
  document.getElementById("mode-label").textContent = titleCase(payload.mode || "paper");
  renderTicker(payload.quotes);
  renderQuotes(payload.quotes);
  renderPlans(payload.plans);
  renderOrders(payload.orders);
}

function renderConnection(connected) {
  document.getElementById("connection-dot").classList.toggle("live", connected);
  document.getElementById("connection-label").textContent = connected ? "Live" : "Disconnected";
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

function renderPlans(plans) {
  document.getElementById("grid-plans").innerHTML = Object.values(plans)
    .sort((a, b) => a.symbol.localeCompare(b.symbol))
    .map((plan) => `
      <article class="plan">
        <div class="plan-head"><strong>${plan.symbol}</strong><span class="muted">${plan.regime}</span></div>
        <div class="plan-meta">
          <div><span>Fair value</span><strong>${fmt.format(plan.fair_value)}</strong></div>
          <div><span>Spacing</span><strong>${fmt.format(plan.spacing)}</strong></div>
          <div><span>Reset</span><strong>${plan.reset_reason || "stable"}</strong></div>
        </div>
        <div class="levels">${plan.buy_levels.map((level) => `<span class="level">${fmt.format(level)}</span>`).join("")}</div>
      </article>
    `)
    .join("");
}

function renderOrders(orders) {
  const target = document.getElementById("orders");
  if (orders.length === 0) {
    target.classList.add("empty-state");
    target.innerHTML = "<span>No active intents</span>";
    return;
  }
  target.classList.remove("empty-state");
  target.innerHTML = orders
    .slice()
    .reverse()
    .map((order) => `
      <article class="order">
        <div><strong class="${order.side === "BUY" ? "buy" : "sell"}">${order.side}</strong><span> ${order.symbol}</span><p class="muted">${order.reason}</p></div>
        <div><strong>${fmt.format(order.price)}</strong><p class="muted">Qty ${order.quantity}</p></div>
      </article>
    `)
    .join("");
}

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
}

connect();
