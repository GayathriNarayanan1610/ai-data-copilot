"""Orchestration: question -> SQL -> guardrail -> run -> self-correct -> result.

Status outcomes:
  success  : a SELECT ran and returned rows
  refused  : the model judged the question unanswerable from the schema (grounding)
  blocked  : the SQL was unsafe (write / stacked) and was never executed
  error    : the SQL kept failing after self-correction retries
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import settings
from .db import get_schema, run_query
from .guardrails import NO_QUERY, clean_sql, is_safe_select
from .llm import get_planner


@dataclass
class Result:
    question: str
    status: str                       # success | refused | blocked | error
    sql: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    error: str = ""
    attempts: int = 0

    def to_dict(self) -> dict:
        return {
            "question": self.question, "status": self.status, "sql": self.sql,
            "columns": self.columns, "rows": self.rows, "error": self.error,
            "attempts": self.attempts, "row_count": len(self.rows),
        }


class Copilot:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.schema = get_schema(self.db_path)
        self.planner = get_planner()

    def ask(self, question: str) -> Result:
        sql = clean_sql(self.planner.plan(self.schema, question))
        if sql == NO_QUERY or not sql:
            return Result(question, "refused",
                          error="The question can't be answered from this database.")

        attempts = 0
        last_error = ""
        while attempts <= settings.max_retries:
            attempts += 1
            safe, reason = is_safe_select(sql)
            if not safe:
                return Result(question, "blocked", sql=sql, error=reason, attempts=attempts)
            try:
                df = run_query(sql, self.db_path, settings.row_limit)
                return Result(question, "success", sql=sql,
                              columns=list(df.columns),
                              rows=df.to_dict(orient="records"), attempts=attempts)
            except Exception as exc:  # noqa: BLE001 - surface DB errors to self-correction
                last_error = str(exc)
                if attempts <= settings.max_retries:
                    sql = clean_sql(self.planner.fix(self.schema, question, sql, last_error))
        return Result(question, "error", sql=sql, error=last_error, attempts=attempts)
