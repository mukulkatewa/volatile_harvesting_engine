# Phase 3: React Migration + Google Auth + Virtual Portfolio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the existing vanilla JS dashboard to React 18 + Vite + TypeScript + Tailwind CSS, add Google OAuth authentication via a backend-driven flow, and add a virtual portfolio scorecard where each signed-in user tracks their ₹75,000 virtual stake against the shared live session P&L.

**Architecture:** A `frontend/` Vite workspace builds a React SPA. FastAPI serves the compiled `dist/` as static files at `/`. The backend gains an `vhe/auth/` package (Google OAuth exchange + JWT cookie issuance) and a `users` table in the existing SQLite DB. All existing dashboard state flows through a `useWebSocket` React hook. Auth state flows through a `useAuth` context. Protected routes redirect to `/` if unauthenticated.

**Tech Stack:** React 18, Vite 5, TypeScript 5, Tailwind CSS 3, React Router 6, Recharts 2, @tanstack/react-query 5, authlib (Python), python-jose (Python), FastAPI, SQLite

**Prerequisite:** Phases 1 and 2 complete — the Risk tab content will be ported in Task 9.

---

## File Map

### Backend (Python)

| File | Action |
|------|--------|
| `python/vhe/auth/__init__.py` | Create — empty package marker |
| `python/vhe/auth/google_oauth.py` | Create — OAuth URL + code exchange |
| `python/vhe/auth/jwt_utils.py` | Create — JWT create/verify |
| `python/vhe/auth/middleware.py` | Create — FastAPI `require_auth` dependency |
| `python/vhe/storage/db.py` | Modify — add `users` table migration |
| `python/vhe/platform/server.py` | Modify — add auth routes + static serving for React dist |
| `pyproject.toml` | Modify — add authlib, python-jose |
| `python/tests/test_auth.py` | Create — auth unit tests |

### Frontend (React)

| File | Action |
|------|--------|
| `frontend/package.json` | Create — npm workspace config |
| `frontend/vite.config.ts` | Create — Vite config with proxy |
| `frontend/tailwind.config.ts` | Create — custom colors matching VHE design |
| `frontend/tsconfig.json` | Create — TypeScript config |
| `frontend/index.html` | Create — Vite entry HTML |
| `frontend/src/main.tsx` | Create — React entry point |
| `frontend/src/App.tsx` | Create — Router + QueryClient |
| `frontend/src/types/api.ts` | Create — TypeScript types for all API responses |
| `frontend/src/api/client.ts` | Create — typed fetch wrappers |
| `frontend/src/hooks/useWebSocket.ts` | Create — WS connection + state |
| `frontend/src/hooks/useAuth.ts` | Create — auth context + hook |
| `frontend/src/components/auth/LandingPage.tsx` | Create — hero + sign-in CTA |
| `frontend/src/components/auth/AuthCallback.tsx` | Create — OAuth callback handler |
| `frontend/src/components/auth/ProtectedRoute.tsx` | Create — auth guard wrapper |
| `frontend/src/components/layout/Sidebar.tsx` | Create — nav sidebar |
| `frontend/src/components/layout/Header.tsx` | Create — top bar with clock + session badge |
| `frontend/src/components/dashboard/Terminal.tsx` | Create — portfolio + quotes + risk |
| `frontend/src/components/dashboard/Strategies.tsx` | Create — grid plans + sentiment |
| `frontend/src/components/dashboard/Execution.tsx` | Create — fills + orders |
| `frontend/src/components/dashboard/Activity.tsx` | Create — paper stats + events |
| `frontend/src/components/risk/MonteCarloPanel.tsx` | Create — MC form + results |
| `frontend/src/components/risk/WalkForwardPanel.tsx` | Create — WF form + table |
| `frontend/src/components/profile/ProfilePage.tsx` | Create — user info + virtual capital |

---

## Task 1: Python Dependencies + Auth Package

**Files:**
- Modify: `pyproject.toml`
- Create: `python/vhe/auth/__init__.py`
- Create: `python/vhe/auth/google_oauth.py`
- Create: `python/vhe/auth/jwt_utils.py`
- Create: `python/vhe/auth/middleware.py`
- Create: `python/tests/test_auth.py`

- [ ] **Step 1.1: Add auth dependencies to pyproject.toml**

In `pyproject.toml`, find the `dependencies` list and add:

```toml
  "authlib>=1.3,<2",
  "python-jose[cryptography]>=3.3,<4",
```

- [ ] **Step 1.2: Install new dependencies**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && pip install "authlib>=1.3,<2" "python-jose[cryptography]>=3.3,<4"
```

Expected: both packages install without errors.

- [ ] **Step 1.3: Write failing auth tests**

Create `python/tests/test_auth.py`:

```python
from __future__ import annotations

import os

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
```

- [ ] **Step 1.4: Run tests — expect ImportError**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/test_auth.py -v 2>&1 | head -15
```

Expected: `ImportError: No module named 'vhe.auth'`

- [ ] **Step 1.5: Create auth package files**

Create `python/vhe/auth/__init__.py` (empty):

```python
```

Create `python/vhe/auth/jwt_utils.py`:

```python
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
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "exp": datetime.now(tz=timezone.utc) + timedelta(days=7),
    }
    return jwt.encode(
        payload,
        os.environ["JWT_SECRET"],
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
```

Create `python/vhe/auth/google_oauth.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx


@dataclass(frozen=True, slots=True)
class GoogleProfile:
    google_id: str
    email: str
    name: str


def get_login_url(redirect_uri: str) -> str:
    params = {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


async def exchange_code(code: str, redirect_uri: str) -> GoogleProfile:
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_resp.raise_for_status()
        info = user_resp.json()

    return GoogleProfile(
        google_id=info["sub"],
        email=info["email"],
        name=info.get("name", info.get("given_name", "")),
    )
```

Create `python/vhe/auth/middleware.py`:

```python
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
```

- [ ] **Step 1.6: Run auth tests — expect all pass**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/test_auth.py -v
```

Expected:
```
PASSED test_create_and_verify_token
PASSED test_verify_invalid_token_raises
PASSED test_get_login_url_contains_client_id
PASSED test_require_auth_raises_401_without_cookie
PASSED test_require_auth_raises_401_with_bad_token
PASSED test_require_auth_returns_claims_with_valid_token
6 passed
```

- [ ] **Step 1.7: Commit**

```bash
git add pyproject.toml python/vhe/auth/ python/tests/test_auth.py
git commit -m "feat: add Google OAuth + JWT auth package"
```

---

## Task 2: Users Table + Auth Routes in server.py

**Files:**
- Modify: `python/vhe/storage/db.py`
- Modify: `python/vhe/platform/server.py`

- [ ] **Step 2.1: Add users table to db.py `_init_schema`**

In `python/vhe/storage/db.py`, find the `_init_schema` method and add the `users` table to the `executescript` call. Find the existing SQL and append:

```python
                CREATE TABLE IF NOT EXISTS users (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    google_id           TEXT UNIQUE NOT NULL,
                    email               TEXT UNIQUE NOT NULL,
                    name                TEXT NOT NULL DEFAULT '',
                    virtual_capital_inr INTEGER NOT NULL DEFAULT 75000,
                    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                );
