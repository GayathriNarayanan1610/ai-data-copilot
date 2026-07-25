# AI Data Copilot

Ask questions about your data in plain English; get back **guarded, self-correcting
SQL** and the results. Ships with a deterministic offline mode (no API key, no
network) and an **execution-accuracy evaluation harness**, so correctness is measured,
not assumed.

```
"What is the average score by city?"
  -> SELECT s.city, ROUND(AVG(g.score),1) FROM students s
     JOIN grades g ON s.id = g.student_id GROUP BY s.city ORDER BY 2 DESC
  -> [{"city": "Kolkata", "avg_score": 72.5}, ...]
```

## Why it's built this way

Turning natural language into SQL is easy to demo and hard to trust. Three properties
carry this from toy to production-shaped:

1. **Guardrails, in depth.** Generated SQL is never assumed safe. It passes a text
   guardrail (SELECT/WITH only; no writes, DDL, stacked statements or comment
   injection), then runs on a connection opened `mode=ro`, behind a SQLite
   *authorizer* that denies every write action at the driver level. Three independent
   layers, so no single bug is fatal.
2. **Self-correction.** When a query fails, the error is fed back to the planner for a
   bounded number of retries before giving up — a real accuracy lift, quantified by
   the eval harness.
3. **Grounding over hallucination.** If a question can't be answered from the schema,
   the copilot *refuses* instead of inventing tables.

Every request ends in exactly one of four honest outcomes: `success`, `refused`
(off-topic / ungroundable), `blocked` (unsafe SQL, never executed), or `error` (failed
after retries).

## Architecture

```
                    ┌──────────────┐
  question ───────▶ │   Copilot    │  orchestrates the loop below
                    └──────┬───────┘
                           │ 1. plan()          llm.py  (mock | ollama | gemini)
                           ▼
                    ┌──────────────┐
                    │  clean_sql   │  strip fences/prose/comments      guardrails.py
                    │ is_safe_select│  reject writes / stacked / DDL
                    └──────┬───────┘
                           │ 2. run (read-only)                        db.py
                           ▼                     mode=ro + authorizer + row cap
                    ┌──────────────┐
                    │  run_query   │──ok──▶ success
                    └──────┬───────┘
                           │ fail
                           ▼ 3. fix() + retry (bounded)                copilot.py
                    self-correction loop ──exhausted──▶ error
```

Layers are dependency-light and unit-testable: guardrails are pure functions; the DB
layer has no LLM knowledge; the planner is swappable behind a `Planner` protocol.

## Data

A deterministic generator (`datacopilot/data.py`, fixed seed) builds a dataset large
enough for joins and aggregations to be meaningful:

| table    | rows | columns                                   |
|----------|------|-------------------------------------------|
| students |  60  | id, name, year, city (7 cities)           |
| subjects |  12  | id, subject_name, department (4 depts)    |
| grades   | ~300 | id, student_id, subject_id, score, grade  |

Same seed ⇒ same rows, which is what keeps the evaluation reproducible.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,ui]"        # add ,llm for real model backends

datacopilot seed                   # create + populate data/copilot.db
datacopilot ask "average score by city"

streamlit run ui.py                # Streamlit UI on http://localhost:8501
datacopilot serve                  # or the FastAPI service on http://127.0.0.1:8000/docs
```

Or with Docker (Streamlit UI on 8501, matching the deployment):

```bash
docker compose up --build          # mock mode by default
LLM_MODE=gemini GOOGLE_API_KEY=... docker compose up --build   # to match prod
```

## Two front ends, one backend

The copilot logic lives in the `datacopilot` package; both surfaces are thin clients
over `Copilot().ask(question)`:

- **`ui.py`** — Streamlit app (schema sidebar, question box, per-status rendering,
  self-correction + latency indicators). This is what the Docker image runs.
- **`datacopilot/api.py`** — FastAPI service (`/query`, `/schema`, `/healthz`,
  `/readyz`) with request-id + latency middleware and error handlers.

## API

| method | path       | purpose                                  |
|--------|------------|------------------------------------------|
| POST   | `/query`   | `{"question": "..."}` → result payload   |
| GET    | `/schema`  | the schema shown to the model            |
| GET    | `/healthz` | liveness                                 |
| GET    | `/readyz`  | readiness (copilot + DB usable)          |

```bash
curl -s localhost:8000/query -H 'content-type: application/json' \
  -d '{"question":"how many students are in each city?"}' | jq
```

Every response carries an `x-request-id` and `x-response-time-ms` header for tracing.

## Model backends

Offline by default (`LLM_MODE=mock`, a deterministic keyword planner) so the app, tests
and CI run anywhere. Switch to a real model via environment:

```bash
LLM_MODE=ollama  OLLAMA_MODEL=llama3            # local, via Ollama
LLM_MODE=gemini  GOOGLE_API_KEY=...             # Google Gemini
```

Both use the same strict, schema-grounded prompt (`prompts.py`) and go through the same
guardrails and self-correction loop.

## Evaluation

```bash
python eval/run_eval.py
```

Runs the real copilot over a golden set (`eval/golden.jsonl`) and reports **execution
accuracy** (result-set comparison, not string-matching), per category, plus valid-SQL
rate, refusal correctness, and the measured lift from the self-correction loop. Sample:

```
Execution accuracy : 91.7%  (11/12 answerable)
Refusal correctness: 100.0% (4 should-refuse)
Self-correction    : 83.3% -> 91.7%  (+8.4 points)
```

Result-set comparison is order-insensitive unless a case is marked `order_matters`
(then row order is part of correctness). Extend coverage by adding lines to the golden
set; each is `{question, reference_sql, category}` with optional `expect_refusal`.

## Development

```bash
make check     # lint (ruff) + types (mypy) + tests (pytest, with coverage)
make eval      # evaluation harness
make format    # auto-fix + format
```

CI (`.github/workflows/ci.yml`) runs lint, type-check, tests and the eval on Python
3.10–3.12, all in offline mock mode.

## Layout

```
src/datacopilot/
  config.py          validated settings (pydantic-settings)
  logging_config.py  structured logging (JSON option), to stderr
  exceptions.py      typed error hierarchy
  guardrails.py      pure SQL safety functions
  db.py              read-only execution (mode=ro + authorizer + row cap)
  llm.py             planners: mock / ollama / gemini behind one protocol
  prompts.py         schema-grounded prompt templates
  copilot.py         the orchestration loop
  api.py             FastAPI surface (middleware, error handlers, probes)
  data.py / seed.py  deterministic dataset + DDL/load
  __main__.py        CLI: seed | ask | serve | info
ui.py                Streamlit front end (what the Docker image runs)
tests/               unit + API tests
eval/                golden set + execution-accuracy harness
```

## License

MIT — see [LICENSE](LICENSE).
