from __future__ import annotations

from decimal import Decimal

from app.config import Settings
from app.rules.amount_threshold_rule import AmountThresholdRule
from app.rules.guide_due_date_rule import GuideDueDateSemaphoreRule
from app.rules.pending_items_rule import PendingItemsRule


def test_pending_items_rule_detects_old_pending_record() -> None:
    settings = Settings(alert_days_threshold=5, mail_to=("ops@example.com",))
    rule = PendingItemsRule(settings)

    alerts = rule.evaluate(
        [
            {
                "record_reference": "P-100",
                "source": "sucursal-1",
                "status": "PENDING",
                "age_days": 8,
            },
            {
                "record_reference": "P-101",
                "source": "sucursal-1",
                "status": "PENDING",
                "age_days": 2,
            },
        ]
    )

    assert len(alerts) == 1
    assert alerts[0].alert_id == "pending_item:sucursal-1:p-100"
    assert alerts[0].metadata["threshold_days"] == 5


def test_amount_threshold_rule_detects_amount_over_threshold() -> None:
    settings = Settings(alert_amount_threshold=1000, mail_to=("ops@example.com",))
    rule = AmountThresholdRule(settings)

    alerts = rule.evaluate(
        [
            {"record_reference": "M-1", "source": "tesoreria", "amount": Decimal("1500.50")},
            {"record_reference": "M-2", "source": "tesoreria", "amount": Decimal("900.00")},
        ]
    )

    assert len(alerts) == 1
    assert alerts[0].alert_id == "amount_threshold:tesoreria:m-1"
    assert alerts[0].severity == "high"


def test_guide_due_date_rule_classifies_semaphore_sections() -> None:
    settings = Settings(mail_to=("ops@example.com",))
    rule = GuideDueDateSemaphoreRule(settings)

    alerts = rule.evaluate(
        [
            {
                "record_reference": "103",
                "codigo_sucursal": "SUC DHL-(MEX MZA)",
                "fecha_pactada_date": "2026-06-08",
                "days_until_due": 0,
            },
            {
                "record_reference": "104",
                "codigo_sucursal": "SUC DHL-(MEX MZA)",
                "fecha_pactada_date": "2026-06-10",
                "days_until_due": 2,
            },
            {
                "record_reference": "105",
                "codigo_sucursal": "SUC DHL-(MEX MZA)",
                "fecha_pactada_date": "2026-06-13",
                "days_until_due": 5,
            },
        ]
    )

    assert [alert.metadata["semaphore"] for alert in alerts] == [
        "critical",
        "warning",
        "upcoming",
    ]
    assert alerts[0].metadata["branch_title"] == "SUC DHL-(MEX MZA)"
