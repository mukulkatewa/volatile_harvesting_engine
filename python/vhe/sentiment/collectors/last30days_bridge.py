from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from vhe.sentiment.collectors.base import BuzzCollector
from vhe.sentiment.models import BuzzItem
from vhe.sentiment.scoring import lexicon_score
from vhe.sentiment.symbols import search_queries


class Last30DaysCollector(BuzzCollector):
    """Bridge to mvanhorn/last30days-skill engine when installed locally.

    Install: https://github.com/mvanhorn/last30days-skill
    Set LAST30DAYS_ENGINE_PATH to the repo root, or clone to vendor/last30days-skill.
    """

    name = "last30days"

    def __init__(self, *, engine_path: Path | None = None, timeout_seconds: float = 120.0) -> None:
        self.engine_path = engine_path or _resolve_engine_path()
        self.timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return self.engine_path is not None and _engine_script(self.engine_path).exists()

    def collect(self, symbol: str) -> list[BuzzItem]:
        if not self.available:
            return []

        script = _engine_script(self.engine_path)
        topic = search_queries(symbol)[0]
        cmd = [
            _python_executable(),
            str(script),
            topic,
            "--emit=json",
            "--no-synthesis",
        ]
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")

        try:
            completed = subprocess.run(
                cmd,
                cwd=str(self.engine_path),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            return []

        if completed.returncode != 0:
            return _parse_stdout_fallback(completed.stdout, symbol)

        return _parse_engine_json(completed.stdout, symbol)


def _resolve_engine_path() -> Path | None:
    candidates: list[Path] = []
    env_path = os.environ.get("LAST30DAYS_ENGINE_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    home = Path.home()
    candidates.extend(
        [
            Path("vendor/last30days-skill"),
            home / "last30days-skill",
            home / ".claude" / "skills" / "last30days",
        ]
    )
    for candidate in candidates:
        resolved = candidate.resolve() if candidate.exists() else candidate
        if _engine_script(resolved).exists():
            return resolved
    return None


def _engine_script(root: Path) -> Path:
    return root / "skills" / "last30days" / "scripts" / "research.py"


def _python_executable() -> str:
    return shutil.which("python3") or shutil.which("python") or "python3"


def _parse_engine_json(stdout: str, symbol: str) -> list[BuzzItem]:
    text = stdout.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return _parse_stdout_fallback(stdout, symbol)

    rows = payload if isinstance(payload, list) else payload.get("items") or payload.get("results") or []
    items: list[BuzzItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or row.get("headline") or "").strip()
        if not title:
            continue
        source = str(row.get("source") or row.get("platform") or "last30days")
        url = str(row.get("url") or row.get("link") or "")
        engagement = float(row.get("score") or row.get("engagement") or row.get("ups") or 0)
        published = _parse_timestamp(row.get("published_at") or row.get("created_at"))
        body = str(row.get("text") or row.get("snippet") or "")
        items.append(
            BuzzItem(
                source=source,
                symbol=symbol,
                title=title[:240],
                url=url,
                engagement=engagement,
                published_at=published,
                text=body[:500],
                raw_score=lexicon_score(f"{title} {body}"),
            )
        )
    return items[:25]


def _parse_stdout_fallback(stdout: str, symbol: str) -> list[BuzzItem]:
    items: list[BuzzItem] = []
    for line in stdout.splitlines():
        match = re.match(r"^\s*-\s+\[(?P<source>[^\]]+)\]\s+(?P<title>.+?)\s+\((?P<score>[0-9.]+)\)", line)
        if not match:
            continue
        title = match.group("title").strip()
        items.append(
            BuzzItem(
                source=match.group("source").lower(),
                symbol=symbol,
                title=title[:240],
                url="",
                engagement=float(match.group("score")),
                published_at=datetime.now(tz=timezone.utc),
                raw_score=lexicon_score(title),
            )
        )
    return items


def _parse_timestamp(value: object) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(tz=timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return datetime.now(tz=timezone.utc)
