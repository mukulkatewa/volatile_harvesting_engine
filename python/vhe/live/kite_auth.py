from __future__ import annotations

import os
from dataclasses import dataclass

from vhe.config.loader import BrokerConfig


@dataclass(frozen=True, slots=True)
class KiteCredentials:
    api_key: str
    access_token: str
    api_secret: str | None = None


class KiteCredentialError(RuntimeError):
    pass


def load_kite_credentials(broker: BrokerConfig) -> KiteCredentials:
    api_key = os.environ.get(broker.api_key_env, "").strip()
    access_token = os.environ.get(broker.access_token_env, "").strip()
    api_secret = os.environ.get(broker.api_secret_env, "").strip() or None

    if not api_key or not access_token or access_token == "your_access_token_here":
        missing = []
        if not api_key:
            missing.append(broker.api_key_env)
        if not access_token or access_token == "your_access_token_here":
            missing.append(broker.access_token_env)
        raise KiteCredentialError(f"Missing Kite credentials: {', '.join(missing)}")

    return KiteCredentials(api_key=api_key, access_token=access_token, api_secret=api_secret)


def kite_login_url(api_key: str, redirect_url: str = "http://127.0.0.1") -> str:
    return f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
