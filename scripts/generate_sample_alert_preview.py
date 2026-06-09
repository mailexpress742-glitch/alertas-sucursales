from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.config import Settings
from app.email_service.email_sender import EmailSender
from app.rules.guide_due_date_rule import GuideDueDateSemaphoreRule


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

    rows = [
        {
            "record_reference": "GUIA-CRITICA-001",
            "sucursal_id": 44,
            "codigo_sucursal": "MEXSR",
            "fecha_pactada_date": "2026-06-08",
            "days_until_due": 0,
        },
        {
            "record_reference": "GUIA-ADVERTENCIA-001",
            "sucursal_id": 42,
            "codigo_sucursal": "MEXRIOIV",
            "fecha_pactada_date": "2026-06-10",
            "days_until_due": 2,
        },
        {
            "record_reference": "GUIA-PROXIMA-001",
            "sucursal_id": 128,
            "codigo_sucursal": "MEXGALVEAR",
            "fecha_pactada_date": "2026-06-13",
            "days_until_due": 5,
        },
    ]

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
