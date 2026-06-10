from __future__ import annotations

import os
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.config import Settings
from app.email_service.email_sender import EmailSender
from app.rules.guide_due_date_rule import GuideDueDateSemaphoreRule
from app.utils.date_utils import local_now


def _bool_from_env(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def main() -> None:
    email_dry_run = _bool_from_env(
        os.environ.get("SAMPLE_PREVIEW_EMAIL_DRY_RUN"),
        True,
    )
    settings = replace(Settings.from_env(), email_dry_run=email_dry_run)
    preview_dir = settings.email_preview_dir
    before = set(preview_dir.glob("*")) if preview_dir.exists() else set()

    today = local_now(settings.app_timezone).date()
    branch_samples = [
        {
            "label": "SR",
            "sucursal_id": 44,
            "codigo_sucursal": "MEXSR",
            "cliente": "MAILEXPRESS SAN RAFAEL",
            "base_id": 103832782,
        },
        {
            "label": "CBA",
            "sucursal_id": 42,
            "codigo_sucursal": "MEXRIOIV",
            "cliente": "MAILEXPRESS RIO IV",
            "base_id": 103837782,
        },
        {
            "label": "GA",
            "sucursal_id": 128,
            "codigo_sucursal": "MEXGALVEAR",
            "cliente": "MAILEXPRESS GENERAL ALVEAR",
            "base_id": 103842782,
        },
    ]
    status_samples = [
        {
            "label": "CRITICA",
            "days_until_due": 0,
            "estado": "DESPACHADO A SUCURSAL",
            "count": 35,
            "offset": 0,
        },
        {
            "label": "ADVERTENCIA",
            "days_until_due": 2,
            "estado": "RC-EN RUTA PARA SU ENTREGA",
            "count": 33,
            "offset": 1000,
        },
        {
            "label": "PROXIMA",
            "days_until_due": 5,
            "estado": "DESP-Despachado",
            "count": 31,
            "offset": 2000,
        },
    ]

    rows = []
    for branch in branch_samples:
        for status in status_samples:
            days_until_due = status["days_until_due"]
            for index in range(1, status["count"] + 1):
                guide_id = branch["base_id"] + status["offset"] + index - 1
                rows.append(
                    {
                        "record_reference": str(guide_id),
                        "sucursal_id": branch["sucursal_id"],
                        "codigo_sucursal": branch["codigo_sucursal"],
                        "cliente": branch["cliente"],
                        "fecha_pactada_date": (today + timedelta(days=days_until_due)).isoformat(),
                        "days_until_due": days_until_due,
                        "estado": status["estado"],
                    }
                )

    alerts = GuideDueDateSemaphoreRule(settings).evaluate(rows)
    EmailSender(settings).send_alerts(
        alerts,
        {
            "total_alerts": len(alerts),
            "new_alerts": len(alerts),
            "duplicates_skipped": 0,
            "mode": "sample_preview",
        },
    )

    after = set(preview_dir.glob("*")) if preview_dir.exists() else set()
    created = sorted(after - before)

    print(f"Alertas de muestra generadas: {len(alerts)}")
    if not settings.email_dry_run:
        print("Correo de muestra enviado por SMTP.")
    if created:
        print("Archivos generados:")
        for path in created:
            print(Path(path).resolve())


if __name__ == "__main__":
    main()
