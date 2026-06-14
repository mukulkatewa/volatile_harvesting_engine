from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class PlatformEvent:
    timestamp: datetime
    category: str
    message: str
    severity: str = "info"

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


def event(category: str, message: str, severity: str = "info") -> PlatformEvent:
    return PlatformEvent(
        timestamp=datetime.now(tz=timezone.utc),
        category=category,
        message=message,
        severity=severity,
    )
