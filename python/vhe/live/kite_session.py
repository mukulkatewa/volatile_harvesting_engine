from __future__ import annotations

import hashlib
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


def kite_session_checksum(api_key: str, request_token: str, api_secret: str) -> str:
    payload = f"{api_key}{request_token}{api_secret}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class KiteSessionClient:
    def __init__(self, credentials: KiteCredentials, timeout_seconds: float = 30.0) -> None:
        if not credentials.api_secret:
            raise ValueError("api_secret is required to exchange request_token")
        self.credentials = credentials
        self.timeout_seconds = timeout_seconds

    def exchange_request_token(self, request_token: str) -> KiteSession:
        checksum = kite_session_checksum(
            self.credentials.api_key,
            request_token,
            self.credentials.api_secret,
        )
        payload = {
            "api_key": self.credentials.api_key,
            "request_token": request_token,
            "checksum": checksum,
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                KITE_SESSION_URL,
                data=payload,
                headers={"X-Kite-Version": "3"},
            )
        if response.status_code >= 400:
            try:
                body = response.json()
                message = body.get("message", response.text)
            except ValueError:
                message = response.text
            raise RuntimeError(f"Kite session exchange failed ({response.status_code}): {message}")
        body = response.json()
        if body.get("status") != "success":
            raise RuntimeError(f"Kite session exchange failed: {json.dumps(body)}")
        data = body["data"]
        return KiteSession(
            access_token=str(data["access_token"]),
            user_id=str(data["user_id"]),
            login_time=str(data.get("login_time", "")),
        )
