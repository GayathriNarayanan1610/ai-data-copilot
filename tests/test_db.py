from __future__ import annotations

import pytest

from datacopilot.db import get_schema, run_query
from datacopilot.exceptions import QueryExecutionError


def test_schema_lists_tables(db_path):
    schema = get_schema(db_path)
    for table in ("students", "subjects", "grades"):
        assert table in schema


def test_select_returns_rows(db_path):
    df = run_query("SELECT COUNT(*) AS n FROM students", db_path)
    assert int(df.iloc[0]["n"]) == 60


def test_row_limit_is_enforced(db_path):
    df = run_query("SELECT * FROM students", db_path, row_limit=5)
    assert len(df) == 5


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO students VALUES (999, 'Mallory', 1, 'Nowhere')",
        "UPDATE students SET city='Hacked'",
        "DELETE FROM grades",
    ],
)
def test_writes_are_rejected_at_driver_level(db_path, sql):
    # Even if a write bypassed the guardrails, the read-only connection + authorizer
    # must reject it.
    with pytest.raises(QueryExecutionError):
        run_query(sql, db_path)


def test_bad_sql_raises_query_execution_error(db_path):
    with pytest.raises(QueryExecutionError):
        run_query("SELECT nope FROM students", db_path)
