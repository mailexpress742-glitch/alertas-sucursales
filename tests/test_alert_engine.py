from __future__ import annotations

from pathlib import Path

from app.alerts.alert_engine import AlertEngine
from app.alerts.alert_history import AlertHistory
from app.config import Settings


class FakeDatabase:
    def __init__(self) -> None:
        self.calls = 0

    def execute_select(self, sql: str, params: dict | None = None) -> list[dict]:
        self.calls += 1
        if "pending_items" in sql:
            return [
                {
                    "record_reference": "P-100",
                    "source": "sucursal-1",
                    "status": "PENDING",
                    "age_days": 9,
                }
            ]
        if "financial_movements" in sql:
            return [
                {
                    "record_reference": "M-900",
                    "source": "sucursal-2",
                    "amount": "2500.00",
                }
            ]
        if "process_status" in sql:
            return []
        return []


class FakeEmailSender:
    def __init__(self) -> None:
        self.sent_alerts = []

    def send_alerts(self, alerts, summary=None) -> bool:
        self.sent_alerts.append(list(alerts))
        return True


def _settings() -> Settings:
    return Settings(
        alert_days_threshold=5,
        alert_amount_threshold=1000,
        mail_to=("ops@example.com",),
        enabled_rules=("pending_items", "amount_threshold"),
    )


def test_alert_engine_runs_rules_with_simulated_data(tmp_path: Path) -> None:
    history = AlertHistory(tmp_path / "history.json")
    sender = FakeEmailSender()
    engine = AlertEngine(_settings(), FakeDatabase(), sender, history)

    summary = engine.run()

    assert summary.total_alerts == 2
    assert summary.new_alerts == 2
    assert summary.email_sent is True
    assert len(sender.sent_alerts[0]) == 2


def test_alert_engine_avoids_duplicates_by_alert_id(tmp_path: Path) -> None:
    history_path = tmp_path / "history.json"

    first_sender = FakeEmailSender()
    first_engine = AlertEngine(_settings(), FakeDatabase(), first_sender, AlertHistory(history_path))
    first_summary = first_engine.run()

    second_sender = FakeEmailSender()
    second_engine = AlertEngine(_settings(), FakeDatabase(), second_sender, AlertHistory(history_path))
    second_summary = second_engine.run()

    assert first_summary.new_alerts == 2
    assert second_summary.total_alerts == 2
    assert second_summary.new_alerts == 0
    assert second_summary.duplicates_skipped == 2
    assert second_sender.sent_alerts == []
