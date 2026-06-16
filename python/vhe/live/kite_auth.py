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


def _placeholder_access_token(value: str) -> bool:
    return not value or value == "your_access_token_here"


def load_kite_api_key(broker: BrokerConfig) -> str:
    api_key = os.environ.get(broker.api_key_env, "").strip()
    if not api_key:
        raise KiteCredentialError(f"Missing Kite credentials: {broker.api_key_env}")
    return api_key


def load_kite_exchange_credentials(broker: BrokerConfig) -> KiteCredentials:
    api_key = os.environ.get(broker.api_key_env, "").strip()
    api_secret = os.environ.get(broker.api_secret_env, "").strip() or None
    missing: list[str] = []
    if not api_key:
        missing.append(broker.api_key_env)
    if not api_secret:
        missing.append(broker.api_secret_env)
    if missing:
        raise KiteCredentialError(f"Missing Kite credentials: {', '.join(missing)}")
    return KiteCredentials(api_key=api_key, access_token="", api_secret=api_secret)


def load_kite_credentials(broker: BrokerConfig) -> KiteCredentials:
    api_key = os.environ.get(broker.api_key_env, "").strip()
    access_token = os.environ.get(broker.access_token_env, "").strip()
    api_secret = os.environ.get(broker.api_secret_env, "").strip() or None

    if not api_key or _placeholder_access_token(access_token):
        missing = []
        if not api_key:
            missing.append(broker.api_key_env)
        if _placeholder_access_token(access_token):
            missing.append(broker.access_token_env)
        raise KiteCredentialError(f"Missing Kite credentials: {', '.join(missing)}")

    return KiteCredentials(api_key=api_key, access_token=access_token, api_secret=api_secret)


def kite_login_url(api_key: str, redirect_url: str = "http://127.0.0.1") -> str:
    return f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
