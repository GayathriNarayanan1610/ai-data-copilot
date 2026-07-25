"""Orchestration: question -> SQL -> guardrail -> run -> self-correct -> result.

Status outcomes:
  success  : a SELECT ran and returned rows
  refused  : the model judged the question unanswerable from the schema (grounding)
  blocked  : the SQL was unsafe (write / stacked) and was never executed
  error    : the SQL kept failing after self-correction retries
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import settings
from .db import get_schema, run_query
from .exceptions import QueryExecutionError
from .guardrails import NO_QUERY, clean_sql, is_safe_select
from .llm import get_planner
from .logging_config import get_logger

log = get_logger(__name__)


@dataclass
class Result:
    question: str
    status: str                       # success | refused | blocked | error
    sql: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    error: str = ""
    attempts: int = 0
    latency_ms: float = 0.0
    mode: str = settings.llm_mode

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "status": self.status,
            "sql": self.sql,
            "columns": self.columns,
            "rows": self.rows,
            "error": self.error,
            "attempts": self.attempts,
            "latency_ms": round(self.latency_ms, 1),
            "mode": self.mode,
            "row_count": len(self.rows),
        }


class Copilot:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.schema = get_schema(self.db_path)
        self.planner = get_planner()

    def ask(self, question: str) -> Result:
        start = time.perf_counter()
        question = (question or "").strip()
        if not question:
            return Result(question, "refused", error="Question must not be empty.")

        log.info("copilot.ask", extra={"question": question})
        sql = clean_sql(self.planner.plan(self.schema, question))

        if sql == NO_QUERY or not sql:
            return self._finish(
                Result(question, "refused",
                       error="The question can't be answered from this database."),
                start,
            )

        attempts = 0
        last_error = ""
        while attempts <= settings.max_retries:
            attempts += 1
            safe, reason = is_safe_select(sql)
            if not safe:
                log.warning("blocked unsafe sql", extra={"sql": sql, "reason": reason})
                return self._finish(
                    Result(question, "blocked", sql=sql, error=reason, attempts=attempts),
                    start,
                )
            try:
                df = run_query(sql, self.db_path, settings.row_limit, settings.query_timeout_s)
                return self._finish(
                    Result(question, "success", sql=sql,
                           columns=list(df.columns),
                           rows=df.to_dict(orient="records"), attempts=attempts),
                    start,
                )
            except QueryExecutionError as exc:
                last_error = str(exc)
                log.info("sql failed, attempting self-correction",
                         extra={"attempt": attempts, "error": last_error})
                if attempts <= settings.max_retries:
                    sql = clean_sql(self.planner.fix(self.schema, question, sql, last_error))

        return self._finish(
            Result(question, "error", sql=sql, error=last_error, attempts=attempts),
            start,
        )

    @staticmethod
    def _finish(result: Result, start: float) -> Result:
        result.latency_ms = (time.perf_counter() - start) * 1000.0
        log.info("copilot.result",
                 extra={"status": result.status, "attempts": result.attempts,
                        "rows": len(result.rows), "latency_ms": round(result.latency_ms, 1)})
        return result
