from __future__ import annotations

import pytest

from datacopilot.guardrails import NO_QUERY, clean_sql, is_safe_select


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("```sql\nSELECT 1;\n```", "SELECT 1"),
        ("SQL: SELECT name FROM students", "SELECT name FROM students"),
        ("SELECT 1 -- trailing comment", "SELECT 1"),
        ("Here you go: SELECT * FROM students", "SELECT * FROM students"),
        ("NO_QUERY", NO_QUERY),
    ],
)
def test_clean_sql(raw, expected):
    assert clean_sql(raw) == expected


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM students",
        "WITH t AS (SELECT 1 AS x) SELECT x FROM t",
        "SELECT REPLACE(name, 'a', 'b') FROM students",  # REPLACE() function is fine
    ],
)
def test_safe_selects_are_allowed(sql):
    ok, reason = is_safe_select(sql)
    assert ok, reason


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM grades",
        "UPDATE students SET city='X'",
        "DROP TABLE students",
        "INSERT INTO students VALUES (1,'a',1,'b')",
        "SELECT 1; DROP TABLE students",           # stacked
        "SELECT 1 /* hidden */",                    # comment injection
        "REPLACE INTO students VALUES (1,'a',1,'b')",
        "",                                          # empty
    ],
)
def test_unsafe_queries_are_blocked(sql):
    ok, _ = is_safe_select(sql)
    assert not ok
