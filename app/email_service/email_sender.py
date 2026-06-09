from __future__ import annotations

import logging
import re
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.alerts.alert_model import Alert
from app.config import Settings
from app.utils.date_utils import local_now, utc_now


logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(self, settings: Settings, template_dir: Path | None = None):
        self.settings = settings
        self.template_dir = template_dir or Path(__file__).resolve().parent / "templates"
        self.template_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def send_alerts(self, alerts: list[Alert], summary: dict[str, Any] | None = None) -> bool:
        if not alerts:
            logger.info("No email sent because there are no alerts")
            return False

        batches = self._build_recipient_batches(alerts)
        if not batches:
            raise ValueError("No email recipients configured")

        for batch, batch_alerts in batches.items():
            recipients, branch_title = batch
            message = self._build_message(
                batch_alerts,
                list(recipients),
                summary or {},
                branch_title=branch_title,
            )
            if self.settings.email_dry_run:
                self._write_preview(message, recipients, branch_title)
                continue
            self._send_message(message)

        if self.settings.email_dry_run:
            logger.info("Email dry-run enabled. Generated %s preview batch(es)", len(batches))
            return False

        logger.info("Alert email sent in %s recipient batch(es)", len(batches))
        return True

    def _send_message(self, message: EmailMessage) -> None:
        try:
            context = ssl.create_default_context()
            if self.settings.smtp_port == 465:
                with smtplib.SMTP_SSL(
                    self.settings.smtp_server, self.settings.smtp_port, context=context
                ) as smtp:
                    self._login_if_needed(smtp)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(self.settings.smtp_server, self.settings.smtp_port) as smtp:
                    smtp.ehlo()
                    if self.settings.smtp_use_tls:
                        smtp.starttls(context=context)
                        smtp.ehlo()
                    self._login_if_needed(smtp)
                    smtp.send_message(message)

        except smtplib.SMTPException:
            logger.exception("SMTP error while sending alert email")
            raise

    def _build_message(
        self,
        alerts: list[Alert],
        recipients: list[str],
        summary: dict[str, Any],
        branch_title: str | None = None,
    ) -> EmailMessage:
        generated_at = local_now(self.settings.app_timezone)
        mail_title = branch_title or self._resolve_mail_title(alerts)
        is_consolidated_guide = self._is_consolidated_guide_email(alerts)
        alert_count = 1 if is_consolidated_guide else len(alerts)
        detail_count = len(alerts)
        template = self.template_env.get_template("alert_email.html")
        html_body = template.render(
            mail_title=mail_title,
            alerts=alerts,
            sections=self._build_sections(alerts),
            summary=summary,
            total_alerts=alert_count,
            total_details=detail_count,
            is_consolidated_guide=is_consolidated_guide,
            generated_at=generated_at,
        )

        headline = f"{mail_title}: {alert_count}"
        if is_consolidated_guide:
            headline = f"{mail_title}: {alert_count} alerta consolidada, {detail_count} detalles"

        plain_body = "\n".join(
            [
                headline,
                f"Fecha de ejecucion: {generated_at:%Y-%m-%d %H:%M:%S %Z}",
                "",
                *[
                    f"- [{alert.severity}] {alert.title} ({alert.source} / {alert.record_reference})"
                    for alert in alerts
                ],
                "",
                "Este correo fue generado automaticamente por el sistema de alertas.",
            ]
        )

        message = EmailMessage()
        message["Subject"] = f"{mail_title} - Alertas ({alert_count})"
        message["From"] = self.settings.mail_from
        message["To"] = ", ".join(recipients)
        message.set_content(plain_body)
        message.add_alternative(html_body, subtype="html")
        return message

    def _login_if_needed(self, smtp: smtplib.SMTP) -> None:
        if self.settings.smtp_user:
            smtp.login(self.settings.smtp_user, self.settings.smtp_password)

    def _build_recipient_batches(self, alerts: list[Alert]) -> dict[tuple[tuple[str, ...], str], list[Alert]]:
        batches: dict[tuple[tuple[str, ...], str], list[Alert]] = {}
        for alert in alerts:
            recipients = tuple(dict.fromkeys(alert.recipients or self.settings.mail_to))
            if not recipients:
                continue
            branch_title = str(alert.metadata.get("branch_title") or self._resolve_mail_title([alert]))
            batches.setdefault((recipients, branch_title), []).append(alert)
        return batches

    @staticmethod
    def _resolve_mail_title(alerts: list[Alert]) -> str:
        titles = {
            str(alert.metadata.get("branch_title"))
            for alert in alerts
            if alert.metadata.get("branch_title")
        }
        if len(titles) == 1:
            return next(iter(titles))
        if len(titles) > 1:
            return "Alertas por sucursal"
        return "Alertas inteligentes detectadas"

    @staticmethod
    def _is_consolidated_guide_email(alerts: list[Alert]) -> bool:
        return bool(alerts) and all(
            alert.alert_type == "GUIDE_DUE_DATE" and alert.metadata.get("semaphore")
            for alert in alerts
        )

    def _write_preview(
        self,
        message: EmailMessage,
        recipients: tuple[str, ...],
        branch_title: str | None = None,
    ) -> None:
        self.settings.email_preview_dir.mkdir(parents=True, exist_ok=True)
        timestamp = utc_now().strftime("%Y%m%d_%H%M%S_%f")
        safe_recipients = re.sub(r"[^a-zA-Z0-9_.-]+", "_", "_".join(recipients))[:120]
        safe_branch = re.sub(r"[^a-zA-Z0-9_.-]+", "_", branch_title or "alertas")[:80]
        base_path = self.settings.email_preview_dir / (
            f"alertas_{timestamp}_{safe_branch}_{safe_recipients}"
        )
        eml_path = base_path.with_suffix(".eml")
        html_path = base_path.with_suffix(".html")

        eml_path.write_text(message.as_string(), encoding="utf-8")
        html_body = self._extract_html(message)
        if html_body:
            html_path.write_text(html_body, encoding="utf-8")

        logger.info("Email preview generated: %s", html_path if html_body else eml_path)

    @staticmethod
    def _extract_html(message: EmailMessage) -> str:
        for part in message.walk():
            if part.get_content_type() == "text/html":
                return part.get_content()
        return ""

    @staticmethod
    def _build_sections(alerts: list[Alert]) -> list[dict[str, Any]]:
        section_definitions = [
            {
                "key": "critical",
                "title": "CRITICO (Hoy o vencidas)",
                "color": "#b42318",
                "action": "Gestion inmediata y rendicion prioritaria.",
            },
            {
                "key": "warning",
                "title": "PROXIMAS 48 HORAS",
                "color": "#b54708",
                "action": "Seguimiento preventivo para asegurar el cumplimiento.",
            },
            {
                "key": "upcoming",
                "title": "PROXIMA SEMANA",
                "color": "#027a48",
                "action": "Visibilidad para la organizacion operativa semanal.",
            },
        ]
        sections: list[dict[str, Any]] = []
        remaining = list(alerts)

        for definition in section_definitions:
            grouped = [
                alert
                for alert in alerts
                if alert.metadata.get("semaphore") == definition["key"]
            ]
            if grouped:
                sections.append({**definition, "alerts": grouped})
                remaining = [alert for alert in remaining if alert not in grouped]

        if remaining:
            sections.append(
                {
                    "key": "other",
                    "title": "OTRAS ALERTAS",
                    "color": "#344054",
                    "action": "Revision operativa.",
                    "alerts": remaining,
                }
            )

        return sections
