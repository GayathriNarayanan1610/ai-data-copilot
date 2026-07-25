"""Pure SQL guardrails — no I/O, so they are directly unit-testable.

``clean_sql``      : strip markdown fences / prose / comments the model adds and
                     isolate the query itself.
``is_safe_select`` : allow read-only SELECT/WITH only; block writes, DDL, multiple
                     statements and comment injection.

This is the *first* line of defence. It is backed by two more (see ``db.py``): the
connection is opened read-only (``mode=ro``) and a SQLite authorizer denies every
write action at the driver level. Regexes alone are never trusted for security.
"""
from __future__ import annotations

import re

NO_QUERY = "NO_QUERY"  # sentinel the model returns when a question is unanswerable

# Write / DDL / admin statements. REPLACE is matched only as the statement form
# ``REPLACE INTO`` so the read-only ``REPLACE(col, a, b)`` string *function* is not
# a false positive.
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|ATTACH|DETACH|"
    r"PRAGMA|GRANT|REVOKE|VACUUM|REINDEX)\b|\bREPLACE\s+INTO\b",
    re.I,
)

_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_FENCE = re.compile(r"```(?:sql)?", re.I)
_LEADING_LABEL = re.compile(r"^\s*sql\s*:\s*", re.I)
_FIRST_STATEMENT = re.compile(r"\b(SELECT|WITH)\b", re.I)
_STARTS_SELECT = re.compile(r"^\s*(SELECT|WITH)\b", re.I)


def clean_sql(raw: str) -> str:
    """Best-effort normalisation of a raw model response into a bare SQL string."""
    s = (raw or "").strip()
    if NO_QUERY in s.upper() and not re.search(r"\bSELECT\b", s, re.I):
        return NO_QUERY

    s = _FENCE.sub("", s).strip()          # drop ```sql ... ``` fences
    s = _LEADING_LABEL.sub("", s)          # drop a leading "SQL:" label
    s = _BLOCK_COMMENT.sub(" ", s)         # drop /* ... */ comments
    s = _LINE_COMMENT.sub("", s)           # drop -- ... comments

    match = _FIRST_STATEMENT.search(s)     # isolate from the first SELECT / WITH
    if match:
        s = s[match.start():]
    return s.strip().rstrip(";").strip()


def is_safe_select(sql: str) -> tuple[bool, str]:
    """Return (is_safe, reason). Reason is empty when safe."""
    s = (sql or "").strip().rstrip(";").strip()
    if not s:
        return False, "Empty query."
    if not _STARTS_SELECT.match(s):
        return False, "Only read-only SELECT queries are allowed."
    if _FORBIDDEN.search(s):
        return False, "Query was blocked: it attempted to modify the database."
    if ";" in s:
        return False, "Multiple statements are not allowed."
    if "--" in s or "/*" in s:
        return False, "SQL comments are not allowed."
    return True, ""
