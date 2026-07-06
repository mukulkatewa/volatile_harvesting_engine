from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret-32-bytes-exactly-ok!!")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")


def test_create_and_verify_token() -> None:
    from vhe.auth.jwt_utils import UserClaims, create_token, verify_token

    token = create_token(user_id=1, email="test@example.com", name="Test User")
    claims = verify_token(token)
    assert isinstance(claims, UserClaims)
    assert claims.user_id == 1
    assert claims.email == "test@example.com"
    assert claims.name == "Test User"


def test_verify_invalid_token_raises() -> None:
    from jose import JWTError

    from vhe.auth.jwt_utils import verify_token

    with pytest.raises(JWTError):
        verify_token("not.a.valid.token")


def test_get_login_url_contains_client_id() -> None:
    from vhe.auth.google_oauth import get_login_url

    url = get_login_url(redirect_uri="http://localhost:8765/auth/google/callback")
    assert "test-client-id" in url
    assert "accounts.google.com" in url
    assert "openid" in url


def test_require_auth_raises_401_without_cookie() -> None:
    from fastapi import HTTPException

    from vhe.auth.middleware import require_auth

    with pytest.raises(HTTPException) as exc_info:
        require_auth(vhe_session=None)
    assert exc_info.value.status_code == 401


def test_require_auth_raises_401_with_bad_token() -> None:
    from fastapi import HTTPException

    from vhe.auth.middleware import require_auth

    with pytest.raises(HTTPException) as exc_info:
        require_auth(vhe_session="garbage.token.value")
    assert exc_info.value.status_code == 401


def test_require_auth_returns_claims_with_valid_token() -> None:
    from vhe.auth.jwt_utils import create_token
    from vhe.auth.middleware import require_auth

    token = create_token(user_id=42, email="user@vhe.dev", name="VHE User")
    claims = require_auth(vhe_session=token)
    assert claims.user_id == 42
    assert claims.email == "user@vhe.dev"
