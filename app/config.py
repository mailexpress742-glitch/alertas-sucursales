from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent


class ConfigurationError(RuntimeError):
    """Raised when a required runtime setting is missing or invalid."""


def _bool_from_env(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_from_env(value: str | None, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigurationError(f"Invalid integer value: {value!r}") from exc


def _float_from_env(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigurationError(f"Invalid numeric value: {value!r}") from exc


def _split_recipients(value: str | Iterable[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    return tuple(str(item).strip() for item in value if str(item).strip())


def _split_csv(value: str | Iterable[str] | None, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    parsed = _split_recipients(value)
    return parsed or default


def _path_from_env(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


@dataclass(frozen=True)
class Settings:
    db_type: str = "mssql"
    db_server: str = ""
    db_name: str = ""
    db_user: str = ""
    db_password: str = ""
    db_port: int | None = 1433
    db_driver: str = "ODBC Driver 18 for SQL Server"

    smtp_server: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_dry_run: bool = False
    email_preview_dir: Path = ROOT_DIR / "data" / "email_previews"
    mail_from: str = ""
    mail_to: tuple[str, ...] = ()

    alert_days_threshold: int = 7
    alert_amount_threshold: float = 100000.0
    enabled_rules: tuple[str, ...] = ("guide_due_date",)
    guide_due_date_column: str = "fecha_vencimiento"
    guide_lookahead_days: int = 7
    guide_max_rows: int = 1000
    guide_only_active: bool = True
    guide_only_unfinished: bool = True
    sucursal_recipients_file: Path = ROOT_DIR / "config" / "sucursal_recipients.json"
    sucursal_recipients_json: str = ""
    sucursal_groups_file: Path = ROOT_DIR / "config" / "sucursal_groups.json"
    sucursal_groups_json: str = ""
    environment: str = "local"
    app_timezone: str = "America/Argentina/Buenos_Aires"

    history_file: Path = ROOT_DIR / "data" / "alert_history.json"
    log_file: Path = ROOT_DIR / "logs" / "alertas.log"

    @classmethod
    def from_env(cls) -> "Settings":
        env_file = ROOT_DIR / ".env"
        if env_file.exists():
            load_dotenv(env_file)

        return cls(
            db_type=os.getenv("DB_TYPE", "mssql"),
            db_server=os.getenv("DB_SERVER", ""),
            db_name=os.getenv("DB_NAME", ""),
            db_user=os.getenv("DB_USER", ""),
            db_password=os.getenv("DB_PASSWORD", ""),
            db_port=_int_from_env(os.getenv("DB_PORT"), 1433),
            db_driver=os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
            smtp_server=os.getenv("SMTP_SERVER", ""),
            smtp_port=_int_from_env(os.getenv("SMTP_PORT"), 587) or 587,
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_use_tls=_bool_from_env(os.getenv("SMTP_USE_TLS"), True),
            email_dry_run=_bool_from_env(os.getenv("EMAIL_DRY_RUN"), False),
            email_preview_dir=_path_from_env(
                os.getenv("EMAIL_PREVIEW_DIR"), ROOT_DIR / "data" / "email_previews"
            ),
            mail_from=os.getenv("MAIL_FROM", ""),
            mail_to=_split_recipients(os.getenv("MAIL_TO")),
            alert_days_threshold=_int_from_env(os.getenv("ALERT_DAYS_THRESHOLD"), 7) or 7,
            alert_amount_threshold=_float_from_env(
                os.getenv("ALERT_AMOUNT_THRESHOLD"), 100000.0
            ),
            enabled_rules=_split_csv(os.getenv("ENABLED_RULES"), ("guide_due_date",)),
            guide_due_date_column=os.getenv("GUIDE_DUE_DATE_COLUMN", "fecha_vencimiento"),
            guide_lookahead_days=_int_from_env(os.getenv("GUIDE_LOOKAHEAD_DAYS"), 7) or 7,
            guide_max_rows=_int_from_env(os.getenv("GUIDE_MAX_ROWS"), 1000) or 1000,
            guide_only_active=_bool_from_env(os.getenv("GUIDE_ONLY_ACTIVE"), True),
            guide_only_unfinished=_bool_from_env(os.getenv("GUIDE_ONLY_UNFINISHED"), True),
            sucursal_recipients_file=_path_from_env(
                os.getenv("SUCURSAL_RECIPIENTS_FILE"),
                ROOT_DIR / "config" / "sucursal_recipients.json",
            ),
            sucursal_recipients_json=os.getenv("SUCURSAL_RECIPIENTS_JSON", ""),
            sucursal_groups_file=_path_from_env(
                os.getenv("SUCURSAL_GROUPS_FILE"),
                ROOT_DIR / "config" / "sucursal_groups.json",
            ),
            sucursal_groups_json=os.getenv("SUCURSAL_GROUPS_JSON", ""),
            environment=os.getenv("ENVIRONMENT", "local"),
            app_timezone=os.getenv("APP_TIMEZONE", "America/Argentina/Buenos_Aires"),
            history_file=_path_from_env(
                os.getenv("ALERT_HISTORY_FILE"), ROOT_DIR / "data" / "alert_history.json"
            ),
            log_file=_path_from_env(os.getenv("LOG_FILE"), ROOT_DIR / "logs" / "alertas.log"),
        )

    @property
    def is_github_actions(self) -> bool:
        return self.environment.lower() in {"github_actions", "github-actions", "actions"}

    @property
    def mail_to_csv(self) -> str:
        return ",".join(self.mail_to)

    def validate_runtime(self) -> None:
        missing: list[str] = []

        db_type = self.db_type.lower()
        if db_type != "sqlite":
            required_db = {
                "DB_TYPE": self.db_type,
                "DB_SERVER": self.db_server,
                "DB_NAME": self.db_name,
                "DB_USER": self.db_user,
                "DB_PASSWORD": self.db_password,
            }
            if db_type in {"mssql", "sqlserver", "sql_server"}:
                required_db["DB_DRIVER"] = self.db_driver
            missing.extend(name for name, value in required_db.items() if not value)

        required_email = {"MAIL_TO": self.mail_to}
        if not self.email_dry_run:
            required_email.update(
                {
                    "SMTP_SERVER": self.smtp_server,
                    "SMTP_PORT": self.smtp_port,
                    "SMTP_USER": self.smtp_user,
                    "SMTP_PASSWORD": self.smtp_password,
                    "MAIL_FROM": self.mail_from,
                }
            )
        missing.extend(name for name, value in required_email.items() if not value)

        if missing:
            joined = ", ".join(sorted(set(missing)))
            raise ConfigurationError(f"Missing required configuration values: {joined}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
