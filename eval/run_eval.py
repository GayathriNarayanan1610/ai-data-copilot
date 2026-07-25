"""Execution-accuracy evaluation for the AI Data Copilot.

Runs the real ``Copilot`` (mock planner by default, so it needs no network) over the
golden set and reports execution accuracy overall + per category, valid-SQL rate,
refusal correctness, and the lift from the self-correction loop. Determinism is
checked by re-running the baseline.

    python eval/run_eval.py
"""
from __future__ import annotations

import os
import sys
import tempfile

# Make the package importable whether run from repo root or the eval/ dir.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copilot_eval import (  # noqa: E402
    read_jsonl,
    render_report,
    results_match,
    self_correction_lift,
    summarize,
)
from datacopilot.config import settings  # noqa: E402
from datacopilot.copilot import Copilot  # noqa: E402
from datacopilot.db import run_query  # noqa: E402
from datacopilot.seed import create  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden.jsonl")


def _rows_to_tuples(rows, columns):
    return [tuple(row[c] for c in columns) for row in rows]


def _order_matters(case):
    if "order_matters" in case:
        return bool(case["order_matters"])
    return "order by" in (case.get("reference_sql") or "").lower()


def evaluate(copilot: Copilot, db_path: str):
    """Run the copilot over the golden set and return per-case result dicts.

    Maps the copilot's status to the harness's scoring model:
        success -> compare result sets against the reference
        refused/blocked -> a decline (correct iff the case expected one)
        error   -> invalid / failed
    """
    results = []
    for case in read_jsonl(GOLDEN):
        expect_refusal = bool(case.get("expect_refusal", False))
        rec = {
            "id": case["id"],
            "question": case["question"],
            "category": case["category"],
            "expect_refusal": expect_refusal,
            "generated_sql": None,
            "refused": False,
            "valid": None,
            "correct": False,
        }

        res = copilot.ask(case["question"])

        if res.status in ("refused", "blocked"):
            rec["refused"] = True
            rec["correct"] = expect_refusal
        elif res.status == "error":
            rec["valid"] = False
            rec["error"] = res.error
            rec["correct"] = False
        else:  # success
            rec["generated_sql"] = res.sql
            rec["valid"] = True
            if expect_refusal:
                rec["correct"] = False  # answered something it should have declined
            else:
                gen = _rows_to_tuples(res.rows, res.columns)
                ref_df = run_query(case["reference_sql"], db_path, settings.row_limit)
                ref = [tuple(r) for r in ref_df.itertuples(index=False, name=None)]
                rec["correct"] = results_match(gen, ref, order_matters=_order_matters(case))

        results.append(rec)
    return results


def main() -> int:
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "eval.db")
    create(db_path)
    copilot = Copilot(db_path)

    original_retries = settings.max_retries

    # Baseline: self-correction disabled.
    settings.max_retries = 0
    results_off = evaluate(copilot, db_path)
    summary_off = summarize(results_off)

    # Full: self-correction enabled.
    settings.max_retries = max(1, original_retries)
    results_on = evaluate(copilot, db_path)
    summary_on = summarize(results_on)

    lift = self_correction_lift(summary_off, summary_on, results_off, results_on)
    print(render_report(results_on, summary_on, lift=lift,
                        title="AI Data Copilot — Execution-Accuracy Evaluation"))

    # Determinism check.
    settings.max_retries = max(1, original_retries)
    again = summarize(evaluate(copilot, db_path))
    same = again == summary_on
    print("DETERMINISM CHECK")
    print("-" * 64)
    verdict = "identical numbers (deterministic)" if same else "NUMBERS DRIFTED"
    print(f"  Re-ran full eval: {verdict}")
    print()

    settings.max_retries = original_retries
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
