"""The planner: turn a question into SQL, and fix SQL given an error.

`mock`  : deterministic keyword router — no model, no network. Enough to run and
          test the full pipeline offline, including the unsafe-query, off-topic, and
          self-correction paths.
`ollama`: local Llama 3 via Ollama.
`gemini`: Google Gemini (needs GOOGLE_API_KEY).
"""
from __future__ import annotations

from .config import settings
from .guardrails import NO_QUERY
from .prompts import FIX_PROMPT, SQL_PROMPT


class MockPlanner:
    """Deterministic stand-in for an LLM, matched to the demo schema."""

    def plan(self, schema: str, question: str) -> str:
        q = question.lower()
        if "hometown" in q:
            # wrong column on purpose -> exercises self-correction
            return ("SELECT s.hometown, AVG(g.score) AS avg_score "
                    "FROM students s JOIN grades g ON s.id = g.student_id GROUP BY s.hometown")
        if ("average" in q or "avg" in q or "mean" in q) and "city" in q:
            return ("SELECT s.city, ROUND(AVG(g.score), 1) AS avg_score "
                    "FROM students s JOIN grades g ON s.id = g.student_id "
                    "GROUP BY s.city ORDER BY avg_score DESC")
        if ("top" in q or "highest" in q or "best" in q) and "subject" in q:
            return ("SELECT sub.subject_name, st.name, MAX(g.score) AS top_score "
                    "FROM grades g JOIN students st ON st.id = g.student_id "
                    "JOIN subjects sub ON sub.id = g.subject_id GROUP BY sub.subject_name")
        if "how many" in q and "student" in q:
            return "SELECT COUNT(*) AS student_count FROM students"
        if "list" in q or "all students" in q:
            return "SELECT id, name, year, city FROM students ORDER BY name"
        if any(w in q for w in ("delete", "drop", "remove all", "truncate", "wipe")):
            return "DELETE FROM grades"          # unsafe -> exercises the guardrail
        return NO_QUERY                          # unanswerable -> exercises refusal

    def fix(self, schema: str, question: str, sql: str, error: str) -> str:
        if "hometown" in sql.lower():
            return sql.replace("hometown", "city")
        return sql                               # no improvement -> retries exhaust


class _LangchainPlanner:
    """Wraps Ollama or Gemini behind the same plan()/fix() interface."""

    def __init__(self) -> None:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate

        if settings.llm_mode == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(model=settings.gemini_model,
                                         google_api_key=settings.google_api_key, temperature=0)
        else:
            from langchain_ollama import ChatOllama

            llm = ChatOllama(model=settings.ollama_model, temperature=0)

        self._sql = ChatPromptTemplate.from_template(SQL_PROMPT) | llm | StrOutputParser()
        self._fix = ChatPromptTemplate.from_template(FIX_PROMPT) | llm | StrOutputParser()

    def plan(self, schema: str, question: str) -> str:
        return self._sql.invoke({"schema": schema, "question": question})

    def fix(self, schema: str, question: str, sql: str, error: str) -> str:
        return self._fix.invoke({"schema": schema, "question": question, "sql": sql, "error": error})


def get_planner():
    if settings.llm_mode in ("ollama", "gemini"):
        return _LangchainPlanner()
    return MockPlanner()
