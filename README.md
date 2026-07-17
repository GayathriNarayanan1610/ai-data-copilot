# AI Data Copilot

**Ask a database questions in plain English and get safe, grounded, cited-by-SQL answers, not guesses.**

The people who most need answers from data usually can't get them without waiting on
an analyst. This copilot closes that gap: a non-technical user types a question, and
it generates the SQL, **validates it**, runs it read-only, and returns a results
table — refusing safely when a question is unsafe or unanswerable instead of
hallucinating a query.

This is the production-hardened version of my original text-to-SQL prototype. The
prototype proved the idea (LLM writes SQL, app runs it); this version adds the parts
that make it trustworthy: guardrails, self-correction, grounding, a real multi-table
schema, and both a UI and an API.

Deployed cloud url  https://copilot.jollyglacier-1f65987e.uksouth.azurecontainerapps.io/

## What it does

1. **Generates SQL** from a natural-language question, using the live database schema.
2. **Cleans** the model's output (strips markdown fences / stray prose).
3. **Guards** it — only read-only `SELECT`/`WITH` runs; writes, stacked statements, and
   schema changes are blocked and never executed.
4. **Self-corrects** — if the SQL errors, the error is fed back to the model to fix and
   retry (up to a limit).
5. **Grounds** — if the question can't be answered from the schema, it refuses rather
   than invent an answer.
6. **Returns a results table**, plus the SQL it ran and how many attempts it took.

## Demo

<img width="1192" height="743" alt="image" src="https://github.com/user-attachments/assets/0cd5f684-8a55-4d48-9aa3-74fe6df85d29" />

<img width="952" height="703" alt="image" src="https://github.com/user-attachments/assets/e27702b2-e60e-421a-8cdf-4677b850760b" />

<img width="927" height="537" alt="image" src="https://github.com/user-attachments/assets/cc3608bc-ae80-4022-bf3d-1fa888f1ed70" />

<img width="998" height="525" alt="image" src="https://github.com/user-attachments/assets/1438649a-056c-4238-b63a-804c52f15ac6" />


## Why this version matters (what changed from the prototype)

| Capability | Prototype | This version |
|---|---|---|
| Safety | ran any SQL the model produced | **read-only guardrail** + read-only DB connection |
| Model output handling | `.strip()` only | **fence/prose cleaning** so real models don't break it |
| Failure handling | showed the error | **self-correction retry loop** |
| Schema | one flat table | **3 tables** (students, subjects, grades) → real joins & aggregations |
| Hallucination | would query anyway | **grounding refusal** (`NO_QUERY`) |
| Interface | Streamlit only | **Streamlit UI + FastAPI endpoint** |

## It runs offline (mock mode)

By default `LLM_MODE=mock` uses a deterministic planner — no Ollama, no API key — so
the whole pipeline (and its tests) runs anywhere. Real models plug in unchanged:
- `LLM_MODE=ollama` — local Llama 3 (run `ollama pull llama3` first).
- `LLM_MODE=gemini` — Google Gemini (set `GOOGLE_API_KEY`).

The guardrails, cleaning, retry, grounding, and SQL all work identically across modes;
only the planner swaps.

## Run it

```bash
pip install -r requirements.txt
python -m app.seed                 # build the 3-table demo database
streamlit run ui.py                # the chat UI
uvicorn app.api:app --reload       # the API: POST /query, GET /schema
pytest -q                          # 11 tests, no model or network needed
```

```bash
curl -s localhost:8000/query -H 'content-type: application/json' \
  -d '{"question":"What is the average score per city?"}'
```

## What you'll see (real output, mock mode)

```
Q: What is the average score per city?
   status=success
   sql=SELECT s.city, ROUND(AVG(g.score),1) AS avg_score FROM students s
       JOIN grades g ON s.id = g.student_id GROUP BY s.city ORDER BY avg_score DESC
   rows=[{'city':'Bangalore','avg_score':88.8}, {'city':'Chennai','avg_score':78.0}, ...]

Q: What is the average score by hometown?   (there is no 'hometown' column)
   status=success  attempts=2          <- failed once, self-corrected to 'city'

Q: Delete all grades
   status=blocked                      <- guardrail; nothing ran

Q: What will the weather be tomorrow?
   status=refused                      <- not answerable from the schema
```

## How it's built

```
app/
  config.py      modes (mock|ollama|gemini), db path, retry limit, row cap
  seed.py        creates the 3-table demo DB
  db.py          schema introspection + READ-ONLY query execution -> DataFrame
  guardrails.py  clean_sql + is_safe_select  (pure, unit-tested)
  prompts.py     SQL + fix prompt templates
  llm.py         MockPlanner + Ollama/Gemini wrappers (same interface)
  copilot.py     orchestration: clean -> refuse -> guard -> run -> self-correct
  api.py         FastAPI: /query, /schema, /healthz
ui.py            Streamlit chat UI (SQL + results table + attempts)
tests/           guardrail unit tests + end-to-end copilot tests
```

The four outcomes are explicit — **success / refused / blocked / error** — so the UI
and API always say *why*, which is the difference between a demo and a tool people trust.

## Tests

```bash
pytest -q     # 11 passed
```
Unit tests cover SQL cleaning and the safety rules (SELECT allowed; DELETE/DROP/UPDATE
and stacked statements blocked). End-to-end tests cover an answerable question, a
multi-table aggregation, an unsafe query (blocked), an off-topic question (refused),
and the self-correction path (fails once, then succeeds).

## Honest notes

- **Mock mode** is a deterministic stand-in so the project runs and tests without a
  model. With a real model, the guardrails and grounding matter more, not less — that's
  the point of them.
- **Ollama vs Gemini:** Ollama keeps everything local/offline; Gemini lets a reviewer
  run it without installing a model (needs a key). Pick one in your CV and keep it
  consistent with what you demo.

## What I'd add for production

- A retrieval step over the schema (embeddings) so it scales past a handful of tables.
- Query cost/row estimation before execution; per-user row limits.
- An eval set of question→expected-SQL pairs to measure accuracy on every change.
- Logging of every question, generated SQL, and outcome for audit.
