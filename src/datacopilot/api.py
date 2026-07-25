"""FastAPI surface for the copilot.

Adds, over a bare router: request-id + latency middleware, CORS, typed request/
response models, a readiness probe distinct from liveness, and a global exception
handler so unexpected failures return a structured 500 with a correlation id rather
than a stack trace.
"""
from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import settings
from .copilot import Copilot
from .exceptions import CopilotError
from .logging_config import configure_logging, get_logger
from .seed import create

configure_logging(settings.log_level, settings.log_json)
log = get_logger(__name__)

_copilot: Copilot | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not os.path.exists(settings.db_path):
        log.info("database missing, seeding", extra={"db_path": settings.db_path})
        create(settings.db_path)
    global _copilot
    _copilot = Copilot()
    log.info("copilot ready", extra={"llm_mode": settings.llm_mode})
    yield


app = FastAPI(
    title="AI Data Copilot",
    version="1.0.0",
    summary="Natural-language questions -> guarded, self-correcting SQL over your data.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000.0
    response.headers["x-request-id"] = request_id
    response.headers["x-response-time-ms"] = f"{elapsed:.1f}"
    log.info("http", extra={"request_id": request_id, "path": request.url.path,
                            "status_code": response.status_code, "latency_ms": round(elapsed, 1)})
    return response


@app.exception_handler(CopilotError)
async def copilot_error_handler(request: Request, exc: CopilotError):
    return JSONResponse(status_code=400, content={"error": str(exc), "type": type(exc).__name__})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    log.exception("unhandled error", extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000,
                          examples=["What is the average score by city?"])


class QueryResponse(BaseModel):
    question: str
    status: str
    sql: str = ""
    columns: list[str] = []
    rows: list[dict] = []
    error: str = ""
    attempts: int = 0
    latency_ms: float = 0.0
    mode: str = ""
    row_count: int = 0


def _get_copilot() -> Copilot:
    if _copilot is None:  # pragma: no cover - lifespan guarantees this
        raise CopilotError("Copilot is not initialised yet.")
    return _copilot


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> dict:
    return _get_copilot().ask(req.question).to_dict()


@app.get("/schema")
async def schema() -> dict:
    return {"schema": _get_copilot().schema}


@app.get("/healthz")
async def healthz() -> dict:
    """Liveness: the process is up."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict:
    """Readiness: the copilot and database are usable."""
    ready = _copilot is not None
    return {"status": "ready" if ready else "starting", "llm_mode": settings.llm_mode}
