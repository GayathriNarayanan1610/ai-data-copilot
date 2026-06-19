"""Prompt templates (plain strings; the real LLM wrappers format them)."""

SQL_PROMPT = """You are a careful SQLite expert. Using ONLY the schema below, write a
single SQL query that answers the user's question.

Rules:
- Use only the tables and columns in the schema.
- Return ONLY the SQL query — no explanation, no markdown.
- Use a read-only SELECT. Never modify data.
- If the question cannot be answered from this schema, return exactly: NO_QUERY

Schema:
{schema}

Question: {question}
SQL:"""

FIX_PROMPT = """The SQL you wrote failed to execute. Fix it using ONLY the schema.
Return ONLY the corrected SQL query (no explanation, no markdown).

Schema:
{schema}

Question: {question}
Your SQL: {sql}
Error: {error}
Corrected SQL:"""
