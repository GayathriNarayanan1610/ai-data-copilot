"""Database access: schema for the prompt, and READ-ONLY query execution."""
from __future__ import annotations

import sqlite3

import pandas as pd


def get_schema(db_path: str) -> str:
    """Return the CREATE statements — what the model needs to write correct SQL."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL ORDER BY name"
        ).fetchall()
    finally:
        conn.close()
    return "\n\n".join(r[0] for r in rows)


def run_query(sql: str, db_path: str, row_limit: int = 100) -> pd.DataFrame:
    """Execute a query against a READ-ONLY connection and return a DataFrame.

    Opening the database in mode=ro means even if a write somehow slipped past the
    guardrails, SQLite itself would reject it — defense in depth.
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query(sql, conn)
    finally:
        conn.close()
    return df.head(row_limit)
