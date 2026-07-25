# syntax=docker/dockerfile:1
#
# Runs the Streamlit UI (ui.py) on $PORT (default 8501), matching the existing
# deployment. The FastAPI service is still available in-image via
# `uvicorn datacopilot.api:app` or `datacopilot serve` if you prefer an API.

# ---- builder: install the package (+ ui, llm extras) into a venv ----
FROM python:3.12-slim AS builder
WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install ".[ui,llm]"

# ---- runtime: minimal, non-root ----
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    LLM_MODE=mock \
    DB_PATH=/app/data/copilot.db \
    PORT=8501

COPY --from=builder /opt/venv /opt/venv
COPY ui.py ./

RUN useradd --create-home appuser \
    && mkdir -p /app/data && chown -R appuser /app/data
USER appuser
VOLUME ["/app/data"]
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','8501'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/_stcore/health').status==200 else 1)"

CMD ["sh", "-c", "streamlit run ui.py --server.port=${PORT} --server.address=0.0.0.0 --server.enableCORS=false --server.enableXsrfProtection=false --server.headless=true"]
