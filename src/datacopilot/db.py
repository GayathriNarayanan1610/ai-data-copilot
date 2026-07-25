"""Database access: schema for the prompt, and READ-ONLY query execution.

Three independent layers keep execution read-only (defence in depth):
  1. guardrails (``guardrails.py``) reject non-SELECT text before we ever connect;
  2. the connection is opened with ``mode=ro`` so SQLite itself rejects writes;
  3. a SQLite *authorizer* denies every write/DDL action at prepare time, giving a
     clean error rather than a late failure.

Only ``row_limit`` rows are fetched from the cursor, so a pathological query can't
pull an unbounded result set into memory.
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from .exceptions import QueryExecutionError, SchemaError
from .logging_config import get_logger

log = get_logger(__name__)

# SQLite authorizer action codes that represent a mutation or schema change.
_DENIED_ACTIONS = {
    sqlite3.SQLITE_INSERT,
    sqlite3.SQLITE_UPDATE,
    sqlite3.SQLITE_DELETE,
    sqlite3.SQLITE_CREATE_TABLE,
    sqlite3.SQLITE_CREATE_INDEX,
    sqlite3.SQLITE_CREATE_TRIGGER,
    sqlite3.SQLITE_CREATE_VIEW,
    sqlite3.SQLITE_CREATE_TEMP_TABLE,
    sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
    sqlite3.SQLITE_CREATE_TEMP_VIEW,
    sqlite3.SQLITE_CREATE_VTABLE,
    sqlite3.SQLITE_DROP_TABLE,
    sqlite3.SQLITE_DROP_INDEX,
    sqlite3.SQLITE_DROP_TRIGGER,
    sqlite3.SQLITE_DROP_VIEW,
    sqlite3.SQLITE_DROP_VTABLE,
    sqlite3.SQLITE_ALTER_TABLE,
    sqlite3.SQLITE_ATTACH,
    sqlite3.SQLITE_DETACH,
}


def _readonly_authorizer(action: int, *_args: object) -> int:
    """Deny any write/DDL action; allow everything else (reads, functions, CTEs)."""
    return sqlite3.SQLITE_DENY if action in _DENIED_ACTIONS else sqlite3.SQLITE_OK


def _connect(db_path: str, *, read_only: bool, timeout: float = 5.0) -> sqlite3.Connection:
    if read_only:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=timeout)
        conn.set_authorizer(_readonly_authorizer)
    else:
        conn = sqlite3.connect(db_path, timeout=timeout)
    return conn


def get_schema(db_path: str) -> str:
    """Return the CREATE statements — what the model needs to write correct SQL."""
    try:
        conn = _connect(db_path, read_only=True)
    except sqlite3.Error as exc:
        raise SchemaError(f"Could not open database at {db_path}: {exc}") from exc
    try:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND sql IS NOT NULL ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        raise SchemaError(f"No tables found in database at {db_path}")
    return "\n\n".join(r[0] for r in rows)


def run_query(sql: str, db_path: str, row_limit: int = 100, timeout: float = 5.0) -> pd.DataFrame:
    """Execute ``sql`` read-only and return at most ``row_limit`` rows as a DataFrame.

    Raises ``QueryExecutionError`` on any SQL/execution failure so the caller's
    self-correction loop (or the API's error handler) can react.
    """
    conn = _connect(db_path, read_only=True, timeout=timeout)
    try:
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(row_limit)
        return pd.DataFrame(rows, columns=columns)
    except sqlite3.Error as exc:
        raise QueryExecutionError(str(exc)) from exc
    finally:
        conn.close()
