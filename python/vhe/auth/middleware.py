from __future__ import annotations

from fastapi import Cookie, HTTPException
from jose import JWTError

from vhe.auth.jwt_utils import UserClaims, verify_token


def require_auth(vhe_session: str | None = Cookie(default=None)) -> UserClaims:
    if not vhe_session:
        raise HTTPException(status_code=401, detail="not authenticated")
    try:
        return verify_token(vhe_session)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="invalid or expired token") from exc
    except KeyError:
        raise HTTPException(status_code=503, detail="JWT_SECRET not configured in .env")
