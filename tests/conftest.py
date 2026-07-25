from __future__ import annotations

import pytest

from datacopilot.copilot import Copilot
from datacopilot.seed import create


@pytest.fixture(scope="session")
def db_path(tmp_path_factory) -> str:
    path = tmp_path_factory.mktemp("db") / "test.db"
    create(str(path))
    return str(path)


@pytest.fixture()
def copilot(db_path: str) -> Copilot:
    return Copilot(db_path=db_path)