```

(Add it inside the `executescript("""...""")` string alongside the existing table definitions.)

- [ ] **Step 2.2: Add user DB helper methods to PlatformDatabase**

In `python/vhe/storage/db.py`, add these two methods to the `PlatformDatabase` class:

```python
    def upsert_user(self, google_id: str, email: str, name: str) -> int:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO users (google_id, email, name)
                VALUES (?, ?, ?)
                ON CONFLICT(google_id) DO UPDATE SET
                    email = excluded.email,
                    name  = excluded.name
                """,
                (google_id, email, name),
            )
            row = conn.execute(
                "SELECT id FROM users WHERE google_id = ?", (google_id,)
            ).fetchone()
        return int(row["id"])

    def get_user(self, user_id: int) -> dict | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT id, email, name, virtual_capital_inr, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def update_virtual_capital(self, user_id: int, capital_inr: int) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE users SET virtual_capital_inr = ? WHERE id = ?",
                (capital_inr, user_id),
            )
```

- [ ] **Step 2.3: Add auth routes to server.py**

In `python/vhe/platform/server.py`, add the following imports at the top (after existing imports):

```python
from fastapi import Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
```

Then add these routes after the existing control routes (before the `/favicon.ico` route):

```python
# ── Auth routes ──────────────────────────────────────────────────

_CALLBACK_PATH = "/auth/google/callback"


def _callback_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + _CALLBACK_PATH


@app.get("/auth/google/login")
async def google_login(request: Request) -> RedirectResponse:
    from vhe.auth.google_oauth import get_login_url
    url = get_login_url(redirect_uri=_callback_uri(request))
    return RedirectResponse(url=url)


@app.get(_CALLBACK_PATH)
async def google_callback(request: Request, code: str = "") -> RedirectResponse:
    from vhe.auth.google_oauth import exchange_code
    from vhe.auth.jwt_utils import create_token

    if not code:
        return RedirectResponse(url="/?error=no_code")
    try:
        profile = await exchange_code(code, redirect_uri=_callback_uri(request))
    except Exception:
        return RedirectResponse(url="/?error=oauth_failed")

    if runtime.database is None:
        return RedirectResponse(url="/?error=no_db")

    user_id = runtime.database.upsert_user(profile.google_id, profile.email, profile.name)
    token = create_token(user_id=user_id, email=profile.email, name=profile.name)

    response = RedirectResponse(url="/dashboard")
    response.set_cookie(
        key="vhe_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
    )
    return response


@app.post("/auth/logout")
async def logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie("vhe_session")
    return response


@app.get("/api/me")
async def api_me(claims=Depends(require_auth)) -> dict:
    if runtime.database is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    user = runtime.database.get_user(claims.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@app.put("/api/me/capital")
async def update_capital(body: dict, claims=Depends(require_auth)) -> dict:
    capital = int(body.get("virtual_capital_inr", 75000))
    if not (25_000 <= capital <= 500_000):
        raise HTTPException(status_code=422, detail="capital must be between ₹25,000 and ₹500,000")
    if runtime.database is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    runtime.database.update_virtual_capital(claims.user_id, capital)
    return runtime.database.get_user(claims.user_id)
```

Also add the import at the top of server.py:

```python
from vhe.auth.middleware import require_auth
```

- [ ] **Step 2.4: Verify server imports cleanly**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -c "from vhe.platform.server import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 2.5: Run full test suite**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/ -q 2>&1 | tail -5
```

Expected: all pass.

- [ ] **Step 2.6: Commit**

```bash
git add python/vhe/storage/db.py python/vhe/platform/server.py
git commit -m "feat: add users table, auth routes, and virtual capital endpoints"
```

---

## Task 3: Scaffold React + Vite + Tailwind

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`

- [ ] **Step 3.1: Check Node.js is available**

```bash
node --version && npm --version
```

Expected: Node ≥ 18.x, npm ≥ 9.x

- [ ] **Step 3.2: Create `frontend/package.json`**

Create `frontend/package.json`:

```json
{
  "name": "vhe-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2",
    "recharts": "^2.13.0",
    "@tanstack/react-query": "^5.56.2"
  },
  "devDependencies": {
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.13",
    "typescript": "^5.5.3",
    "vite": "^5.4.8"
  }
}
```

- [ ] **Step 3.3: Create `frontend/vite.config.ts`**

Create `frontend/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../python/vhe/platform/static",
    emptyOutDir: false,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8765",
      "/auth": "http://localhost:8765",
      "/ws": { target: "ws://localhost:8765", ws: true },
    },
  },
});
```

- [ ] **Step 3.4: Create `frontend/tailwind.config.ts`**

Create `frontend/tailwind.config.ts`:

```typescript
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-deep":     "#080b10",
        "bg-panel":    "#11161d",
        "bg-card":     "#161d27",
        "bg-elevated": "#1c2430",
        "vhe-green":   "#00d09c",
        "vhe-red":     "#ff6b6b",
        "vhe-amber":   "#f0b429",
        "vhe-blue":    "#387ed1",
        "text-primary":"#e8edf4",
        "text-muted":  "#8b97a8",
        "text-faint":  "#5c6778",
      },
      fontFamily: {
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 3.5: Create `frontend/tsconfig.json`**

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3.6: Create `frontend/index.html`**

Create `frontend/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>VHE — Volatility Harvesting Engine</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  </head>
  <body class="bg-bg-deep text-text-primary font-sans min-h-screen">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3.7: Create `frontend/src/main.tsx`**

First create the directory:

```bash
mkdir -p /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/frontend/src
```

Create `frontend/src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 3.8: Create `frontend/src/index.css`**

Create `frontend/src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    background-color: #080b10;
    color: #e8edf4;
  }
  body::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background:
      radial-gradient(circle at 12% 8%, rgba(56, 126, 209, 0.12), transparent 28%),
      radial-gradient(circle at 88% 0%, rgba(0, 208, 156, 0.08), transparent 24%);
    z-index: 0;
  }
}
```

- [ ] **Step 3.9: Also create `frontend/postcss.config.js`**

Create `frontend/postcss.config.js`:

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 3.10: Install npm dependencies**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/frontend && npm install
```

Expected: `node_modules/` created, no errors.

- [ ] **Step 3.11: Commit scaffold**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine
git add frontend/
git commit -m "feat: scaffold React + Vite + Tailwind frontend"
```

---

## Task 4: API Types + Client + WebSocket Hook

**Files:**
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/hooks/useWebSocket.ts`
- Create: `frontend/src/hooks/useAuth.ts`

- [ ] **Step 4.1: Create `frontend/src/types/api.ts`**

```bash
mkdir -p /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/frontend/src/types
mkdir -p /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/frontend/src/api
mkdir -p /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/frontend/src/hooks
```

Create `frontend/src/types/api.ts`:

```typescript
export interface Quote {
  symbol: string;
  ltp: number;
  timestamp: string;
  stale?: boolean;
}

export interface Portfolio {
  cash: number;
  equity: number;
  gross_exposure: number;
  gross_exposure_pct: number;
  positions: Record<string, { quantity: number; avg_price: number; unrealized_pnl: number }>;
}

export interface Controls {
  kill_switch: boolean;
  automation_paused: boolean;
  last_risk_reject: string | null;
  kill_switch_reason: string | null;
}

export interface GridPlan {
  symbol: string;
  regime: string;
  fair_value: number;
  current_price: number;
  levels_filled: number;
  total_levels: number;
}

export interface Fill {
  fill_id: string;
  symbol: string;
  side: "BUY" | "SELL";
  price: number;
  quantity: number;
  fees: number;
  reason: string;
  filled_at: string;
}

export interface VHEState {
  connected: boolean;
  mode: string;
  source: string;
  phase: number | string;
  server_time: string;
  portfolio: Portfolio;
  controls: Controls;
  quotes: Record<string, Quote>;
  plans: Record<string, GridPlan>;
  fills: Fill[];
  events: Array<{ category: string; message: string; severity: string; timestamp: string }>;
  capital?: Record<string, number>;
  market_session?: { status: string };
  strategy_status?: Record<string, unknown>;
  sentiment?: Record<string, unknown>;
}

export interface User {
  id: number;
  email: string;
  name: string;
  virtual_capital_inr: number;
  created_at: string;
}

export interface MonteCarloResult {
  var_95: number;
  cvar_95: number;
  p_ruin: number;
  drawdown_p95: number;
  kelly_fraction: number;
  pnl_percentiles: { p5: number; p25: number; p50: number; p75: number; p95: number };
  equity_curves: number[][];
  sim_count: number;
  trade_count: number;
}

export interface WFWindow {
  period: string;
  is_sharpe: number;
  oos_sharpe: number;
  oos_pnl: number;
  best_params: { atr_multiplier: number; max_levels: number };
}

export interface WFResult {
  windows: WFWindow[];
  wf_efficiency: number;
  verdict: "Not overfit" | "Marginal" | "Curve-fitted";
  param_stability: { atr_multiplier: number; stability_score: number };
}
```

- [ ] **Step 4.2: Create `frontend/src/api/client.ts`**

Create `frontend/src/api/client.ts`:

```typescript
import type { MonteCarloResult, User, VHEState, WFResult } from "../types/api";

async function fetchJSON<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const resp = await fetch(input, init);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(body.detail ?? resp.statusText);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  state: () => fetchJSON<VHEState>("/api/state"),
  me: () => fetchJSON<User>("/api/me"),
  updateCapital: (capital: number) =>
    fetchJSON<User>("/api/me/capital", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ virtual_capital_inr: capital }),
    }),
  logout: () => fetchJSON<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  runMonteCarlo: (payload: { symbol: string; bars_file: string; n_sims: number; initial_capital: number }) =>
    fetchJSON<MonteCarloResult>("/api/backtest/monte-carlo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  runWalkForward: (params: { symbol: string; bars_file: string; train_days: number; test_days: number }) => {
    const qs = new URLSearchParams(params as Record<string, string>);
    return fetchJSON<WFResult>(`/api/backtest/walk-forward?${qs}`);
  },
};
```

- [ ] **Step 4.3: Create `frontend/src/hooks/useWebSocket.ts`**

Create `frontend/src/hooks/useWebSocket.ts`:

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import type { VHEState } from "../types/api";

const INITIAL_STATE: VHEState = {
  connected: false,
  mode: "paper",
  source: "simulated",
  phase: 0,
  server_time: "",
  portfolio: { cash: 0, equity: 0, gross_exposure: 0, gross_exposure_pct: 0, positions: {} },
  controls: { kill_switch: false, automation_paused: false, last_risk_reject: null, kill_switch_reason: null },
  quotes: {},
  plans: {},
  fills: [],
  events: [],
};

export function useWebSocket() {
  const [state, setState] = useState<VHEState>(INITIAL_STATE);
  const ws = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${proto}://${window.location.host}/ws/state`);
    ws.current = socket;

    socket.onmessage = (ev) => {
      try {
        setState(JSON.parse(ev.data) as VHEState);
      } catch {
        // ignore malformed frames
      }
    };

    socket.onclose = () => {
      setState((prev) => ({ ...prev, connected: false }));
      setTimeout(connect, 1200);
    };

    socket.onerror = () => socket.close();
  }, []);

  useEffect(() => {
    connect();
    return () => ws.current?.close();
  }, [connect]);

  const postControl = useCallback(async (endpoint: string) => {
    const resp = await fetch(endpoint, { method: "POST" });
    if (resp.ok) setState(await resp.json());
  }, []);

  return { state, postControl };
}
```

- [ ] **Step 4.4: Create `frontend/src/hooks/useAuth.ts`**

Create `frontend/src/hooks/useAuth.ts`:

```typescript
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { User } from "../types/api";

export function useAuth() {
  const qc = useQueryClient();
  const { data: user, isLoading } = useQuery<User | null>({
    queryKey: ["me"],
    queryFn: () => api.me().catch(() => null),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const logout = async () => {
    await api.logout();
    qc.setQueryData(["me"], null);
    window.location.href = "/";
  };

  return { user: user ?? null, isLoading, logout };
}
```

- [ ] **Step 4.5: Commit hooks and types**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine
git add frontend/src/
git commit -m "feat: add API types, client, WebSocket hook, and auth hook"
```

---

## Task 5: App Router + Auth Context

**Files:**
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/components/auth/ProtectedRoute.tsx`

- [ ] **Step 5.1: Create `frontend/src/components/auth/ProtectedRoute.tsx`**

```bash
mkdir -p /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/frontend/src/components/auth
```

Create `frontend/src/components/auth/ProtectedRoute.tsx`:

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

interface Props {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: Props) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-bg-deep flex items-center justify-center">
        <span className="font-mono text-text-muted text-sm animate-pulse">Loading…</span>
      </div>
    );
  }

  if (!user) return <Navigate to="/" replace />;
  return <>{children}</>;
}
```

- [ ] **Step 5.2: Create `frontend/src/App.tsx`**

Create `frontend/src/App.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { LandingPage } from "./components/auth/LandingPage";
import { AuthCallback } from "./components/auth/AuthCallback";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { DashboardLayout } from "./components/layout/DashboardLayout";

const qc = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route
            path="/dashboard/*"
            element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePageLazy />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

import { lazy, Suspense } from "react";
const ProfilePageLazy = lazy(() =>
  import("./components/profile/ProfilePage").then((m) => ({ default: m.ProfilePage }))
);

function ProfilePageLazy2() {
  return (
    <Suspense fallback={<div className="p-8 text-text-muted font-mono text-sm">Loading…</div>}>
      <ProfilePageLazy />
    </Suspense>
  );
}
```

Wait — the lazy import has a naming conflict. Replace App.tsx with this corrected version:

Create `frontend/src/App.tsx`:

```tsx
import { lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { LandingPage } from "./components/auth/LandingPage";
import { AuthCallback } from "./components/auth/AuthCallback";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { DashboardLayout } from "./components/layout/DashboardLayout";

const LazyProfile = lazy(() =>
  import("./components/profile/ProfilePage").then((m) => ({ default: m.ProfilePage }))
);

function Fallback() {
  return (
    <div className="min-h-screen bg-bg-deep flex items-center justify-center">
      <span className="font-mono text-text-muted text-sm animate-pulse">Loading…</span>
    </div>
  );
}

const qc = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route
            path="/dashboard/*"
            element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Suspense fallback={<Fallback />}>
                  <LazyProfile />
                </Suspense>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 5.3: Commit**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine
git add frontend/src/App.tsx frontend/src/components/auth/ProtectedRoute.tsx
git commit -m "feat: add React router, QueryClient, and ProtectedRoute"
```

---

## Task 6: Auth Pages (Landing + Callback)

**Files:**
- Create: `frontend/src/components/auth/LandingPage.tsx`
- Create: `frontend/src/components/auth/AuthCallback.tsx`

- [ ] **Step 6.1: Create LandingPage.tsx**

Create `frontend/src/components/auth/LandingPage.tsx`:

```tsx
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

export function LandingPage() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && user) navigate("/dashboard", { replace: true });
  }, [user, isLoading, navigate]);

  const params = new URLSearchParams(window.location.search);
  const error = params.get("error");

  return (
    <div className="min-h-screen bg-bg-deep flex flex-col items-center justify-center relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-[10%] w-[400px] h-[400px] bg-vhe-blue/10 rounded-full blur-3xl" />
        <div className="absolute top-0 right-[5%] w-[300px] h-[300px] bg-vhe-green/8 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 flex flex-col items-center gap-8 max-w-md w-full px-6">
        {/* Brand */}
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-vhe-blue to-vhe-green flex items-center justify-center text-2xl font-bold shadow-lg shadow-vhe-green/20">
            V
          </div>
          <div className="text-center">
            <h1 className="text-3xl font-bold text-text-primary font-sans tracking-tight">
              VHE
            </h1>
            <p className="text-text-muted text-sm font-mono uppercase tracking-widest mt-1">
              Volatility Harvesting Engine
            </p>
          </div>
        </div>

        {/* Description */}
        <div className="text-center space-y-2">
          <p className="text-text-primary font-sans text-base leading-relaxed">
            Systematic intraday grid trading with real-time sentiment analysis,
            Monte Carlo risk simulation, and walk-forward validation.
          </p>
          <p className="text-text-muted font-sans text-sm">
            Paper trading · NSE equities · ATR-driven grid strategy
          </p>
        </div>

        {/* Feature pills */}
        <div className="flex flex-wrap gap-2 justify-center">
          {["Grid Strategy", "Pair Spread", "Sentiment Engine", "Monte Carlo", "Walk-Forward"].map((f) => (
            <span
              key={f}
              className="px-3 py-1 rounded-full bg-bg-card border border-white/10 text-text-muted text-xs font-mono"
            >
              {f}
            </span>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div className="w-full p-3 rounded-lg bg-vhe-red/10 border border-vhe-red/30 text-vhe-red text-sm font-mono text-center">
            Authentication failed: {error}
          </div>
        )}

        {/* CTA */}
        <a
          href="/auth/google/login"
          className="w-full flex items-center justify-center gap-3 py-3 px-6 rounded-xl bg-bg-card border border-white/15 text-text-primary font-sans font-semibold text-sm hover:border-vhe-blue/50 hover:bg-bg-elevated transition-all duration-200 group"
        >
          <svg viewBox="0 0 24 24" className="w-5 h-5 shrink-0" aria-hidden>
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Sign in with Google
          <span className="ml-auto text-text-faint group-hover:text-text-muted transition-colors">→</span>
        </a>

        <p className="text-text-faint text-xs font-mono text-center">
          Paper trading only · No real money · For portfolio demonstration
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 6.2: Create AuthCallback.tsx**

Create `frontend/src/components/auth/AuthCallback.tsx`:

```tsx
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

export function AuthCallback() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  useEffect(() => {
    api.me()
      .then((user) => {
        qc.setQueryData(["me"], user);
        navigate("/dashboard", { replace: true });
      })
      .catch(() => navigate("/?error=session_failed", { replace: true }));
  }, [navigate, qc]);

  return (
    <div className="min-h-screen bg-bg-deep flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-vhe-blue to-vhe-green animate-pulse" />
        <span className="font-mono text-text-muted text-sm">Signing you in…</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 6.3: Commit**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine
git add frontend/src/components/auth/
git commit -m "feat: add landing page and auth callback components"
```

---

## Task 7: Layout Components (Sidebar + Header + DashboardLayout)

**Files:**
- Create: `frontend/src/components/layout/Sidebar.tsx`
- Create: `frontend/src/components/layout/Header.tsx`
- Create: `frontend/src/components/layout/DashboardLayout.tsx`

- [ ] **Step 7.1: Create directories**

```bash
mkdir -p /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/frontend/src/components/layout
```

- [ ] **Step 7.2: Create Sidebar.tsx**

Create `frontend/src/components/layout/Sidebar.tsx`:

```tsx
import { NavLink } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

const NAV = [
  { label: "Terminal",   to: "/dashboard" },
  { label: "Strategies", to: "/dashboard/strategies" },
  { label: "Execution",  to: "/dashboard/execution" },
  { label: "Activity",   to: "/dashboard/activity" },
  { label: "Risk",       to: "/dashboard/risk" },
];

export function Sidebar({ sentiment }: { sentiment?: Record<string, unknown> }) {
  const { user, logout } = useAuth();

  return (
    <aside className="sticky top-0 h-screen w-[220px] flex flex-col gap-6 px-4 py-5 border-r border-white/[0.08] bg-bg-deep/95 backdrop-blur-xl z-10">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-base bg-gradient-to-br from-vhe-blue to-vhe-green shadow-lg shadow-vhe-green/20">
          V
        </div>
        <div>
          <strong className="block text-[15px] text-text-primary font-sans font-bold">VHE</strong>
          <span className="text-text-muted text-[11px] font-sans uppercase tracking-widest">Volatility Engine</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1.5">
        {NAV.map(({ label, to }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/dashboard"}
            className={({ isActive }) =>
              `px-3 py-2.5 rounded-[10px] text-[13px] font-semibold font-sans transition-all duration-180 ${
                isActive
                  ? "text-text-primary bg-vhe-blue/16 border border-vhe-blue/35"
                  : "text-text-muted border border-transparent hover:text-text-primary hover:bg-white/[0.03]"
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      {user && (
        <div className="mt-auto flex flex-col gap-2">
          <div className="text-[11px] font-mono text-text-faint truncate">{user.email}</div>
          <div className="text-[11px] font-mono text-vhe-green">
            ₹{user.virtual_capital_inr.toLocaleString("en-IN")} virtual
          </div>
          <NavLink
            to="/profile"
            className="text-[12px] font-sans text-text-muted hover:text-text-primary transition-colors"
          >
            Profile →
          </NavLink>
          <button
            onClick={logout}
            className="text-left text-[12px] font-sans text-text-faint hover:text-vhe-red transition-colors"
          >
            Sign out
          </button>
        </div>
      )}
    </aside>
  );
}
```

- [ ] **Step 7.3: Create Header.tsx**

Create `frontend/src/components/layout/Header.tsx`:

```tsx
import { useEffect, useState } from "react";
import type { VHEState } from "../../types/api";

function toIST(date: Date): string {
  return date.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });
}

export function Header({ state }: { state: VHEState }) {
  const [clock, setClock] = useState(toIST(new Date()));
  useEffect(() => {
    const id = setInterval(() => setClock(toIST(new Date())), 1000);
    return () => clearInterval(id);
  }, []);

  const sessionStatus = state.market_session?.status ?? "unknown";
  const sessionCls =
    sessionStatus === "open" ? "text-vhe-green border-vhe-green/30 bg-vhe-green/10"
    : sessionStatus === "force_exit" ? "text-vhe-red border-vhe-red/30 bg-vhe-red/10"
    : "text-vhe-amber border-vhe-amber/30 bg-vhe-amber/10";

  return (
    <header className="sticky top-0 z-10 flex items-center justify-between px-6 py-3 border-b border-white/[0.06] bg-bg-deep/90 backdrop-blur-xl">
      <div className="flex items-center gap-4">
        <time className="font-mono text-[18px] font-semibold text-vhe-green">{clock}</time>
        <span className={`text-[11px] font-bold font-mono px-2 py-0.5 rounded border uppercase ${sessionCls}`}>
          {sessionStatus}
        </span>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${state.connected ? "bg-vhe-green animate-pulse" : "bg-vhe-red"}`} />
          <span className="text-[13px] text-text-muted font-sans">
            {state.connected ? "Live" : "Reconnecting"}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3 text-[12px] font-mono text-text-muted">
        <span>Phase <strong className="text-text-primary">{state.phase}</strong></span>
        <span>Mode <strong className="text-text-primary capitalize">{state.mode}</strong></span>
        <span>Feed <strong className="text-text-primary">{state.source}</strong></span>
      </div>
    </header>
  );
}
```

- [ ] **Step 7.4: Create DashboardLayout.tsx**

Create `frontend/src/components/layout/DashboardLayout.tsx`:

```tsx
import { Route, Routes } from "react-router-dom";
import { useWebSocket } from "../../hooks/useWebSocket";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { Terminal } from "../dashboard/Terminal";
import { Strategies } from "../dashboard/Strategies";
import { Execution } from "../dashboard/Execution";
import { Activity } from "../dashboard/Activity";
import { RiskTab } from "../risk/RiskTab";

export function DashboardLayout() {
  const { state, postControl } = useWebSocket();

  return (
    <div className="flex min-h-screen bg-bg-deep">
      <Sidebar sentiment={state.sentiment} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header state={state} />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route index element={<Terminal state={state} postControl={postControl} />} />
            <Route path="strategies" element={<Strategies state={state} />} />
            <Route path="execution" element={<Execution state={state} postControl={postControl} />} />
            <Route path="activity" element={<Activity state={state} />} />
            <Route path="risk" element={<RiskTab />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 7.5: Commit**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine
git add frontend/src/components/layout/
git commit -m "feat: add Sidebar, Header, and DashboardLayout"
```

---

## Task 8: Dashboard Tabs (Terminal, Strategies, Execution, Activity)

**Files:**
- Create: `frontend/src/components/dashboard/Terminal.tsx`
- Create: `frontend/src/components/dashboard/Strategies.tsx`
- Create: `frontend/src/components/dashboard/Execution.tsx`
- Create: `frontend/src/components/dashboard/Activity.tsx`

- [ ] **Step 8.1: Create directories**

```bash
mkdir -p /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/frontend/src/components/dashboard
```

- [ ] **Step 8.2: Create Terminal.tsx**

Create `frontend/src/components/dashboard/Terminal.tsx`:

```tsx
import type { VHEState } from "../../types/api";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const PCT = (v: number) => `${(v * 100).toFixed(2)}%`;

interface Props { state: VHEState; postControl: (endpoint: string) => Promise<void> }

export function Terminal({ state, postControl }: Props) {
  const p = state.portfolio;
  const ctrl = state.controls;
  const equity = p.equity ?? p.cash ?? 0;
  const pnl = equity - 75000;
  const pnlCls = pnl >= 0 ? "text-vhe-green" : "text-vhe-red";

  return (
    <div className="p-6 space-y-6">
      {/* Equity row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Equity", value: INR.format(equity), cls: "" },
          { label: "Session P&L", value: INR.format(pnl), cls: pnlCls },
          { label: "Gross Exposure", value: INR.format(p.gross_exposure ?? 0), cls: "" },
          { label: "Exposure %", value: PCT(p.gross_exposure_pct ?? 0), cls: "" },
        ].map(({ label, value, cls }) => (
          <div key={label} className="bg-bg-card rounded-xl border border-white/[0.08] p-4">
            <div className="text-[10px] font-mono font-bold text-text-muted uppercase tracking-wider">{label}</div>
            <div className={`text-xl font-mono font-semibold mt-1 ${cls || "text-text-primary"}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* Risk status */}
      {(ctrl.kill_switch || ctrl.automation_paused || ctrl.last_risk_reject) && (
        <div className="flex gap-3 flex-wrap">
          {ctrl.kill_switch && (
            <span className="px-3 py-1 rounded-full bg-vhe-red/10 border border-vhe-red/30 text-vhe-red text-xs font-mono font-bold">
              KILL SWITCH
            </span>
          )}
          {ctrl.automation_paused && (
            <span className="px-3 py-1 rounded-full bg-vhe-amber/10 border border-vhe-amber/30 text-vhe-amber text-xs font-mono font-bold">
              PAUSED
            </span>
          )}
          {ctrl.last_risk_reject && (
            <span className="px-3 py-1 rounded-full bg-bg-card border border-white/10 text-text-muted text-xs font-mono">
              Last reject: {ctrl.last_risk_reject}
            </span>
          )}
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2 flex-wrap">
        {[
          { label: "Pause",      endpoint: "/api/control/pause",       cls: "border-vhe-amber/30 text-vhe-amber hover:bg-vhe-amber/10" },
          { label: "Resume",     endpoint: "/api/control/resume",      cls: "border-vhe-green/30 text-vhe-green hover:bg-vhe-green/10" },
          { label: "Kill",       endpoint: "/api/control/kill",        cls: "border-vhe-red/30 text-vhe-red hover:bg-vhe-red/10" },
          { label: "Demo Fill",  endpoint: "/api/control/demo-fill",   cls: "border-white/15 text-text-muted hover:bg-white/5" },
          { label: "Reset",      endpoint: "/api/control/reset-paper", cls: "border-white/15 text-text-muted hover:bg-white/5" },
        ].map(({ label, endpoint, cls }) => (
          <button
            key={label}
            onClick={() => postControl(endpoint)}
            className={`px-3 py-1.5 rounded-lg border text-xs font-sans font-semibold transition-colors ${cls}`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Quotes table */}
      {Object.keys(state.quotes).length > 0 && (
        <div className="bg-bg-card rounded-xl border border-white/[0.08] overflow-hidden">
          <div className="px-4 py-3 border-b border-white/[0.06] text-[11px] font-mono font-bold text-text-muted uppercase tracking-wider">
            Live Quotes
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-mono font-bold text-text-faint uppercase">
                  <th className="text-left px-4 py-2">Symbol</th>
                  <th className="text-right px-4 py-2">LTP</th>
                  <th className="text-right px-4 py-2">Regime</th>
                </tr>
              </thead>
              <tbody>
                {Object.values(state.quotes).map((q) => (
                  <tr key={q.symbol} className="border-t border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="px-4 py-2 font-mono font-semibold text-text-primary">{q.symbol}</td>
                    <td className="px-4 py-2 font-mono text-right text-vhe-green">{INR.format(q.ltp)}</td>
                    <td className="px-4 py-2 font-mono text-right text-text-muted text-xs">
                      {state.plans?.[q.symbol]?.regime ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 8.3: Create Strategies.tsx**

Create `frontend/src/components/dashboard/Strategies.tsx`:

```tsx
import type { VHEState } from "../../types/api";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function Strategies({ state }: { state: VHEState }) {
  const plans = Object.values(state.plans ?? {});
  return (
    <div className="p-6 space-y-6">
      <h2 className="text-lg font-bold font-sans text-text-primary">Grid Plans</h2>
      {plans.length === 0 ? (
        <p className="text-text-muted font-mono text-sm">No active grid plans.</p>
      ) : (
        <div className="bg-bg-card rounded-xl border border-white/[0.08] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-mono font-bold text-text-faint uppercase border-b border-white/[0.06]">
                  <th className="text-left px-4 py-2">Symbol</th>
                  <th className="text-right px-4 py-2">Regime</th>
                  <th className="text-right px-4 py-2">Fair Value</th>
                  <th className="text-right px-4 py-2">LTP</th>
                  <th className="text-right px-4 py-2">Levels</th>
                </tr>
              </thead>
              <tbody>
                {plans.map((p) => (
                  <tr key={p.symbol} className="border-t border-white/[0.04]">
                    <td className="px-4 py-2 font-mono font-semibold text-text-primary">{p.symbol}</td>
                    <td className="px-4 py-2 font-mono text-right text-xs text-text-muted">{p.regime}</td>
                    <td className="px-4 py-2 font-mono text-right">{INR.format(p.fair_value)}</td>
                    <td className="px-4 py-2 font-mono text-right text-vhe-green">{INR.format(p.current_price)}</td>
                    <td className="px-4 py-2 font-mono text-right text-text-muted">
                      {p.levels_filled}/{p.total_levels}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 8.4: Create Execution.tsx**

Create `frontend/src/components/dashboard/Execution.tsx`:

```tsx
import type { VHEState } from "../../types/api";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function Execution({ state, postControl }: { state: VHEState; postControl: (e: string) => Promise<void> }) {
  const fills = [...(state.fills ?? [])].reverse().slice(0, 25);
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold font-sans text-text-primary">Paper Fill Tape</h2>
        <button
          onClick={() => postControl("/api/control/demo-fill")}
          className="px-3 py-1.5 rounded-lg border border-white/15 text-text-muted text-xs font-sans font-semibold hover:bg-white/5 transition-colors"
        >
          Demo Fill
        </button>
      </div>
      {fills.length === 0 ? (
        <p className="text-text-muted font-mono text-sm">No fills yet.</p>
      ) : (
        <div className="bg-bg-card rounded-xl border border-white/[0.08] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-mono font-bold text-text-faint uppercase border-b border-white/[0.06]">
                  <th className="text-left px-4 py-2">Time</th>
                  <th className="text-left px-4 py-2">Symbol</th>
                  <th className="text-right px-4 py-2">Side</th>
                  <th className="text-right px-4 py-2">Price</th>
                  <th className="text-right px-4 py-2">Qty</th>
                  <th className="text-right px-4 py-2">Reason</th>
                </tr>
              </thead>
              <tbody>
                {fills.map((f) => (
                  <tr key={f.fill_id} className="border-t border-white/[0.04]">
                    <td className="px-4 py-2 font-mono text-text-faint text-xs">
                      {new Date(f.filled_at).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })}
                    </td>
                    <td className="px-4 py-2 font-mono font-semibold text-text-primary">{f.symbol}</td>
                    <td className={`px-4 py-2 font-mono font-bold text-right ${f.side === "BUY" ? "text-vhe-green" : "text-vhe-red"}`}>
                      {f.side}
                    </td>
                    <td className="px-4 py-2 font-mono text-right">{INR.format(f.price)}</td>
                    <td className="px-4 py-2 font-mono text-right text-text-muted">{f.quantity}</td>
                    <td className="px-4 py-2 font-mono text-right text-text-faint text-xs">{f.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 8.5: Create Activity.tsx**

Create `frontend/src/components/dashboard/Activity.tsx`:

```tsx
import type { VHEState } from "../../types/api";

export function Activity({ state }: { state: VHEState }) {
  const events = [...(state.events ?? [])].reverse().slice(0, 50);
  const SEV: Record<string, string> = {
    info: "text-text-muted",
    warning: "text-vhe-amber",
    danger: "text-vhe-red",
    success: "text-vhe-green",
  };
  return (
    <div className="p-6 space-y-6">
      <h2 className="text-lg font-bold font-sans text-text-primary">Event Log</h2>
      {events.length === 0 ? (
        <p className="text-text-muted font-mono text-sm">No events yet.</p>
      ) : (
        <div className="bg-bg-card rounded-xl border border-white/[0.08] divide-y divide-white/[0.04]">
          {events.map((ev, i) => (
            <div key={i} className="px-4 py-2.5 flex items-start gap-3">
              <span className="font-mono text-[10px] text-text-faint pt-0.5 shrink-0">
                {new Date(ev.timestamp).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })}
              </span>
              <span className={`text-xs font-mono uppercase font-bold w-16 shrink-0 ${SEV[ev.severity] ?? "text-text-muted"}`}>
                {ev.category}
              </span>
              <span className="text-sm font-sans text-text-primary">{ev.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 8.6: Commit**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine
git add frontend/src/components/dashboard/
git commit -m "feat: add Terminal, Strategies, Execution, and Activity dashboard tabs"
```

---

## Task 9: Risk Tab (MC + WF Panels)

**Files:**
- Create: `frontend/src/components/risk/RiskTab.tsx`
- Create: `frontend/src/components/risk/MonteCarloPanel.tsx`
- Create: `frontend/src/components/risk/WalkForwardPanel.tsx`

- [ ] **Step 9.1: Create directories**

```bash
mkdir -p /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/frontend/src/components/risk
```

- [ ] **Step 9.2: Create MonteCarloPanel.tsx**

Create `frontend/src/components/risk/MonteCarloPanel.tsx`:

```tsx
import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../../api/client";
import type { MonteCarloResult } from "../../types/api";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function MonteCarloPanel() {
  const [symbol, setSymbol] = useState("");
  const [barsFile, setBarsFile] = useState("");
  const [nSims, setNSims] = useState(5000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MonteCarloResult | null>(null);

  const run = async () => {
    if (!symbol.trim() || !barsFile.trim()) { setError("Symbol and bars_file required"); return; }
    setError(null);
    setLoading(true);
    try {
      const r = await api.runMonteCarlo({ symbol: symbol.trim().toUpperCase(), bars_file: barsFile.trim(), n_sims: nSims, initial_capital: 75000 });
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const pctData = result
    ? Object.entries(result.pnl_percentiles).map(([k, v]) => ({ label: k.toUpperCase(), value: v }))
    : [];

  const curveData = result?.equity_curves?.[0]?.map((_, i) => ({
    trade: i,
    ...Object.fromEntries(result.equity_curves.slice(0, 20).map((c, j) => [`s${j}`, c[i]])),
    median: result.equity_curves
      .slice(0, 20)
      .map((c) => c[i])
      .sort((a, b) => a - b)[10] ?? 0,
  })) ?? [];

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-bold font-sans text-text-primary">Monte Carlo Risk Analysis</h2>

      {/* Controls */}
      <div className="flex gap-2 flex-wrap">
        <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="Symbol e.g. RELIANCE"
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg placeholder:text-text-faint min-w-[180px]" />
        <input value={barsFile} onChange={(e) => setBarsFile(e.target.value)} placeholder="data/RELIANCE.csv"
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg placeholder:text-text-faint min-w-[200px]" />
        <input value={nSims} onChange={(e) => setNSims(Number(e.target.value))} type="number" min={100} max={100000}
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg w-28" />
        <button onClick={run} disabled={loading}
          className="px-4 py-2 rounded-lg bg-vhe-green/10 border border-vhe-green/30 text-vhe-green text-sm font-semibold font-sans hover:bg-vhe-green/20 disabled:opacity-50 transition-colors">
          {loading ? "Running…" : "Run MC"}
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-vhe-red/10 border border-vhe-red/30 text-vhe-red text-sm font-mono">{error}</div>
      )}

      {result && (
        <>
          {/* Metric cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: "Median P&L",  value: INR.format(result.pnl_percentiles.p50), cls: result.pnl_percentiles.p50 >= 0 ? "text-vhe-green" : "text-vhe-red" },
              { label: "VaR 95%",     value: INR.format(result.var_95 - 75000), cls: "text-vhe-red" },
              { label: "P(Ruin)",     value: `${(result.p_ruin * 100).toFixed(1)}%`, cls: result.p_ruin < 0.05 ? "text-vhe-green" : result.p_ruin < 0.15 ? "text-vhe-amber" : "text-vhe-red" },
              { label: "Kelly f*",    value: `${(result.kelly_fraction * 100).toFixed(1)}%`, cls: "text-vhe-blue" },
              { label: "CVaR 95%",    value: INR.format(result.cvar_95 - 75000), cls: "text-vhe-red" },
              { label: "Max DD P95",  value: `${(result.drawdown_p95 * 100).toFixed(1)}%`, cls: result.drawdown_p95 > 0.05 ? "text-vhe-amber" : "text-vhe-green" },
              { label: "Trade Count", value: String(result.trade_count), cls: "text-text-primary" },
              { label: "Simulations", value: String(result.sim_count), cls: "text-text-primary" },
            ].map(({ label, value, cls }) => (
              <div key={label} className="bg-bg-card rounded-xl border border-white/[0.08] p-4">
                <div className="text-[10px] font-mono font-bold text-text-muted uppercase tracking-wider">{label}</div>
                <div className={`text-xl font-mono font-semibold mt-1 ${cls}`}>{value}</div>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-bg-card rounded-xl border border-white/[0.08] p-4">
              <div className="text-[11px] font-mono font-bold text-text-muted uppercase tracking-wider mb-4">P&L Percentiles</div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={pctData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                  <XAxis dataKey="label" tick={{ fill: "#8b97a8", fontSize: 11, fontFamily: "IBM Plex Mono" }} />
                  <YAxis tick={{ fill: "#8b97a8", fontSize: 11, fontFamily: "IBM Plex Mono" }} />
                  <Tooltip
                    contentStyle={{ background: "#161d27", border: "1px solid rgba(148,163,184,0.15)", borderRadius: "8px" }}
                    formatter={(v: number) => INR.format(v)}
                  />
                  <Bar dataKey="value" fill="#387ed1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-bg-card rounded-xl border border-white/[0.08] p-4">
              <div className="text-[11px] font-mono font-bold text-text-muted uppercase tracking-wider mb-4">Equity Scenarios</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={curveData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                  <XAxis dataKey="trade" tick={false} />
                  <YAxis tick={{ fill: "#8b97a8", fontSize: 11, fontFamily: "IBM Plex Mono" }} />
                  <Tooltip
                    contentStyle={{ background: "#161d27", border: "1px solid rgba(148,163,184,0.15)", borderRadius: "8px" }}
                    formatter={(v: number) => INR.format(v)}
                  />
                  {Array.from({ length: Math.min(20, result.equity_curves.length) }, (_, j) => (
                    <Line key={j} type="monotone" dataKey={`s${j}`} stroke="rgba(56,126,209,0.2)" dot={false} strokeWidth={1} />
                  ))}
                  <Line type="monotone" dataKey="median" stroke="#00d09c" strokeWidth={2} dot={false} name="Median" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 9.3: Create WalkForwardPanel.tsx**

Create `frontend/src/components/risk/WalkForwardPanel.tsx`:

```tsx
import { useState } from "react";
import { api } from "../../api/client";
import type { WFResult } from "../../types/api";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function WalkForwardPanel() {
  const [symbol, setSymbol] = useState("");
  const [barsFile, setBarsFile] = useState("");
  const [trainDays, setTrainDays] = useState(60);
  const [testDays, setTestDays] = useState(15);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<WFResult | null>(null);

  const run = async () => {
    if (!symbol.trim() || !barsFile.trim()) { setError("Symbol and bars_file required"); return; }
    setError(null);
    setLoading(true);
    try {
      const r = await api.runWalkForward({ symbol: symbol.trim().toUpperCase(), bars_file: barsFile.trim(), train_days: trainDays, test_days: testDays });
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const verdictCls = result?.verdict === "Not overfit"
    ? "bg-vhe-green/10 border-vhe-green/30 text-vhe-green"
    : result?.verdict === "Marginal"
    ? "bg-vhe-amber/10 border-vhe-amber/30 text-vhe-amber"
    : "bg-vhe-red/10 border-vhe-red/30 text-vhe-red";

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-bold font-sans text-text-primary">Walk-Forward Validation</h2>

      <div className="flex gap-2 flex-wrap">
        <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="Symbol"
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg placeholder:text-text-faint min-w-[160px]" />
        <input value={barsFile} onChange={(e) => setBarsFile(e.target.value)} placeholder="data/RELIANCE.csv"
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg placeholder:text-text-faint min-w-[200px]" />
        <input value={trainDays} onChange={(e) => setTrainDays(Number(e.target.value))} type="number" min={10} max={250}
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg w-24" placeholder="Train days" />
        <input value={testDays} onChange={(e) => setTestDays(Number(e.target.value))} type="number" min={5} max={60}
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg w-24" placeholder="Test days" />
        <button onClick={run} disabled={loading}
          className="px-4 py-2 rounded-lg bg-vhe-blue/10 border border-vhe-blue/30 text-vhe-blue text-sm font-semibold font-sans hover:bg-vhe-blue/20 disabled:opacity-50 transition-colors">
          {loading ? "Running…" : "Run WF"}
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-vhe-red/10 border border-vhe-red/30 text-vhe-red text-sm font-mono">{error}</div>
      )}

      {result && (
        <>
          <div className="flex gap-3 flex-wrap items-center">
            <span className={`px-4 py-1.5 rounded-full border text-xs font-mono font-bold ${verdictCls}`}>
              {result.verdict}
            </span>
            <span className="text-text-muted font-mono text-sm">
              WF Efficiency: <strong className="text-text-primary">{result.wf_efficiency.toFixed(3)}</strong>
            </span>
            <span className="text-text-muted font-mono text-sm">
              Stable ATR Mult: <strong className="text-text-primary">{result.param_stability.atr_multiplier}</strong>
            </span>
            <span className="text-text-muted font-mono text-sm">
              Stability: <strong className="text-text-primary">{(result.param_stability.stability_score * 100).toFixed(0)}%</strong>
            </span>
            <span className="text-text-muted font-mono text-sm">
              {result.windows.length} windows
            </span>
          </div>

          <div className="bg-bg-card rounded-xl border border-white/[0.08] overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] font-mono font-bold text-text-faint uppercase border-b border-white/[0.06]">
                    <th className="text-left px-4 py-2">Period</th>
                    <th className="text-right px-4 py-2">IS Sharpe</th>
                    <th className="text-right px-4 py-2">OOS Sharpe</th>
                    <th className="text-right px-4 py-2">OOS P&L</th>
                    <th className="text-right px-4 py-2">ATR Mult</th>
                    <th className="text-right px-4 py-2">Max Levels</th>
                  </tr>
                </thead>
                <tbody>
                  {result.windows.map((w, i) => (
                    <tr key={i} className="border-t border-white/[0.04] hover:bg-white/[0.02]">
                      <td className="px-4 py-2 font-mono text-text-faint text-xs">{w.period}</td>
                      <td className="px-4 py-2 font-mono text-right text-text-primary">{w.is_sharpe.toFixed(2)}</td>
                      <td className={`px-4 py-2 font-mono text-right ${w.oos_sharpe >= 0 ? "text-vhe-green" : "text-vhe-red"}`}>
                        {w.oos_sharpe.toFixed(2)}
                      </td>
                      <td className={`px-4 py-2 font-mono text-right ${w.oos_pnl >= 0 ? "text-vhe-green" : "text-vhe-red"}`}>
                        {INR.format(w.oos_pnl)}
                      </td>
                      <td className="px-4 py-2 font-mono text-right text-text-muted">{w.best_params.atr_multiplier}</td>
                      <td className="px-4 py-2 font-mono text-right text-text-muted">{w.best_params.max_levels}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 9.4: Create RiskTab.tsx**

Create `frontend/src/components/risk/RiskTab.tsx`:

```tsx
import { MonteCarloPanel } from "./MonteCarloPanel";
import { WalkForwardPanel } from "./WalkForwardPanel";

export function RiskTab() {
  return (
    <div className="p-6 space-y-12">
      <MonteCarloPanel />
      <div className="border-t border-white/[0.08]" />
      <WalkForwardPanel />
    </div>
  );
}
```

- [ ] **Step 9.5: Commit**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine
git add frontend/src/components/risk/
git commit -m "feat: add Risk tab with Monte Carlo and Walk-Forward panels"
```

---

## Task 10: Profile Page

**Files:**
- Create: `frontend/src/components/profile/ProfilePage.tsx`

- [ ] **Step 10.1: Create directory and ProfilePage.tsx**

```bash
mkdir -p /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/frontend/src/components/profile
```

Create `frontend/src/components/profile/ProfilePage.tsx`:

```tsx
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../hooks/useAuth";
import { api } from "../../api/client";
import { useWebSocket } from "../../hooks/useWebSocket";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function ProfilePage() {
  const { user, logout } = useAuth();
  const { state } = useWebSocket();
  const qc = useQueryClient();
  const [capital, setCapital] = useState(user?.virtual_capital_inr ?? 75000);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!user) return null;

  // Virtual portfolio calculation
  const equity = state.portfolio?.equity ?? 0;
  const initialEngineCapital = 75000;
  const sessionPnlPct = initialEngineCapital > 0 ? (equity - initialEngineCapital) / initialEngineCapital : 0;
  const userEquity = user.virtual_capital_inr * (1 + sessionPnlPct);
  const userPnl = userEquity - user.virtual_capital_inr;

  const saveCapital = async () => {
    if (capital < 25000 || capital > 500000) { setErr("Must be between ₹25,000 and ₹5,00,000"); return; }
    setErr(null);
    setSaving(true);
    try {
      const updated = await api.updateCapital(capital);
      qc.setQueryData(["me"], updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-deep p-8">
      <div className="max-w-lg mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-vhe-blue to-vhe-green flex items-center justify-center text-lg font-bold">
            {user.name[0]?.toUpperCase() ?? "U"}
          </div>
          <div>
            <h1 className="text-xl font-bold font-sans text-text-primary">{user.name}</h1>
            <p className="text-text-muted font-mono text-sm">{user.email}</p>
          </div>
        </div>

        {/* Virtual Portfolio */}
        <div className="bg-bg-card rounded-xl border border-white/[0.08] p-5 space-y-4">
          <h2 className="text-sm font-bold font-sans text-text-muted uppercase tracking-wider">Virtual Portfolio</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-[10px] font-mono text-text-faint uppercase tracking-wider">Starting Capital</div>
              <div className="text-xl font-mono font-semibold text-text-primary mt-1">
                {INR.format(user.virtual_capital_inr)}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-mono text-text-faint uppercase tracking-wider">Current Value</div>
              <div className="text-xl font-mono font-semibold text-vhe-green mt-1">{INR.format(userEquity)}</div>
            </div>
            <div>
              <div className="text-[10px] font-mono text-text-faint uppercase tracking-wider">Session P&L</div>
              <div className={`text-xl font-mono font-semibold mt-1 ${userPnl >= 0 ? "text-vhe-green" : "text-vhe-red"}`}>
                {INR.format(userPnl)}
              </div>
            </div>
            <div>
              <div className="text-[10px] font-mono text-text-faint uppercase tracking-wider">Return %</div>
              <div className={`text-xl font-mono font-semibold mt-1 ${sessionPnlPct >= 0 ? "text-vhe-green" : "text-vhe-red"}`}>
                {(sessionPnlPct * 100).toFixed(2)}%
              </div>
            </div>
          </div>
          <p className="text-text-faint font-mono text-xs">
            Based on shared session P&L. All users see the same live engine positions.
          </p>
        </div>

        {/* Capital input */}
        <div className="bg-bg-card rounded-xl border border-white/[0.08] p-5 space-y-4">
          <h2 className="text-sm font-bold font-sans text-text-muted uppercase tracking-wider">Adjust Virtual Capital</h2>
          <div className="flex gap-2">
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              min={25000}
              max={500000}
              step={5000}
              className="flex-1 bg-bg-elevated border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg"
            />
            <button
              onClick={saveCapital}
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-vhe-green/10 border border-vhe-green/30 text-vhe-green text-sm font-semibold font-sans hover:bg-vhe-green/20 disabled:opacity-50 transition-colors"
            >
              {saving ? "Saving…" : saved ? "Saved ✓" : "Save"}
            </button>
          </div>
          {err && <p className="text-vhe-red font-mono text-xs">{err}</p>}
          <p className="text-text-faint font-mono text-xs">Range: ₹25,000 – ₹5,00,000</p>
        </div>

        {/* Sign out */}
        <div className="flex justify-between items-center pt-2">
          <a href="/dashboard" className="text-sm text-vhe-blue font-sans hover:underline">← Back to Dashboard</a>
          <button onClick={logout} className="text-sm text-text-faint font-sans hover:text-vhe-red transition-colors">
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 10.2: Commit**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine
git add frontend/src/components/profile/
git commit -m "feat: add profile page with virtual portfolio scorecard"
```

---

## Task 11: Build + Wire to FastAPI

**Files:**
- Modify: `python/vhe/platform/server.py`

- [ ] **Step 11.1: Build the React app**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/frontend && npm run build 2>&1 | tail -20
```

Expected: no TypeScript errors, build succeeds, files written to `../python/vhe/platform/static/`.

If TypeScript errors appear, fix them before proceeding.

- [ ] **Step 11.2: Update server.py to serve React SPA**

The build outputs `index.html` to `python/vhe/platform/static/`. The server currently serves `static/index.html` at `/`. After the build, `dist/index.html` is there. Verify the build output path is correct:

```bash
ls /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/python/vhe/platform/static/ | head -10
```

Expected: `index.html`, `assets/` directory, and the old `app.js`, `styles.css` (which are now superseded by the React build).

In `python/vhe/platform/server.py`, find the `/` route and update it to serve the React SPA for all non-API paths (React Router handles client-side routing). Replace:

```python
@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (STATIC_DIR / "index.html").read_text()
```

With:

```python
@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (STATIC_DIR / "index.html").read_text()


@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/dashboard/{rest:path}", response_class=HTMLResponse)
@app.get("/profile", response_class=HTMLResponse)
async def spa_fallback() -> str:
    return (STATIC_DIR / "index.html").read_text()
```

- [ ] **Step 11.3: Verify server starts and serves React**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m uvicorn vhe.platform.server:app --port 8765 --reload 2>&1 &
sleep 3 && curl -s http://localhost:8765/ | grep -c "root"
```

Expected: `1` (the React `<div id="root">` is in the HTML)

```bash
curl -s http://localhost:8765/dashboard | grep -c "root"
```

Expected: `1` (SPA fallback serves React app)

- [ ] **Step 11.4: Kill dev server**

```bash
pkill -f "uvicorn vhe.platform.server" 2>/dev/null || true
```

- [ ] **Step 11.5: Run full Python test suite**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine && python -m pytest python/tests/ -q 2>&1 | tail -5
```

Expected: all pass.

- [ ] **Step 11.6: Add .env example entries**

Check if `.env.example` or `.env` exists and add the auth variables:

```bash
echo "
# Google OAuth (get from console.cloud.google.com)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# Generate with: python -c \"import secrets; print(secrets.token_hex(32))\"
JWT_SECRET=change-me-32-byte-random-hex-string
JWT_ALGORITHM=HS256
" >> /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/.env.example 2>/dev/null || \
echo "GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
JWT_SECRET=
JWT_ALGORITHM=HS256" > /home/katewa/Documents/dev/Projects/volatile_harvesting_engine/.env.example
```

- [ ] **Step 11.7: Final commit**

```bash
cd /home/katewa/Documents/dev/Projects/volatile_harvesting_engine
git add python/vhe/platform/server.py frontend/ .env.example
git commit -m "feat: wire React build to FastAPI, complete Phase 3 implementation"
```

---

## Post-Implementation: Connect Google OAuth credentials

After all code is committed, to test the full auth flow:

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → APIs & Services → Credentials → OAuth 2.0 Client ID
3. Application type: Web application
4. Authorized redirect URIs: `http://localhost:8765/auth/google/callback`
5. Copy Client ID and Client Secret into `.env`:
   ```
   GOOGLE_CLIENT_ID=<your-client-id>
   GOOGLE_CLIENT_SECRET=<your-client-secret>
   JWT_SECRET=<output of: python -c "import secrets; print(secrets.token_hex(32))">
   ```
6. Run: `python -m uvicorn vhe.platform.server:app --port 8765 --reload`
7. Visit `http://localhost:8765` → click "Sign in with Google"
