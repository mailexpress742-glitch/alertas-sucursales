from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from app.utils.date_utils import parse_datetime, utc_now


def _normalize_id_component(value: object) -> str:
    text = str(value or "unknown").strip().lower()
    text = re.sub(r"[^a-z0-9_.-]+", "_", text)
    return text.strip("_") or "unknown"


@dataclass(frozen=True)
class Alert:
    alert_id: str
    alert_type: str
    severity: str
    title: str
    description: str
    source: str
    record_reference: str
    detected_at: datetime = field(default_factory=utc_now)
    recipients: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def build_alert_id(alert_type: str, source: str, record_reference: str) -> str:
        return ":".join(
            [
                _normalize_id_component(alert_type),
                _normalize_id_component(source),
                _normalize_id_component(record_reference),
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["detected_at"] = self.detected_at.isoformat()
        payload["recipients"] = list(self.recipients)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Alert":
        detected_at = parse_datetime(payload.get("detected_at")) or utc_now()
        return cls(
            alert_id=payload["alert_id"],
            alert_type=payload["alert_type"],
            severity=payload["severity"],
            title=payload["title"],
            description=payload["description"],
            source=payload["source"],
            record_reference=payload["record_reference"],
            detected_at=detected_at,
            recipients=tuple(payload.get("recipients") or ()),
            metadata=dict(payload.get("metadata") or {}),
        )

