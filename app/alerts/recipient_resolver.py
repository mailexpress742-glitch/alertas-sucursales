from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.config import Settings


logger = logging.getLogger(__name__)


class BranchRecipientResolver:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._mapping = self._load_mapping()

    def resolve(self, row: dict[str, Any]) -> tuple[str, ...]:
        candidates = [
            row.get("codigo_sucursal"),
            row.get("sucursal_descripcion"),
            row.get("sucursal_id"),
            row.get("source"),
        ]

        for candidate in candidates:
            recipients = self._mapping.get(self._normalize_key(candidate))
            if recipients:
                return recipients

        if self.settings.use_database_recipients:
            db_recipients = self._split_addresses(row.get("sucursal_mail") or row.get("mail"))
            if db_recipients:
                return db_recipients

        return self.settings.mail_to

    def _load_mapping(self) -> dict[str, tuple[str, ...]]:
        raw_mapping: dict[str, Any] = {}

        if self.settings.sucursal_recipients_json:
            try:
                raw_mapping = json.loads(self.settings.sucursal_recipients_json)
            except json.JSONDecodeError:
                logger.exception("Invalid SUCURSAL_RECIPIENTS_JSON. Ignoring mapping.")

        if not raw_mapping and self.settings.sucursal_recipients_file.exists():
            raw_mapping = self._load_mapping_file(self.settings.sucursal_recipients_file)

        normalized: dict[str, tuple[str, ...]] = {}
        for branch_key, recipients in raw_mapping.items():
            parsed = self._split_addresses(recipients)
            if parsed:
                normalized[self._normalize_key(branch_key)] = parsed

        return normalized

    @staticmethod
    def _load_mapping_file(path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            logger.exception("Could not load sucursal recipients file: %s", path)
            return {}

        if not isinstance(payload, dict):
            logger.error("Sucursal recipients file must contain a JSON object")
            return {}

        return payload

    @staticmethod
    def _split_addresses(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()

        if isinstance(value, str):
            raw_items = value.replace(";", ",").split(",")
        elif isinstance(value, (list, tuple, set)):
            raw_items = []
            for item in value:
                raw_items.extend(str(item).replace(";", ",").split(","))
        else:
            raw_items = str(value).replace(";", ",").split(",")

        recipients: list[str] = []
        for item in raw_items:
            recipient = item.strip()
            if recipient and recipient not in recipients:
                recipients.append(recipient)

        return tuple(recipients)

    @staticmethod
    def _normalize_key(value: Any) -> str:
        return str(value or "").strip().lower()
