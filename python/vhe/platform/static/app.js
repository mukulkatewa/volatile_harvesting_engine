const fmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

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
  renderQuotes(payload.quotes);
  renderPlans(payload.plans);
  renderOrders(payload.orders);
}

function renderConnection(connected) {
  document.getElementById("connection-dot").classList.toggle("live", connected);
  document.getElementById("connection-label").textContent = connected ? "Live" : "Disconnected";
}

function renderQuotes(quotes) {
  document.getElementById("quotes-body").innerHTML = Object.values(quotes)
    .sort((a, b) => a.symbol.localeCompare(b.symbol))
    .map((quote) => `
      <tr>
        <td>${quote.symbol}</td>
        <td>${fmt.format(quote.ltp)}</td>
        <td>${quote.spread_bps === null ? "-" : fmt.format(quote.spread_bps)}</td>
        <td>${fmt.format(quote.volume)}</td>
      </tr>
    `)
    .join("");
}

function renderPlans(plans) {
  document.getElementById("grid-plans").innerHTML = Object.values(plans)
    .sort((a, b) => a.symbol.localeCompare(b.symbol))
    .map((plan) => `
      <article class="plan">
        <div class="plan-head"><strong>${plan.symbol}</strong><span class="muted">${plan.regime}</span></div>
        <p class="muted">FV ${fmt.format(plan.fair_value)} | Spacing ${fmt.format(plan.spacing)}</p>
        <div class="levels">${plan.buy_levels.map((level) => `<span class="level">${fmt.format(level)}</span>`).join("")}</div>
      </article>
    `)
    .join("");
}

function renderOrders(orders) {
  document.getElementById("orders").innerHTML = orders
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

connect();
