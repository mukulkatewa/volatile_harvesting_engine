import pytest

from vhe.config.loader import BrokerConfig
from vhe.live.kite_auth import (
    KiteCredentialError,
    kite_login_url,
    load_kite_api_key,
    load_kite_credentials,
    load_kite_exchange_credentials,
)


def test_kite_login_url() -> None:
    url = kite_login_url("abc123", redirect_url="http://127.0.0.1")
    assert "api_key=abc123" in url
    assert "kite.zerodha.com/connect/login" in url


def test_load_kite_credentials_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KITE_API_KEY", raising=False)
    monkeypatch.delenv("KITE_ACCESS_TOKEN", raising=False)
    with pytest.raises(KiteCredentialError):
        load_kite_credentials(BrokerConfig())


def test_load_kite_api_key_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITE_API_KEY", "key")
    assert load_kite_api_key(BrokerConfig()) == "key"


def test_load_kite_exchange_credentials_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITE_API_KEY", "key")
    monkeypatch.setenv("KITE_API_SECRET", "secret")
    creds = load_kite_exchange_credentials(BrokerConfig())
    assert creds.api_key == "key"
    assert creds.api_secret == "secret"
    assert creds.access_token == ""


def test_load_kite_credentials_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITE_API_KEY", "key")
    monkeypatch.setenv("KITE_ACCESS_TOKEN", "token")
    creds = load_kite_credentials(BrokerConfig())
    assert creds.api_key == "key"
    assert creds.access_token == "token"
