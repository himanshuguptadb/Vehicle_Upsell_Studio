"""Thin wrapper over the Databricks SQL Statement Execution API.

Used for everything interactive: config/component CRUD and the small ``ai_query``
test/compare runs. The SQL Warehouse auto-starts on first use.
"""
from __future__ import annotations

from typing import Any

from databricks.sdk.service.sql import StatementState

from .config import get_workspace_client, settings


class SqlError(RuntimeError):
    pass


def run_sql(statement: str, *, catalog: str | None = None, schema: str | None = None,
            wait_seconds: int = 300) -> list[dict[str, Any]]:
    """Execute a SQL statement on the configured warehouse and return rows as dicts.

    Uses the synchronous-ish wait pattern (the SDK polls up to ``wait_seconds``).
    """
    w = get_workspace_client()
    if not settings.warehouse_id:
        raise SqlError("No SQL Warehouse configured (set WAREHOUSE_ID).")

    resp = w.statement_execution.execute_statement(
        warehouse_id=settings.warehouse_id,
        statement=statement,
        catalog=catalog or settings.catalog,
        schema=schema or settings.schema,
        wait_timeout="50s",
    )

    # Poll until terminal if still running.
    import time
    waited = 0
    while resp.status and resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if waited >= wait_seconds:
            raise SqlError(f"Statement timed out after {wait_seconds}s")
        time.sleep(2)
        waited += 2
        resp = w.statement_execution.get_statement(resp.statement_id)

    state = resp.status.state if resp.status else None
    if state != StatementState.SUCCEEDED:
        msg = ""
        if resp.status and resp.status.error:
            msg = resp.status.error.message or ""
        raise SqlError(f"SQL failed ({state}): {msg}\n---\n{statement[:2000]}")

    return _rows_to_dicts(resp)


def _rows_to_dicts(resp) -> list[dict[str, Any]]:
    if not resp.manifest or not resp.manifest.schema or not resp.result:
        return []
    cols = [c.name for c in resp.manifest.schema.columns]
    data = resp.result.data_array or []
    return [dict(zip(cols, row)) for row in data]


def sql_str(value: str | None) -> str:
    """Escape a Python string into a single-quoted SQL literal."""
    if value is None:
        return "NULL"
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
