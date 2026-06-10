from __future__ import annotations

from email import message_from_string
from pathlib import Path

from app.alerts.alert_model import Alert
from app.alerts.branch_resolver import BranchNameResolver
from app.alerts.recipient_resolver import BranchRecipientResolver
from app.config import Settings
from app.email_service.email_sender import EmailSender


def test_branch_recipient_resolver_prefers_mapping_file(tmp_path: Path) -> None:
    mapping_file = tmp_path / "recipients.json"
    mapping_file.write_text(
        '{"336": ["mendoza@example.com"], "SUC DHL-(MEX MZA)": ["otro@example.com"]}',
        encoding="utf-8",
    )
    settings = Settings(
        mail_to=("fallback@example.com",),
        sucursal_recipients_file=mapping_file,
    )

    resolver = BranchRecipientResolver(settings)

    recipients = resolver.resolve(
        {
            "sucursal_id": 336,
            "codigo_sucursal": "SUC DHL-(MEX MZA)",
            "sucursal_mail": "db@example.com",
        }
    )

    assert recipients == ("otro@example.com",)


def test_branch_recipient_resolver_uses_database_mail_then_fallback(tmp_path: Path) -> None:
    settings = Settings(
        mail_to=("fallback@example.com",),
        sucursal_recipients_file=tmp_path / "missing.json",
    )
    resolver = BranchRecipientResolver(settings)

    assert resolver.resolve({"sucursal_mail": "a@example.com;b@example.com"}) == (
        "a@example.com",
        "b@example.com",
    )
    assert resolver.resolve({"codigo_sucursal": "sin-mail"}) == ("fallback@example.com",)


def test_email_sender_batches_alerts_by_recipients() -> None:
    settings = Settings(mail_to=("fallback@example.com",))
    sender = EmailSender(settings)
    alerts = [
        Alert(
            alert_id="a1",
            alert_type="GUIDE_DUE_DATE",
            severity="critical",
            title="A1",
            description="A1",
            source="Sucursal 1",
            record_reference="1",
            recipients=("s1@example.com",),
            metadata={"branch_title": "Sucursal 1"},
        ),
        Alert(
            alert_id="a2",
            alert_type="GUIDE_DUE_DATE",
            severity="warning",
            title="A2",
            description="A2",
            source="Sucursal 2",
            record_reference="2",
            recipients=("s2@example.com",),
            metadata={"branch_title": "Sucursal 2"},
        ),
    ]

    batches = sender._build_recipient_batches(alerts)

    assert set(batches) == {
        (("s1@example.com",), "Sucursal 1"),
        (("s2@example.com",), "Sucursal 2"),
    }
    assert [alert.record_reference for alert in batches[(("s1@example.com",), "Sucursal 1")]] == ["1"]
    assert [alert.record_reference for alert in batches[(("s2@example.com",), "Sucursal 2")]] == ["2"]


def test_email_sender_batches_same_recipients_by_branch_title() -> None:
    settings = Settings(mail_to=("fallback@example.com",))
    sender = EmailSender(settings)
    alerts = [
        Alert(
            alert_id="a1",
            alert_type="GUIDE_DUE_DATE",
            severity="critical",
            title="A1",
            description="A1",
            source="MEXSR",
            record_reference="1",
            recipients=("same@example.com",),
            metadata={"branch_title": "Sucursal San Rafael"},
        ),
        Alert(
            alert_id="a2",
            alert_type="GUIDE_DUE_DATE",
            severity="warning",
            title="A2",
            description="A2",
            source="MEXRIOIV",
            record_reference="2",
            recipients=("same@example.com",),
            metadata={"branch_title": "Sucursal Cba"},
        ),
    ]

    batches = sender._build_recipient_batches(alerts)

    assert set(batches) == {
        (("same@example.com",), "Sucursal San Rafael"),
        (("same@example.com",), "Sucursal Cba"),
    }


def test_email_sender_dry_run_generates_preview(tmp_path: Path) -> None:
    settings = Settings(
        email_dry_run=True,
        email_preview_dir=tmp_path,
        mail_from="alertas@example.com",
        mail_to=("fallback@example.com",),
    )
    sender = EmailSender(settings)
    alert = Alert(
        alert_id="a1",
        alert_type="GUIDE_DUE_DATE",
        severity="critical",
        title="A1",
        description="A1",
        source="Sucursal 1",
        record_reference="1",
        recipients=("s1@example.com",),
    )

    email_sent = sender.send_alerts([alert])

    assert email_sent is False
    assert list(tmp_path.glob("*.html"))
    assert list(tmp_path.glob("*.eml"))


