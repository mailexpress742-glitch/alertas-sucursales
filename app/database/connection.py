from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError

from app.config import ConfigurationError, Settings


logger = logging.getLogger(__name__)


FORBIDDEN_SQL_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|merge|create|replace|grant|revoke)\b",
    re.IGNORECASE,
)


class ReadOnlyQueryError(ValueError):
    """Raised when a query does not comply with the read-only policy."""


class DatabaseConnection:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._engine: Engine | None = None

    def connect(self) -> Engine:
        if self._engine is not None:
            return self._engine

        try:
            self._engine = create_engine(self._build_url(), pool_pre_ping=True, future=True)
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info(
                "Database connection validated for type=%s server=%s database=%s",
                self.settings.db_type,
                self._masked(self.settings.db_server),
                self._masked(self.settings.db_name),
            )
            return self._engine
        except SQLAlchemyError as exc:
            logger.exception("Could not connect to the database")
            raise

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    def execute_select(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self._ensure_read_only(sql)
        try:
            engine = self.connect()
            with engine.connect() as connection:
                result = connection.execute(text(sql), params or {})
                rows = [dict(row._mapping) for row in result]
            logger.info("Read-only query returned %s rows", len(rows))
            return rows
        except SQLAlchemyError:
            logger.exception("Read-only query failed")
            raise

    def _build_url(self):
        db_type = self.settings.db_type.lower()

        if db_type in {"mssql", "sqlserver", "sql_server"}:
            return URL.create(
                "mssql+pyodbc",
                username=self.settings.db_user,
                password=self.settings.db_password,
                host=self.settings.db_server,
                port=self.settings.db_port,
                database=self.settings.db_name,
                query={
                    "driver": self.settings.db_driver,
                    "TrustServerCertificate": "yes",
                },
            )

        if db_type == "sqlite":
            db_path = self.settings.db_name or ":memory:"
            return f"sqlite:///{db_path}"

        if db_type in {"mysql", "mariadb"}:
            return URL.create(
                "mysql+pymysql",
                username=self.settings.db_user,
                password=self.settings.db_password,
                host=self.settings.db_server,
                port=self.settings.db_port,
                database=self.settings.db_name,
                query={"charset": "utf8mb4"},
            )

        raise ConfigurationError(
            f"Unsupported DB_TYPE={self.settings.db_type!r}. "
            "Supported values for this version: mssql, sqlserver, mysql, mariadb, sqlite."
        )

    @staticmethod
    def _ensure_read_only(sql: str) -> None:
        clean_sql = sql.strip()
        if not clean_sql:
            raise ReadOnlyQueryError("Empty SQL is not allowed")

        first_token = clean_sql.split(maxsplit=1)[0].lower()
        if first_token not in {"select", "with"}:
            raise ReadOnlyQueryError("Only SELECT/WITH queries are allowed")

        if FORBIDDEN_SQL_RE.search(clean_sql):
            raise ReadOnlyQueryError("The query contains a forbidden SQL command")

    @staticmethod
    def _masked(value: str) -> str:
        if not value:
            return "<empty>"
        return value[:2] + "***" if len(value) > 2 else "***"
