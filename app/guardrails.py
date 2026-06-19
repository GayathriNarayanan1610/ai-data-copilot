"""Pure SQL guardrails — no I/O, so they are directly unit-testable.

clean_sql      : strip markdown fences / prose the model adds, isolate the query.
is_safe_select : allow read-only SELECT/WITH only; block writes and stacked queries.
"""
from __future__ import annotations

import re

NO_QUERY = "NO_QUERY"  # sentinel the model returns when a question is unanswerable

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|ATTACH|DETACH|PRAGMA|GRANT|REVOKE|VACUUM)\b",
    re.I,
)


def clean_sql(raw: str) -> str:
    s = (raw or "").strip()
    if NO_QUERY in s.upper() and not re.search(r"\bSELECT\b", s, re.I):
        return NO_QUERY
    # strip ```sql ... ``` fences and a leading "SQL:" label
    s = re.sub(r"```(?:sql)?", "", s, flags=re.I).strip()
    s = re.sub(r"^\s*sql\s*:\s*", "", s, flags=re.I)
    # isolate from the first SELECT / WITH
    m = re.search(r"\b(SELECT|WITH)\b", s, flags=re.I)
    if m:
        s = s[m.start():]
    return s.strip().rstrip(";").strip()


def is_safe_select(sql: str) -> tuple[bool, str]:
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        return False, "Empty query."
    if not re.match(r"^\s*(SELECT|WITH)\b", s, re.I):
        return False, "Only read-only SELECT queries are allowed."
    if _FORBIDDEN.search(s):
        return False, "Query was blocked: it attempted to modify the database."
    if ";" in s:
        return False, "Multiple statements are not allowed."
    return True, ""
