from app.guardrails import clean_sql, is_safe_select, NO_QUERY


def test_clean_strips_markdown_fences():
    raw = "```sql\nSELECT * FROM students;\n```"
    assert clean_sql(raw) == "SELECT * FROM students"


def test_clean_handles_sql_label_and_prose():
    assert clean_sql("SQL: SELECT name FROM students") == "SELECT name FROM students"


def test_clean_detects_no_query():
    assert clean_sql("NO_QUERY") == NO_QUERY
    assert clean_sql("Sorry, NO_QUERY") == NO_QUERY


def test_safe_select_allows_select_and_with():
    assert is_safe_select("SELECT * FROM students")[0] is True
    assert is_safe_select("WITH t AS (SELECT 1) SELECT * FROM t")[0] is True


def test_safe_select_blocks_writes():
    assert is_safe_select("DELETE FROM grades")[0] is False
    assert is_safe_select("DROP TABLE students")[0] is False
    assert is_safe_select("UPDATE students SET city='x'")[0] is False


def test_safe_select_blocks_stacked_statements():
    assert is_safe_select("SELECT 1; DROP TABLE students")[0] is False
