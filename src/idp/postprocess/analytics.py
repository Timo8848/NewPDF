"""DuckDB-backed run summary persistence.

A single connection is opened per process via `get_connection()`; the schema
is created once at startup with `init_schema()`. The previous implementation
opened a fresh connection (and re-ran CREATE TABLE) on every request, which
serialized concurrent extractions behind DuckDB's file lock.
"""
from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Dict, Optional

import duckdb

from idp.config import get_settings

_conn: Optional[duckdb.DuckDBPyConnection] = None
_lock = Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS extractions (
    request_id VARCHAR,
    doc_type VARCHAR,
    field_name VARCHAR,
    value VARCHAR,
    confidence DOUBLE,
    valid BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def get_connection() -> duckdb.DuckDBPyConnection:
    global _conn
    with _lock:
        if _conn is None:
            settings = get_settings()
            db_path = settings.storage.duckdb_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            _conn = duckdb.connect(str(db_path))
            _conn.execute(_SCHEMA)
        return _conn


def init_schema() -> None:
    """Idempotently ensure the table exists. Call once on startup."""
    get_connection()


def close_connection() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def persist_run(run_summary: Dict) -> None:
    con = get_connection()
    rows = [
        (
            run_summary["request_id"],
            doc["doc_type"],
            field_name,
            str(field_payload.get("value")),
            float(field_payload.get("confidence", 0.0)),
            bool(field_payload.get("valid", False)),
        )
        for doc in run_summary["documents"]
        for field_name, field_payload in doc["fields"].items()
    ]
    if not rows:
        return
    with _lock:
        con.executemany(
            "INSERT INTO extractions VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            rows,
        )


def aggregate_failures(limit: int = 20) -> list[dict]:
    settings = get_settings()
    if not Path(settings.storage.duckdb_path).exists():
        return []
    con = get_connection()
    with _lock:
        res = con.execute(
            """
            SELECT field_name, COUNT(*) AS failures
            FROM extractions
            WHERE valid = FALSE
            GROUP BY field_name
            HAVING COUNT(*) > 0
            ORDER BY failures DESC
            LIMIT ?
            """,
            [limit],
        ).fetchall()
    return [{"field": row[0], "failures": row[1]} for row in res]
