from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.config import Settings


logger = logging.getLogger(__name__)


class BranchNameResolver:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._mapping = self._load_mapping()

    def resolve(self, row: dict[str, Any]) -> str:
        candidates = [
            row.get("codigo_sucursal"),
            row.get("sucursal_descripcion"),
            row.get("sucursal_id"),
            row.get("source"),
        ]

        for candidate in candidates:
            branch_name = self._mapping.get(self._normalize_key(candidate))
            if branch_name:
                return branch_name

        fallback = row.get("codigo_sucursal") or row.get("sucursal_descripcion") or row.get("sucursal_id")
        return str(fallback or "Sucursal sin identificar")

    def _load_mapping(self) -> dict[str, str]:
        raw_mapping: dict[str, Any] = {}

        if self.settings.sucursal_groups_json:
            try:
                raw_mapping = json.loads(self.settings.sucursal_groups_json)
            except json.JSONDecodeError:
                logger.exception("Invalid SUCURSAL_GROUPS_JSON. Ignoring mapping.")

        if not raw_mapping and self.settings.sucursal_groups_file.exists():
            raw_mapping = self._load_mapping_file(self.settings.sucursal_groups_file)

        normalized: dict[str, str] = {}
        for branch_key, branch_name in raw_mapping.items():
            if branch_name:
                normalized[self._normalize_key(branch_key)] = str(branch_name).strip()

        return normalized

    @staticmethod
    def _load_mapping_file(path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            logger.exception("Could not load sucursal groups file: %s", path)
            return {}

        if not isinstance(payload, dict):
            logger.error("Sucursal groups file must contain a JSON object")
            return {}

        return payload

    @staticmethod
    def _normalize_key(value: Any) -> str:
        return str(value or "").strip().lower()

