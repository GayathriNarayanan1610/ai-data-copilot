"""The planner: turn a question into SQL, and fix SQL given an error.

``mock``   : deterministic keyword router — no model, no network. Enough to run and
             test the full pipeline offline, including the unsafe-query, off-topic
             and self-correction paths. Matched to the demo schema.
``ollama`` : local Llama 3 via Ollama.
``gemini`` : Google Gemini (needs GOOGLE_API_KEY).

All planners implement the same ``plan()`` / ``fix()`` interface, so the orchestrator
in ``copilot.py`` is backend-agnostic.
"""
from __future__ import annotations

from typing import Protocol

from .config import settings
from .exceptions import PlannerError
from .guardrails import NO_QUERY
from .logging_config import get_logger
from .prompts import FIX_PROMPT, SQL_PROMPT

log = get_logger(__name__)


class Planner(Protocol):
    def plan(self, schema: str, question: str) -> str: ...
    def fix(self, schema: str, question: str, sql: str, error: str) -> str: ...


class MockPlanner:
    """Deterministic stand-in for an LLM, matched to the demo schema.

    Deliberately imperfect on two questions so the offline pipeline still exercises
    the interesting paths:
      * a 'hometown' question -> wrong column, recovered by ``fix`` (self-correction);
      * a 'top N cities' question -> missing ORDER BY, i.e. right rows/wrong order,
        which ``fix`` does *not* repair (so eval reports a realistic partial lift).
    """

    def plan(self, schema: str, question: str) -> str:
        q = question.lower()

        # --- unsafe writes -> exercises the guardrail (status: blocked) ---------
        if any(w in q for w in ("delete", "drop", "truncate", "wipe", "remove all")):
            return "DELETE FROM grades"

        # --- wrong column on purpose -> exercises self-correction ---------------
        if "hometown" in q:
            return ("SELECT s.hometown, AVG(g.score) AS avg_score "
                    "FROM students s JOIN grades g ON s.id = g.student_id "
                    "GROUP BY s.hometown")

        avg = ("average" in q) or ("avg" in q) or ("mean" in q)

        # --- top-N cities by average: missing ORDER BY (checked before generic) -
        if ("top" in q) and ("city" in q or "cities" in q) and avg:
            return ("SELECT s.city, ROUND(AVG(g.score), 1) AS avg_score "
                    "FROM students s JOIN grades g ON s.id = g.student_id "
                    "GROUP BY s.city LIMIT 3")

        if avg and "city" in q:
            return ("SELECT s.city, ROUND(AVG(g.score), 1) AS avg_score "
                    "FROM students s JOIN grades g ON s.id = g.student_id "
                    "GROUP BY s.city ORDER BY avg_score DESC")

        if avg and "department" in q:
            return ("SELECT sub.department, ROUND(AVG(g.score), 1) AS avg_score "
                    "FROM grades g JOIN subjects sub ON sub.id = g.subject_id "
                    "GROUP BY sub.department ORDER BY avg_score DESC")

        if ("top" in q or "highest" in q or "best" in q) and "subject" in q:
            return ("SELECT sub.subject_name, MAX(g.score) AS top_score "
                    "FROM grades g JOIN subjects sub ON sub.id = g.subject_id "
                    "GROUP BY sub.subject_name")

        if ("above 90" in q) or ("over 90" in q) or ("more than 90" in q):
            return ("SELECT DISTINCT s.name FROM students s "
                    "JOIN grades g ON s.id = g.student_id WHERE g.score > 90")

        if "science" in q:
            return ("SELECT DISTINCT s.name FROM students s "
                    "JOIN grades g ON s.id = g.student_id "
                    "JOIN subjects sub ON sub.id = g.subject_id "
                    "WHERE sub.department = 'Science'")

        if ("grade" in q) and ("distribution" in q or "each grade" in q or "how many" in q):
            return "SELECT grade, COUNT(*) AS n FROM grades GROUP BY grade ORDER BY grade"

        # Grouped per-city count — must be checked before the plain total count.
        counting = ("how many" in q) or ("number of" in q) or ("count" in q)
        grouped = ("each" in q) or ("per" in q) or ("by " in q)
        if counting and "city" in q and grouped:
            return "SELECT city, COUNT(*) AS n FROM students GROUP BY city ORDER BY n DESC"

        if "how many" in q and "subject" in q:
            return "SELECT COUNT(*) AS subject_count FROM subjects"

        if "how many" in q and "student" in q:
            return "SELECT COUNT(*) AS student_count FROM students"

        if "list" in q or "all students" in q:
            return "SELECT id, name, year, city FROM students ORDER BY name"

        # --- unanswerable from this schema -> exercises refusal -----------------
        return NO_QUERY

    def fix(self, schema: str, question: str, sql: str, error: str) -> str:
        if "hometown" in sql.lower():
            return sql.replace("hometown", "city")
        return sql  # no improvement -> retries exhaust (status: error)


class _LangchainPlanner:
    """Wraps Ollama or Gemini behind the same plan()/fix() interface."""

    def __init__(self) -> None:
        try:
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate

            if settings.llm_mode == "gemini":
                from langchain_google_genai import ChatGoogleGenerativeAI

                llm = ChatGoogleGenerativeAI(
                    model=settings.gemini_model,
                    google_api_key=settings.google_api_key,
                    temperature=0,
                )
            else:
                from langchain_ollama import ChatOllama

                llm = ChatOllama(model=settings.ollama_model, temperature=0)
        except ImportError as exc:  # pragma: no cover - depends on optional extras
            raise PlannerError(
                f"LLM_MODE={settings.llm_mode} needs the 'llm' extra: "
                f"pip install 'ai-data-copilot[llm]' ({exc})"
            ) from exc

        self._sql = ChatPromptTemplate.from_template(SQL_PROMPT) | llm | StrOutputParser()
        self._fix = ChatPromptTemplate.from_template(FIX_PROMPT) | llm | StrOutputParser()

    def plan(self, schema: str, question: str) -> str:
        return self._sql.invoke({"schema": schema, "question": question})

    def fix(self, schema: str, question: str, sql: str, error: str) -> str:
        return self._fix.invoke(
            {"schema": schema, "question": question, "sql": sql, "error": error}
        )


def get_planner() -> Planner:
    mode = settings.llm_mode
    log.info("initialising planner", extra={"llm_mode": mode})
    if mode in ("ollama", "gemini"):
        return _LangchainPlanner()
    return MockPlanner()
