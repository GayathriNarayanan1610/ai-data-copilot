"""FastAPI surface for the copilot."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from .config import settings
from .copilot import Copilot
from .seed import create

_copilot: Copilot | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not os.path.exists(settings.db_path):
        create(settings.db_path)
    global _copilot
    _copilot = Copilot()
    yield


app = FastAPI(title="AI Data Copilot", version="1.0.0", lifespan=lifespan)


class QueryRequest(BaseModel):
    question: str


@app.post("/query")
async def query(req: QueryRequest) -> dict:
    return _copilot.ask(req.question).to_dict()


@app.get("/schema")
async def schema() -> dict:
    return {"schema": _copilot.schema}


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
