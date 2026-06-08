from __future__ import annotations

from datetime import timezone
from typing import Any

from app.alerts.alert_model import Alert
from app.config import Settings
from app.rules.base_rule import BaseRule
from app.utils.date_utils import parse_datetime, utc_now


class PendingItemsRule(BaseRule):
    name = "pending_items"
    description = "Detecta registros pendientes con mas dias que el umbral configurado."
    severity = "medium"
    data_key = "pending_items"
    alert_type = "PENDING_ITEM"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.threshold_days = settings.alert_days_threshold

    def evaluate(self, data: list[dict[str, Any]]) -> list[Alert]:
        alerts: list[Alert] = []
        for row in data:
            age_days = self._age_days(row)
            if age_days is None or age_days <= self.threshold_days:
                continue

            source = str(row.get("source") or row.get("branch") or "database")
            reference = str(
                row.get("record_reference")
                or row.get("id")
                or row.get("document_number")
                or "unknown"
            )
            alert_id = Alert.build_alert_id(self.alert_type, source, reference)

            alerts.append(
                Alert(
                    alert_id=alert_id,
                    alert_type=self.alert_type,
                    severity=self.severity,
                    title=f"Registro pendiente hace {age_days} dias",
                    description=(
                        f"El registro {reference} de {source} supera el umbral de "
                        f"{self.threshold_days} dias pendientes."
                    ),
                    source=source,
                    record_reference=reference,
                    recipients=self.settings.mail_to,
                    metadata={**row, "age_days": age_days, "threshold_days": self.threshold_days},
                )
            )

        return alerts

    @staticmethod
    def _age_days(row: dict[str, Any]) -> int | None:
        explicit_age = row.get("age_days") or row.get("days_pending") or row.get("dias_pendiente")
        if explicit_age is not None:
            try:
                return int(explicit_age)
            except (TypeError, ValueError):
                return None

        for key in ("created_at", "created_date", "pending_since", "fecha_creacion"):
            detected_date = parse_datetime(row.get(key))
            if detected_date is None:
                continue
            if detected_date.tzinfo is None:
                detected_date = detected_date.replace(tzinfo=timezone.utc)
            now = utc_now()
            return (now.date() - detected_date.astimezone(timezone.utc).date()).days

        return None

