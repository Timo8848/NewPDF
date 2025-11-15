from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

import duckdb

from idp.config import get_settings


def persist_run(run_summary: Dict) -> None:
    settings = get_settings()
    db_path = settings.storage.duckdb_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(
        """
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
    )
    rows = [
        (
            run_summary["request_id"],
            doc["doc_type"],
            field_name,
            str(field_payload.get("value")),
            field_payload.get("confidence", 0.0),
            field_payload.get("valid", False),
        )
        for doc in run_summary["documents"]
        for field_name, field_payload in doc["fields"].items()
    ]
    con.executemany("INSERT INTO extractions VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", rows)
    con.close()


def aggregate_failures(limit: int = 20) -> list[dict]:
    settings = get_settings()
    db_path = settings.storage.duckdb_path
    if not Path(db_path).exists():
        return []
    con = duckdb.connect(str(db_path))
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
    con.close()
    return [{"field": row[0], "failures": row[1]} for row in res]
