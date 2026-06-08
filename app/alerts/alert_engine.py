from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.alerts.alert_history import AlertHistory
from app.alerts.alert_model import Alert
from app.config import Settings
from app.database import queries
from app.email_service.email_sender import EmailSender
from app.rules.amount_threshold_rule import AmountThresholdRule
from app.rules.base_rule import BaseRule
from app.rules.guide_due_date_rule import GuideDueDateSemaphoreRule
from app.rules.pending_items_rule import PendingItemsRule
from app.utils.date_utils import utc_now


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionSummary:
    started_at: datetime
    finished_at: datetime
    rows_by_dataset: dict[str, int] = field(default_factory=dict)
    total_alerts: int = 0
    new_alerts: int = 0
    duplicates_skipped: int = 0
    email_sent: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "rows_by_dataset": self.rows_by_dataset,
            "total_alerts": self.total_alerts,
            "new_alerts": self.new_alerts,
            "duplicates_skipped": self.duplicates_skipped,
            "email_sent": self.email_sent,
            "errors": self.errors,
        }


class AlertEngine:
    def __init__(
        self,
        settings: Settings,
        db_connection,
        email_sender: EmailSender | None = None,
        history: AlertHistory | None = None,
        rules: list[BaseRule] | None = None,
    ):
        self.settings = settings
        self.db_connection = db_connection
        self.email_sender = email_sender
        self.history = history
        self.rules = rules or self._build_enabled_rules(settings)

    def run(self) -> ExecutionSummary:
        started_at = utc_now()
        errors: list[str] = []
        email_sent = False

        data_sources = self._collect_data()
        rows_by_dataset = {name: len(rows) for name, rows in data_sources.items()}
        alerts = self._evaluate_rules(data_sources)
        unique_alerts = self._deduplicate_batch(alerts)

        if len(alerts) != len(unique_alerts):
            logger.info("Removed %s duplicated alert(s) from the current batch", len(alerts) - len(unique_alerts))

        if self.history:
            self.history.record_detected(unique_alerts)
            alerts_to_send = self.history.filter_unsent(unique_alerts)
        else:
            alerts_to_send = unique_alerts

        duplicates_skipped = len(unique_alerts) - len(alerts_to_send)
        summary_context = {
            "started_at": started_at.isoformat(),
            "rows_by_dataset": rows_by_dataset,
            "total_alerts": len(unique_alerts),
            "new_alerts": len(alerts_to_send),
            "duplicates_skipped": duplicates_skipped,
        }

        if alerts_to_send:
            if self.email_sender is None:
                message = "There are alerts to send, but no email sender was configured"
                logger.error(message)
                errors.append(message)
            else:
                email_sent = self.email_sender.send_alerts(alerts_to_send, summary_context)
                if email_sent and self.history:
                    self.history.mark_sent(alerts_to_send)
        else:
            logger.info("No new alerts to send")

        finished_at = utc_now()
        summary = ExecutionSummary(
            started_at=started_at,
            finished_at=finished_at,
            rows_by_dataset=rows_by_dataset,
            total_alerts=len(unique_alerts),
            new_alerts=len(alerts_to_send),
            duplicates_skipped=duplicates_skipped,
            email_sent=email_sent,
            errors=errors,
        )

        logger.info(
            "Alert run finished: total=%s new=%s duplicates_skipped=%s email_sent=%s",
            summary.total_alerts,
            summary.new_alerts,
            summary.duplicates_skipped,
            summary.email_sent,
        )
        return summary

    def _collect_data(self) -> dict[str, list[dict[str, Any]]]:
        logger.info("Collecting data from read-only queries")
        needed_datasets = {rule.data_key for rule in self.rules}
        data_sources: dict[str, list[dict[str, Any]]] = {}

        if "pending_items" in needed_datasets:
            data_sources["pending_items"] = queries.get_pending_items(self.db_connection)
        if "financial_movements" in needed_datasets:
            data_sources["financial_movements"] = queries.get_financial_movements(self.db_connection)
        if "process_status" in needed_datasets:
            data_sources["process_status"] = queries.get_process_status(self.db_connection)
        if "guides_due" in needed_datasets:
            data_sources["guides_due"] = queries.get_guides_due_for_week(
                self.db_connection,
                due_date_column=self.settings.guide_due_date_column,
                lookahead_days=self.settings.guide_lookahead_days,
                max_rows=self.settings.guide_max_rows,
                only_active=self.settings.guide_only_active,
                only_unfinished=self.settings.guide_only_unfinished,
            )

        logger.info(
            "Data collected: %s",
            ", ".join(f"{key}={len(value)}" for key, value in data_sources.items()),
        )
        return data_sources

    def _evaluate_rules(self, data_sources: dict[str, list[dict[str, Any]]]) -> list[Alert]:
        generated: list[Alert] = []
        for rule in self.rules:
            dataset = data_sources.get(rule.data_key, [])
            logger.info("Evaluating rule=%s dataset=%s rows=%s", rule.name, rule.data_key, len(dataset))
            rule_alerts = rule.evaluate(dataset)
            logger.info("Rule=%s produced %s alert(s)", rule.name, len(rule_alerts))
            generated.extend(rule_alerts)
        return generated

    @staticmethod
    def _deduplicate_batch(alerts: list[Alert]) -> list[Alert]:
        unique: dict[str, Alert] = {}
        for alert in alerts:
            unique.setdefault(alert.alert_id, alert)
        return list(unique.values())

    @staticmethod
    def _build_enabled_rules(settings: Settings) -> list[BaseRule]:
        available: dict[str, type[BaseRule]] = {
            "guide_due_date": GuideDueDateSemaphoreRule,
            "pending_items": PendingItemsRule,
            "amount_threshold": AmountThresholdRule,
        }
        enabled_rules: list[BaseRule] = []
        for rule_name in settings.enabled_rules:
            rule_cls = available.get(rule_name)
            if rule_cls is None:
                logger.warning("Ignoring unknown rule configured in ENABLED_RULES: %s", rule_name)
                continue
            enabled_rules.append(rule_cls(settings))

        if not enabled_rules:
            raise ValueError("No valid alert rules enabled")

        return enabled_rules
