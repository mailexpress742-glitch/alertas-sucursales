from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.alerts.alert_model import Alert
from app.config import Settings
from app.rules.base_rule import BaseRule


class AmountThresholdRule(BaseRule):
    name = "amount_threshold"
    description = "Detecta importes mayores al umbral configurado."
    severity = "high"
    data_key = "financial_movements"
    alert_type = "AMOUNT_THRESHOLD"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.threshold_amount = Decimal(str(settings.alert_amount_threshold))

    def evaluate(self, data: list[dict[str, Any]]) -> list[Alert]:
        alerts: list[Alert] = []
        for row in data:
            amount = self._to_decimal(row.get("amount") or row.get("importe") or row.get("total"))
            if amount is None or amount <= self.threshold_amount:
                continue

            source = str(row.get("source") or row.get("branch") or "database")
            reference = str(
                row.get("record_reference")
                or row.get("id")
                or row.get("movement_id")
                or "unknown"
            )
            alert_id = Alert.build_alert_id(self.alert_type, source, reference)

            alerts.append(
                Alert(
                    alert_id=alert_id,
                    alert_type=self.alert_type,
                    severity=self.severity,
                    title=f"Importe fuera de rango: {amount}",
                    description=(
                        f"El movimiento {reference} de {source} tiene importe {amount}, "
                        f"mayor al umbral {self.threshold_amount}."
                    ),
                    source=source,
                    record_reference=reference,
                    recipients=self.settings.mail_to,
                    metadata={
                        **row,
                        "amount": str(amount),
                        "threshold_amount": str(self.threshold_amount),
                    },
                )
            )

        return alerts

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))

        text = str(value).strip().replace(" ", "")
        if not text:
            return None

        if "," in text and "." in text and text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        elif "," in text and "." not in text:
            text = text.replace(",", ".")

        try:
            return Decimal(text)
        except InvalidOperation:
            return None

