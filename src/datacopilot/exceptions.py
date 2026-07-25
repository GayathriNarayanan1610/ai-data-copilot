"""Typed exceptions.

A small hierarchy lets the API layer map failures to the right HTTP status and lets
tests assert on specific error types instead of matching on strings.
"""
from __future__ import annotations


class CopilotError(Exception):
    """Base class for all copilot errors."""


class ConfigurationError(CopilotError):
    """Invalid or missing configuration."""


class SchemaError(CopilotError):
    """The database schema could not be read."""


class UnsafeQueryError(CopilotError):
    """Generated SQL was rejected by the guardrails (write / stacked / etc.)."""


class QueryExecutionError(CopilotError):
    """SQL failed to execute, even after self-correction retries."""


class PlannerError(CopilotError):
    """The planner (LLM backend) failed to produce a response."""
