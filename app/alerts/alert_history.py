from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.alerts.alert_model import Alert
from app.utils.date_utils import utc_now


logger = logging.getLogger(__name__)


class AlertHistory:
    def __init__(self, history_file: Path):
        self.history_file = Path(history_file)
        self._records = self._load()

    def has_been_sent(self, alert_id: str) -> bool:
        record = self._records.get(alert_id)
        return bool(record and record.get("mail_sent"))

    def filter_unsent(self, alerts: list[Alert]) -> list[Alert]:
        return [alert for alert in alerts if not self.has_been_sent(alert.alert_id)]

    def record_detected(self, alerts: list[Alert]) -> None:
        if not alerts:
            return

        now = utc_now().isoformat()
        for alert in alerts:
            record = self._records.get(alert.alert_id)
            if record is None:
                self._records[alert.alert_id] = {
                    "alert_id": alert.alert_id,
                    "first_detected_at": alert.detected_at.isoformat(),
                    "last_detected_at": alert.detected_at.isoformat(),
                    "alert_type": alert.alert_type,
                    "record_reference": alert.record_reference,
                    "severity": alert.severity,
                    "mail_sent": False,
                    "sent_at": None,
                }
            else:
                record["last_detected_at"] = now
        self._save()

    def mark_sent(self, alerts: list[Alert]) -> None:
        if not alerts:
            return

        sent_at = utc_now().isoformat()
        for alert in alerts:
            record = self._records.setdefault(
                alert.alert_id,
                {
                    "alert_id": alert.alert_id,
                    "first_detected_at": alert.detected_at.isoformat(),
                    "alert_type": alert.alert_type,
                    "record_reference": alert.record_reference,
                    "severity": alert.severity,
                },
            )
            record["last_detected_at"] = alert.detected_at.isoformat()
            record["mail_sent"] = True
            record["sent_at"] = sent_at
        self._save()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.history_file.exists():
            return {}

        try:
            with self.history_file.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            logger.exception("Could not read alert history. Starting with empty history.")
            return {}

        if isinstance(payload, dict) and isinstance(payload.get("alerts"), list):
            return {item["alert_id"]: item for item in payload["alerts"] if "alert_id" in item}

        if isinstance(payload, dict):
            return {
                key: value
                for key, value in payload.items()
                if isinstance(value, dict) and value.get("alert_id")
            }

        if isinstance(payload, list):
            return {item["alert_id"]: item for item in payload if "alert_id" in item}

        return {}

    def _save(self) -> None:
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": utc_now().isoformat(),
            "alerts": sorted(self._records.values(), key=lambda item: item["alert_id"]),
        }
        with self.history_file.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

