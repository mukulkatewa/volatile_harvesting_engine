from __future__ import annotations

import os
from pathlib import Path


def load_env_file(project_root: Path | None = None) -> Path | None:
    """Load `.env` from project root into process environment (does not override existing vars)."""
    root = project_root or _find_project_root()
    env_path = root / ".env"
    if not env_path.exists():
        return None

    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_env_manual(env_path)
        return env_path

    load_dotenv(env_path, override=False)
    return env_path


def _load_env_manual(env_path: Path) -> None:
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "configs" / "live_paper.yaml").exists():
            return parent
    return Path.cwd()
