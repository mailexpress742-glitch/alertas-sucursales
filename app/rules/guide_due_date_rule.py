from __future__ import annotations

from typing import Any

from app.alerts.branch_resolver import BranchNameResolver
from app.alerts.alert_model import Alert
from app.alerts.recipient_resolver import BranchRecipientResolver
from app.config import Settings
from app.rules.base_rule import BaseRule
from app.utils.date_utils import parse_datetime


class GuideDueDateSemaphoreRule(BaseRule):
    name = "guide_due_date"
    description = "Semaforiza guias/retiros segun fecha pactada."
    severity = "medium"
    data_key = "guides_due"
    alert_type = "GUIDE_DUE_DATE"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.recipient_resolver = BranchRecipientResolver(settings)
        self.branch_name_resolver = BranchNameResolver(settings)

    def evaluate(self, data: list[dict[str, Any]]) -> list[Alert]:
        alerts: list[Alert] = []

        for row in data:
            days_until_due = self._days_until_due(row)
            if days_until_due is None:
                continue

            semaphore = self._semaphore(days_until_due)
            if semaphore is None:
                continue

            reference = str(row.get("record_reference") or row.get("retiro_id") or "unknown")
            branch_code = str(
                row.get("codigo_sucursal")
                or row.get("sucursal_descripcion")
                or row.get("sucursal_id")
                or "sucursal_desconocida"
            )
            branch_title = self.branch_name_resolver.resolve(row)
            due_date = row.get("fecha_pactada_date") or row.get("fecha_pactada")
            alert_id = Alert.build_alert_id(self.alert_type, branch_code, reference)

            alerts.append(
                Alert(
                    alert_id=alert_id,
                    alert_type=self.alert_type,
                    severity=semaphore["severity"],
                    title=f"Guia {reference} - {semaphore['label']}",
                    description=(
                        f"La guia/retiro {reference} de {branch_code} tiene fecha pactada "
                        f"{due_date}. Accion recomendada: {semaphore['action']}."
                    ),
                    source=branch_code,
                    record_reference=reference,
                    recipients=self.recipient_resolver.resolve(row),
                    metadata={
                        **row,
                        "branch_title": branch_title,
                        "branch_code": branch_code,
                        "days_until_due": days_until_due,
                        "semaphore": semaphore["key"],
                        "semaphore_label": semaphore["label"],
                        "recommended_action": semaphore["action"],
                    },
                )
            )

        return alerts

    @staticmethod
    def _days_until_due(row: dict[str, Any]) -> int | None:
        explicit_days = row.get("days_until_due")
        if explicit_days is not None:
            try:
                return int(explicit_days)
            except (TypeError, ValueError):
                return None

        due_date = parse_datetime(row.get("fecha_pactada_date") or row.get("fecha_pactada"))
        if due_date is None:
            return None

        from app.utils.date_utils import local_now

        today = local_now().date()
        return (due_date.date() - today).days

    @staticmethod
    def _semaphore(days_until_due: int) -> dict[str, str] | None:
        if days_until_due <= 0:
            return {
                "key": "critical",
                "label": "CRITICO",
                "severity": "critical",
                "action": "gestion inmediata y rendicion prioritaria",
            }
        if 1 <= days_until_due <= 2:
            return {
                "key": "warning",
                "label": "ADVERTENCIA",
                "severity": "warning",
                "action": "seguimiento preventivo para asegurar el cumplimiento",
            }
        if 3 <= days_until_due <= 7:
            return {
                "key": "upcoming",
                "label": "PROXIMOS",
                "severity": "info",
                "action": "planificacion operativa semanal",
            }
        return None
