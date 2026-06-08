from __future__ import annotations

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


def test_branch_name_resolver_uses_group_mapping(tmp_path: Path) -> None:
    mapping_file = tmp_path / "groups.json"
    mapping_file.write_text('{"MEXSR": "Sucursal San Rafael", "42": "Sucursal Cba"}', encoding="utf-8")
    settings = Settings(sucursal_groups_file=mapping_file)

    resolver = BranchNameResolver(settings)

    assert resolver.resolve({"codigo_sucursal": "MEXSR", "sucursal_id": 44}) == "Sucursal San Rafael"
    assert resolver.resolve({"sucursal_id": 42}) == "Sucursal Cba"
