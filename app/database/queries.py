from __future__ import annotations

from typing import Protocol


class ReadOnlyDatabase(Protocol):
    def execute_select(self, sql: str, params: dict | None = None) -> list[dict]:
        ...


# Replace table and column names with the real production read-only views.
# Expected output fields: record_reference, status, created_at or age_days, source.
PENDING_ITEMS_QUERY = """
SELECT
    id AS record_reference,
    status,
    created_at,
    DATEDIFF(CURRENT_DATE, created_at) AS age_days,
    branch AS source
FROM dbo.pending_items
WHERE status = 'PENDING'
"""


# Expected output fields: record_reference, amount, movement_date, source.
FINANCIAL_MOVEMENTS_QUERY = """
SELECT
    id AS record_reference,
    amount,
    movement_date,
    branch AS source
FROM dbo.financial_movements
WHERE movement_date >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
"""


# Expected output fields: record_reference, process_name, expected_status,
# current_status, checked_at, source.
PROCESS_STATUS_QUERY = """
SELECT
    id AS record_reference,
    process_name,
    expected_status,
    current_status,
    checked_at,
    branch AS source
FROM dbo.process_status
WHERE current_status <> expected_status
"""


def get_pending_items(db: ReadOnlyDatabase) -> list[dict]:
    return db.execute_select(PENDING_ITEMS_QUERY)


def get_financial_movements(db: ReadOnlyDatabase) -> list[dict]:
    return db.execute_select(FINANCIAL_MOVEMENTS_QUERY)


def get_process_status(db: ReadOnlyDatabase) -> list[dict]:
    return db.execute_select(PROCESS_STATUS_QUERY)


ALLOWED_GUIDE_DATE_COLUMNS = {
    "fecha_retiro",
    "fecha_vencimiento",
    "fechaplanilla",
    "fecha_hora",
    "fechaUltimoEstado",
    "fecha_hora_entrega",
    "fechaRepactacion",
}


GUIDES_DUE_QUERY_TEMPLATE = """
SELECT
    r.id AS record_reference,
    r.id AS retiro_id,
    r.sucursal_id,
    s.codigo_sucursal,
    s.descripcion AS sucursal_descripcion,
    s.mail AS sucursal_mail,
    r.{due_date_column} AS fecha_pactada,
    DATE(r.{due_date_column}) AS fecha_pactada_date,
    DATEDIFF(DATE(r.{due_date_column}), CURRENT_DATE) AS days_until_due,
    r.estado_id,
    r.rendido,
    r.finalizada,
    r.activa,
    r.tracking,
    r.created_at,
    r.updated_at
FROM retiro r
INNER JOIN sucursal s ON s.id = r.sucursal_id
WHERE r.{due_date_column} IS NOT NULL
  AND DATE(r.{due_date_column}) <= DATE_ADD(CURRENT_DATE, INTERVAL :lookahead_days DAY)
  {status_filters}
ORDER BY DATE(r.{due_date_column}) ASC, s.codigo_sucursal ASC, r.id ASC
LIMIT :max_rows
"""


def get_guides_due_for_week(
    db: ReadOnlyDatabase,
    due_date_column: str = "fecha_vencimiento",
    lookahead_days: int = 7,
    max_rows: int = 1000,
    only_active: bool = True,
    only_unfinished: bool = True,
) -> list[dict]:
    column = _validate_guide_date_column(due_date_column)
    status_filters = _build_guide_status_filters(only_active, only_unfinished)
    sql = GUIDES_DUE_QUERY_TEMPLATE.format(
        due_date_column=column,
        status_filters=status_filters,
    )
    return db.execute_select(sql, {"lookahead_days": lookahead_days, "max_rows": max_rows})


def _validate_guide_date_column(column: str) -> str:
    if column not in ALLOWED_GUIDE_DATE_COLUMNS:
        allowed = ", ".join(sorted(ALLOWED_GUIDE_DATE_COLUMNS))
        raise ValueError(f"Invalid GUIDE_DUE_DATE_COLUMN={column!r}. Allowed values: {allowed}")
    return column


def _build_guide_status_filters(only_active: bool, only_unfinished: bool) -> str:
    filters: list[str] = []
    if only_active:
        filters.append("AND (r.activa = 1 OR r.activa IS NULL)")
    if only_unfinished:
        filters.append("AND (r.finalizada = 0 OR r.finalizada IS NULL)")
    return "\n  ".join(filters)
