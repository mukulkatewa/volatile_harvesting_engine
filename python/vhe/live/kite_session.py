from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from vhe.live.kite_auth import KiteCredentials


KITE_SESSION_URL = "https://api.kite.trade/session/token"


@dataclass(frozen=True, slots=True)
class KiteSession:
    access_token: str
    user_id: str
    login_time: str


class KiteSessionClient:
    def __init__(self, credentials: KiteCredentials, timeout_seconds: float = 30.0) -> None:
        if not credentials.api_secret:
            raise ValueError("api_secret is required to exchange request_token")
        self.credentials = credentials
        self.timeout_seconds = timeout_seconds

    def exchange_request_token(self, request_token: str) -> KiteSession:
        payload = {
            "api_key": self.credentials.api_key,
            "request_token": request_token,
            "api_secret": self.credentials.api_secret,
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                KITE_SESSION_URL,
                data=payload,
                headers={"X-Kite-Version": "3"},
            )
        response.raise_for_status()
        body = response.json()
        if body.get("status") != "success":
            raise RuntimeError(f"Kite session exchange failed: {json.dumps(body)}")
        data = body["data"]
        return KiteSession(
            access_token=str(data["access_token"]),
            user_id=str(data["user_id"]),
            login_time=str(data.get("login_time", "")),
        )
