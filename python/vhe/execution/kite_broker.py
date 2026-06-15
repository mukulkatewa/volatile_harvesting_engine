from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from vhe.backtest.models import Fill, Order, OrderSide
from vhe.live.kite_auth import KiteCredentials
from vhe.live.models import LiveQuote

logger = logging.getLogger(__name__)

KITE_ORDERS_URL = "https://api.kite.trade/orders"


@dataclass(frozen=True, slots=True)
class KiteOrderResponse:
    broker_order_id: str
    status: str


class KiteBrokerError(RuntimeError):
    pass


@dataclass(slots=True)
class KiteBroker:
    credentials: KiteCredentials
    timeout_seconds: float = 30.0
    throttle_ms: int = 400
    _last_request_at: float = 0.0

    def place_order(self, order: Order, quote: LiveQuote) -> KiteOrderResponse:
        payload = {
            "exchange": "NSE",
            "tradingsymbol": order.symbol,
            "transaction_type": "BUY" if order.side == OrderSide.BUY else "SELL",
            "order_type": order.order_type.value,
            "quantity": str(order.quantity),
            "product": "MIS",
            "price": str(order.price),
            "validity": "DAY",
            "tag": (order.reason or "vhe")[:20],
        }
        body = self._post("/regular", data=payload)
        order_id = str(body["data"]["order_id"])
        return KiteOrderResponse(broker_order_id=order_id, status="SENT")

    def cancel_order(self, broker_order_id: str, *, variety: str = "regular") -> None:
        self._delete(f"/{variety}/{broker_order_id}")

    def fetch_orders(self) -> list[dict]:
        body = self._get("")
        return list(body.get("data") or [])

    def fetch_trades(self) -> list[dict]:
        body = self._get("/trades")
        return list(body.get("data") or [])

    def _headers(self) -> dict[str, str]:
        return {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.credentials.api_key}:{self.credentials.access_token}",
        }

    def _get(self, path: str) -> dict:
        with httpx.Client(timeout=self.timeout_seconds, headers=self._headers()) as client:
            response = client.get(f"{KITE_ORDERS_URL}{path}")
        return self._parse(response)

    def _post(self, path: str, *, data: dict[str, str]) -> dict:
        with httpx.Client(timeout=self.timeout_seconds, headers=self._headers()) as client:
            response = client.post(f"{KITE_ORDERS_URL}{path}", data=data)
        return self._parse(response)

    def _delete(self, path: str) -> dict:
        with httpx.Client(timeout=self.timeout_seconds, headers=self._headers()) as client:
            response = client.delete(f"{KITE_ORDERS_URL}{path}")
        return self._parse(response)

    def _parse(self, response: httpx.Response) -> dict:
        response.raise_for_status()
        body = response.json()
        if body.get("status") != "success":
            message = body.get("message") or str(body)
            raise KiteBrokerError(message)
        return body
