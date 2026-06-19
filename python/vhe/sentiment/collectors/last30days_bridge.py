from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from vhe.sentiment.collectors.base import BuzzCollector
from vhe.sentiment.models import BuzzItem
from vhe.sentiment.scoring import lexicon_score
from vhe.sentiment.symbols import search_queries


class Last30DaysCollector(BuzzCollector):
    """Bridge to mvanhorn/last30days-skill (last30days.py CLI).

    Clone: https://github.com/mvanhorn/last30days-skill → vendor/last30days-skill
    Or set LAST30DAYS_ENGINE_PATH to the repo root.
    """

    name = "last30days"

    def __init__(
        self,
        *,
        engine_path: Path | None = None,
        timeout_seconds: float = 90.0,
        lookback_days: int = 30,
        search_sources: str = "reddit,hackernews,web",
        quick: bool = True,
    ) -> None:
        self.engine_path = engine_path or _resolve_engine_path()
        self.timeout_seconds = timeout_seconds
        self.lookback_days = lookback_days
        self.search_sources = search_sources
        self.quick = quick

    @property
    def available(self) -> bool:
        return self.engine_path is not None and _engine_script(self.engine_path).exists()

    def collect(self, symbol: str) -> list[BuzzItem]:
        if not self.available:
            return []

        script = _engine_script(self.engine_path)
        topic = search_queries(symbol)[0]
        cmd = [
            sys.executable,
            str(script),
            topic,
            "--emit=json",
            f"--days={self.lookback_days}",
            f"--search={self.search_sources}",
        ]
        if self.quick:
            cmd.append("--quick")

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
        except (subprocess.TimeoutExpired, OSError) as exc:
            return []

        stdout = (completed.stdout or "").strip()
        if not stdout:
            return _parse_stdout_fallback(completed.stderr or "", symbol)

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return _parse_stdout_fallback(stdout, symbol)

        return _parse_last30days_report(payload, symbol)


def _resolve_engine_path() -> Path | None:
    candidates: list[Path] = []
    env_path = os.environ.get("LAST30DAYS_ENGINE_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    root = _project_root()
    candidates.extend(
        [
            root / "vendor" / "last30days-skill",
            Path("vendor/last30days-skill"),
            Path.home() / "last30days-skill",
        ]
    )
    for candidate in candidates:
        if candidate.exists() and _engine_script(candidate).exists():
            return candidate.resolve()
    return None


def _project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "configs" / "live_paper.yaml").exists():
            return parent
    return Path.cwd()


def _engine_script(root: Path) -> Path:
    return root / "skills" / "last30days" / "scripts" / "last30days.py"


def _parse_last30days_report(payload: dict, symbol: str) -> list[BuzzItem]:
    items: list[BuzzItem] = []
    seen: set[str] = set()

    for candidate in payload.get("ranked_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        title = str(candidate.get("title") or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        source = str(candidate.get("source") or "last30days")
        url = str(candidate.get("url") or "")
        engagement = _engagement_value(candidate.get("engagement"))
        if engagement <= 0:
            engagement = float(candidate.get("final_score") or candidate.get("rerank_score") or 1.0)
        published = _parse_timestamp(_first_source_timestamp(candidate))
        snippet = str(candidate.get("snippet") or "")
        items.append(
            BuzzItem(
                source=source,
                symbol=symbol,
                title=title[:240],
                url=url,
                engagement=engagement,
                published_at=published,
                text=snippet[:500],
                raw_score=lexicon_score(f"{title} {snippet}"),
            )
        )

    for source, rows in (payload.get("items_by_source") or {}).items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            key = f"{source}:{title.lower()}"
            if key in seen:
                continue
            seen.add(key)
            body = str(row.get("body") or row.get("snippet") or "")
            engagement = _engagement_value(row.get("engagement"))
            if engagement <= 0:
                engagement = float(row.get("engagement_score") or row.get("local_rank_score") or 1.0)
            items.append(
                BuzzItem(
                    source=str(source),
                    symbol=symbol,
                    title=title[:240],
                    url=str(row.get("url") or ""),
                    engagement=engagement,
                    published_at=_parse_timestamp(row.get("published_at")),
                    text=body[:500],
                    raw_score=lexicon_score(f"{title} {body}"),
                )
            )

    items.sort(key=lambda item: item.engagement, reverse=True)
    return items[:25]


def _engagement_value(raw: object) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, dict):
        total = 0.0
        for value in raw.values():
            try:
                total += float(value)
            except (TypeError, ValueError):
                continue
        return total
    return 0.0


def _first_source_timestamp(candidate: dict) -> object:
    for item in candidate.get("source_items") or []:
        if isinstance(item, dict) and item.get("published_at"):
            return item.get("published_at")
    return None


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
