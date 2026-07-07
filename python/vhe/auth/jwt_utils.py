from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jose import jwt


@dataclass(frozen=True, slots=True)
class UserClaims:
    user_id: int
    email: str
    name: str


def create_token(user_id: int, email: str, name: str) -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise KeyError("JWT_SECRET not configured in .env")
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "exp": datetime.now(tz=timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(
        payload,
        secret,
        algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
    )


def verify_token(token: str) -> UserClaims:
    payload = jwt.decode(
        token,
        os.environ["JWT_SECRET"],
        algorithms=[os.environ.get("JWT_ALGORITHM", "HS256")],
    )
    return UserClaims(
        user_id=int(payload["sub"]),
        email=payload["email"],
        name=payload["name"],
    )
