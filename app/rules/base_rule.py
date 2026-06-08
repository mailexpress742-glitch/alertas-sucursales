from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.alerts.alert_model import Alert
from app.config import Settings


class BaseRule(ABC):
    name: str
    description: str
    severity: str
    data_key: str

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def evaluate(self, data: list[dict[str, Any]]) -> list[Alert]:
        """Return alerts produced by this rule."""

