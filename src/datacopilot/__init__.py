"""AI Data Copilot — natural-language-to-SQL over your database.

Public surface:
    Copilot, Result   — the orchestrator and its typed result
    create            — (re)seed the demo database
    settings          — validated configuration
"""
from __future__ import annotations

from .config import settings
from .copilot import Copilot, Result
from .seed import create

__version__ = "1.0.0"
__all__ = ["Copilot", "Result", "create", "settings", "__version__"]
