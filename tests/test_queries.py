from __future__ import annotations

from app.database.queries import get_guides_due_for_week


class FakeDatabase:
    def __init__(self) -> None:
        self.sql = ""
        self.params = {}
        self.calls = []

    def execute_select(self, sql: str, params: dict | None = None) -> list[dict]:
        self.sql = sql
        self.params = params or {}
        self.calls.append((sql, self.params))
        return []


def test_guides_due_query_uses_bounded_date_window() -> None:
    db = FakeDatabase()

    get_guides_due_for_week(
        db,
        due_date_column="fechaplanilla",
        lookahead_days=7,
        lookback_days=30,
        max_rows=500,
    )

    assert "r.fechaplanilla >= DATE_ADD(CURRENT_DATE, INTERVAL :window_start_days DAY)" in db.sql
    assert "r.fechaplanilla < DATE_ADD(CURRENT_DATE, INTERVAL :window_end_days DAY)" in db.sql
    assert "DATE(r.fechaplanilla) <= DATE_ADD" not in db.sql
    assert [params for _, params in db.calls] == [
        {"window_start_days": -30, "window_end_days": 1, "max_rows": 500},
        {"window_start_days": 1, "window_end_days": 3, "max_rows": 500},
        {"window_start_days": 3, "window_end_days": 8, "max_rows": 500},
    ]


def test_guides_due_query_uses_separate_windows_per_semaphore() -> None:
    db = FakeDatabase()

    get_guides_due_for_week(
        db,
        due_date_column="fechaplanilla",
        lookahead_days=2,
        lookback_days=15,
        max_rows=30,
    )

    assert len(db.calls) == 2
    assert [params for _, params in db.calls] == [
        {"window_start_days": -15, "window_end_days": 1, "max_rows": 30},
        {"window_start_days": 1, "window_end_days": 3, "max_rows": 30},
    ]
