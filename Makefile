.DEFAULT_GOAL := help
.PHONY: help install seed ask run test lint format typecheck eval docker check

PY ?= python

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install the package with dev + llm extras (editable)
	$(PY) -m pip install -e ".[dev,llm]"

seed: ## Create and populate the database
	$(PY) -m datacopilot seed

ask: ## Ask a question, e.g. make ask Q="average score by city"
	$(PY) -m datacopilot ask "$(Q)"

run: ## Run the API with autoreload
	$(PY) -m datacopilot serve --reload

ui: ## Run the Streamlit UI (port 8501)
	$(PY) -m streamlit run ui.py --server.port=8501

test: ## Run the test suite with coverage
	$(PY) -m pytest

lint: ## Lint with ruff
	$(PY) -m ruff check .

format: ## Auto-format / auto-fix with ruff
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .

typecheck: ## Static type check with mypy
	$(PY) -m mypy

eval: ## Run the execution-accuracy evaluation
	$(PY) eval/run_eval.py

check: lint typecheck test ## Run lint + types + tests (what CI runs)

docker: ## Build and run via docker compose
	docker compose up --build
