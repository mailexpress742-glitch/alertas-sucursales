from __future__ import annotations

import logging

from app.alerts.alert_engine import AlertEngine
from app.alerts.alert_history import AlertHistory
from app.config import get_settings
from app.database.connection import DatabaseConnection
from app.email_service.email_sender import EmailSender
from app.logging_config import setup_logging


logger = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    setup_logging(settings)
    db_connection: DatabaseConnection | None = None

    try:
        settings.validate_runtime()
        db_connection = DatabaseConnection(settings)
        email_sender = EmailSender(settings)
        history = AlertHistory(settings.history_file)
        engine = AlertEngine(
            settings=settings,
            db_connection=db_connection,
            email_sender=email_sender,
            history=history,
        )
        summary = engine.run()
        logger.info("Final summary: %s", summary.to_dict())
        return 0
    except Exception:
        logger.exception("Critical error while running alert process")
        return 1
    finally:
        if db_connection is not None:
            db_connection.close()


if __name__ == "__main__":
    raise SystemExit(main())