def test_email_sender_consolidates_guide_details_in_one_branch_email(tmp_path: Path) -> None:
    settings = Settings(
        email_dry_run=True,
        email_preview_dir=tmp_path,
        mail_from="alertas@example.com",
        mail_to=("fallback@example.com",),
    )
    sender = EmailSender(settings)
    alerts = [
        Alert(
            alert_id="a1",
            alert_type="GUIDE_DUE_DATE",
            severity="critical",
            title="A1",
            description="A1",
            source="MEXSR",
            record_reference="G-1",
            recipients=("s1@example.com",),
            metadata={
                "branch_title": "Sucursal San Rafael",
                "semaphore": "critical",
                "remito": "R-1",
                "cliente": "Cliente 1",
                "fecha_pactada_date": "2026-06-09",
                "estado": "DESPACHADO A SUCURSAL",
            },
        ),
        Alert(
            alert_id="a2",
            alert_type="GUIDE_DUE_DATE",
            severity="warning",
            title="A2",
            description="A2",
            source="MEXSR",
            record_reference="G-2",
            recipients=("s1@example.com",),
            metadata={
                "branch_title": "Sucursal San Rafael",
                "semaphore": "warning",
                "remito": "R-2",
                "cliente": "Cliente 2",
                "fecha_pactada_date": "2026-06-10",
                "estado": "RC-EN RUTA PARA SU ENTREGA",
            },
        ),
        Alert(
            alert_id="a3",
            alert_type="GUIDE_DUE_DATE",
            severity="info",
            title="A3",
            description="A3",
            source="MEXSR",
            record_reference="G-3",
            recipients=("s1@example.com",),
            metadata={
                "branch_title": "Sucursal San Rafael",
                "semaphore": "upcoming",
                "remito": "R-3",
                "cliente": "Cliente 3",
                "fecha_pactada_date": "2026-06-13",
                "estado": "DESP-Despachado",
            },
        ),
    ]

    sender.send_alerts(alerts)

    eml = message_from_string(next(tmp_path.glob("*.eml")).read_text(encoding="utf-8"))
    html = next(tmp_path.glob("*.html")).read_text(encoding="utf-8")

    assert eml["Subject"] == "Sucursal San Rafael - Alertas (1)"
    assert "Se detecto 1 alerta consolidada con 3 detalle(s)" in html
    assert "CRITICO (Hoy o vencidas) - Mostrando 1 de 1 registros" in html
    assert "PROXIMAS 48 HORAS - Mostrando 1 de 1 registros" in html
    assert "PROXIMA SEMANA - Mostrando 1 de 1 registros" in html
    assert all(label in html for label in ("Guia", "Cliente", "Pactada", "Estado"))
    assert "Remito" not in html
    assert all(value in html for value in ("G-1", "G-2", "G-3"))
    assert all(value not in html for value in ("R-1", "R-2", "R-3"))


def test_email_sender_limits_guide_details_to_thirty_per_section(tmp_path: Path) -> None:
    settings = Settings(
        email_dry_run=True,
        email_preview_dir=tmp_path,
        mail_from="alertas@example.com",
        mail_to=("fallback@example.com",),
    )
    sender = EmailSender(settings)
    alerts = [
        Alert(
            alert_id=f"a{index}",
            alert_type="GUIDE_DUE_DATE",
            severity="critical",
            title=f"A{index}",
            description=f"A{index}",
            source="MEXSR",
            record_reference=f"G-{index:03d}",
            recipients=("s1@example.com",),
            metadata={
                "branch_title": "Sucursal San Rafael",
                "semaphore": "critical",
                "remito": f"R-{index:03d}",
                "cliente": "Cliente 1",
                "fecha_pactada_date": "2026-06-09",
                "estado": "DESPACHADO A SUCURSAL",
            },
        )
        for index in range(1, 36)
    ]

    sender.send_alerts(alerts)

    html = next(tmp_path.glob("*.html")).read_text(encoding="utf-8")

    assert "Se detecto 1 alerta consolidada con 35 detalle(s)" in html
    assert "CRITICO (Hoy o vencidas) - Mostrando 30 de 35 registros" in html
    assert "G-030" in html
    assert "G-031" not in html


def test_email_sender_does_not_show_remito_or_tracking_columns(tmp_path: Path) -> None:
    settings = Settings(
        email_dry_run=True,
        email_preview_dir=tmp_path,
        mail_from="alertas@example.com",
        mail_to=("fallback@example.com",),
    )
    sender = EmailSender(settings)
    alert = Alert(
        alert_id="a1",
        alert_type="GUIDE_DUE_DATE",
        severity="critical",
        title="A1",
        description="A1",
        source="MEXSR",
        record_reference="103842782",
        recipients=("s1@example.com",),
        metadata={
            "branch_title": "Sucursal San Rafael",
            "semaphore": "critical",
            "remito": "NO-USAR-REMITO",
            "tracking": "NO-USAR-COMO-REMITO",
            "cliente": "Cliente 1",
            "fecha_pactada_date": "2026-06-09",
            "estado": "DESPACHADO A SUCURSAL",
        },
    )

    sender.send_alerts([alert])

    html = next(tmp_path.glob("*.html")).read_text(encoding="utf-8")

    assert "103842782" in html
    assert "Remito" not in html
    assert "NO-USAR-REMITO" not in html
    assert "NO-USAR-COMO-REMITO" not in html


def test_branch_name_resolver_uses_group_mapping(tmp_path: Path) -> None:
    mapping_file = tmp_path / "groups.json"
    mapping_file.write_text('{"MEXSR": "Sucursal San Rafael", "42": "Sucursal Cba"}', encoding="utf-8")
    settings = Settings(sucursal_groups_file=mapping_file)

    resolver = BranchNameResolver(settings)

    assert resolver.resolve({"codigo_sucursal": "MEXSR", "sucursal_id": 44}) == "Sucursal San Rafael"
    assert resolver.resolve({"sucursal_id": 42}) == "Sucursal Cba"
