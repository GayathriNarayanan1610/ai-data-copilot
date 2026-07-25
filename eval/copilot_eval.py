"""
copilot_eval.py — execution-accuracy evaluation for an NL->SQL data copilot.

This is the reusable core. It knows nothing about your database or your model.
You supply two callables:

    ask_copilot(question: str) -> str | None
        Your copilot's NL->SQL. Return the generated SQL string, OR return None
        (or a string handled by `is_refusal`) when the copilot refuses.

    run_sql(sql: str) -> list[tuple]
        Execute SQL READ-ONLY against a *copy* of your DB and return the rows.
        Never point this at production.

Then call evaluate_copilot(...), summarize(...) and render_report(...).
See run_demo.py for a complete, self-contained example.
"""

import json


# --------------------------------------------------------------------------
# A2 — result-set comparison
# --------------------------------------------------------------------------
def results_match(rows_a, rows_b, order_matters=False):
    """Order-independent (by default) result-set equality.

    Cells are stringified so that 5 == '5' and 5.0 == '5.0'-style type/format
    noise doesn't cause spurious mismatches. Set order_matters=True for
    questions that request a specific ordering (top N, sorted, first/last...).
    """
    def norm(rows):
        return [tuple("NULL" if c is None else str(c) for c in row) for row in rows]

    a, b = norm(rows_a), norm(rows_b)
    if order_matters:
        return a == b
    return sorted(a) == sorted(b)


def default_is_refusal(gen_sql):
    """Default refusal detector. Treats None, empty output, or a string that
    doesn't look like a SELECT as a refusal. Adapt this to however YOUR copilot
    signals 'I won't/can't answer' (e.g. a sentinel string, a flag, an empty
    result). The demo copilot simply returns None on refusal."""
    if gen_sql is None:
        return True
    s = gen_sql.strip().lower()
    if not s:
        return True
    return s.startswith(("refuse", "i can't", "i cannot"))


def _order_matters_for(case):
    """Decide whether ordering matters for a case.

    Prefer an explicit `order_matters` field on the golden case. Otherwise fall
    back to inspecting the reference SQL for an ORDER BY. (This is more robust
    than scanning the question text for the word 'order', which false-positives
    on phrases like 'order amount'.)"""
    if "order_matters" in case:
        return bool(case["order_matters"])
    ref = (case.get("reference_sql") or "").lower()
    return "order by" in ref


# --------------------------------------------------------------------------
# A4 — the runner
# --------------------------------------------------------------------------
def read_jsonl(path):
    cases = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def evaluate_copilot(golden_path, ask_copilot, run_sql, is_refusal=default_is_refusal):
    """Run every golden case and return a list of per-case result dicts.

    Each result carries: id, question, category, expect_refusal, refused,
    generated_sql, valid, correct, and (on failure) error.
    """
    results = []
    for case in read_jsonl(golden_path):
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
        try:
            gen_sql = ask_copilot(case["question"])
            refused = is_refusal(gen_sql)
            rec["refused"] = refused

            if refused:
                # Correct iff the case was supposed to be refused.
                rec["correct"] = expect_refusal
                results.append(rec)
                continue

            rec["generated_sql"] = gen_sql

            if expect_refusal:
                # It produced SQL for something it should have refused.
                # Check whether that SQL is even valid, but it's wrong regardless.
                try:
                    run_sql(gen_sql)
                    rec["valid"] = True
                except Exception as e:
                    rec["valid"] = False
                    rec["error"] = str(e)
                rec["correct"] = False
                results.append(rec)
                continue

            # Answerable question with generated SQL: compare result sets.
            gen_rows = run_sql(gen_sql)
            ref_rows = run_sql(case["reference_sql"])
            rec["valid"] = True
            rec["correct"] = results_match(
                gen_rows, ref_rows, order_matters=_order_matters_for(case)
            )
            results.append(rec)

        except Exception as e:
            # Generated SQL failed to parse/run (or reference errored).
            rec["valid"] = False
            rec["correct"] = False
            rec["error"] = str(e)
            results.append(rec)

    return results


# --------------------------------------------------------------------------
# A3 — metrics
# --------------------------------------------------------------------------
def _pct(n, d):
    return None if d == 0 else round(100.0 * n / d, 1)


def summarize(results):
    """Aggregate per-case results into headline + per-category metrics."""
    answerable = [r for r in results if not r["expect_refusal"]]
    refusal_cases = [r for r in results if r["expect_refusal"]]

    # Execution accuracy over answerable questions. A wrongly-refused
    # answerable question counts as incorrect (it is).
    exec_correct = sum(1 for r in answerable if r["correct"])
    exec_acc = _pct(exec_correct, len(answerable))

    # Per-category execution accuracy (answerable categories only).
    per_cat = {}
    for r in answerable:
        d = per_cat.setdefault(r["category"], {"correct": 0, "total": 0})
        d["total"] += 1
        d["correct"] += 1 if r["correct"] else 0
    for _cat, d in per_cat.items():
        d["accuracy"] = _pct(d["correct"], d["total"])

    # Valid-SQL rate over queries the copilot actually generated (answerable,
    # not refused). Separates "broke" (invalid) from "wrong answer" (invalid=False
    # is not the same as correct).
    generated = [r for r in answerable if not r["refused"]]
    valid = sum(1 for r in generated if r["valid"])
    valid_rate = _pct(valid, len(generated))

    # Refusal correctness: of the should-refuse cases, how many were refused.
    ref_ok = sum(1 for r in refusal_cases if r["refused"])
    refusal_correctness = _pct(ref_ok, len(refusal_cases))

    # False refusals: answerable questions the copilot wrongly refused.
    false_ref = sum(1 for r in answerable if r["refused"])
    false_refusal_rate = _pct(false_ref, len(answerable))

    return {
        "n_total": len(results),
        "n_answerable": len(answerable),
        "n_refusal_cases": len(refusal_cases),
        "execution_accuracy": exec_acc,
        "execution_correct": exec_correct,
        "per_category": per_cat,
        "valid_sql_rate": valid_rate,
        "n_generated": len(generated),
        "refusal_correctness": refusal_correctness,
        "false_refusal_rate": false_refusal_rate,
    }


def self_correction_lift(summary_off, summary_on, results_off, results_on):
    """Compare accuracy with and without the self-correction loop.

    Returns the delta in execution accuracy plus how many *initially failed*
    answerable questions were recovered once self-correction was enabled.
    """
    off_correct = {r["id"]: r["correct"] for r in results_off if not r["expect_refusal"]}
    on_correct = {r["id"]: r["correct"] for r in results_on if not r["expect_refusal"]}

    initially_failed = [qid for qid, ok in off_correct.items() if not ok]
    recovered = [qid for qid in initially_failed if on_correct.get(qid)]

    return {
        "accuracy_off": summary_off["execution_accuracy"],
        "accuracy_on": summary_on["execution_accuracy"],
        "lift_points": (
            None
            if summary_off["execution_accuracy"] is None
            else round(summary_on["execution_accuracy"] - summary_off["execution_accuracy"], 1)
        ),
        "initially_failed": initially_failed,
        "recovered": recovered,
        "recovered_pct": _pct(len(recovered), len(initially_failed)),
    }


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def render_report(results, summary, lift=None, title="NL->SQL Copilot Evaluation"):
    L = []
    L.append("=" * 64)
    L.append(title)
    L.append("=" * 64)
    L.append("")
    L.append(f"Cases: {summary['n_total']}  "
             f"(answerable: {summary['n_answerable']}, "
             f"should-refuse: {summary['n_refusal_cases']})")
    L.append("")
    L.append("HEADLINE")
    L.append("-" * 64)
    L.append(f"  Execution accuracy      : {summary['execution_accuracy']}%  "
             f"({summary['execution_correct']}/{summary['n_answerable']} answerable)")
    L.append(f"  Valid-SQL rate          : {summary['valid_sql_rate']}%  "
             f"({summary['n_generated']} generated)")
    L.append(f"  Refusal correctness     : {summary['refusal_correctness']}%  "
             f"({summary['n_refusal_cases']} should-refuse)")
    L.append(f"  False-refusal rate      : {summary['false_refusal_rate']}%  "
             f"(answerable wrongly refused)")
    L.append("")
    L.append("EXECUTION ACCURACY BY CATEGORY")
    L.append("-" * 64)
    for cat in sorted(summary["per_category"]):
        d = summary["per_category"][cat]
        bar = "#" * int((d["accuracy"] or 0) / 5)
        L.append(f"  {cat:<14} {d['accuracy']:>5}%  ({d['correct']}/{d['total']})  {bar}")
    L.append("")

    if lift is not None:
        L.append("SELF-CORRECTION LIFT")
        L.append("-" * 64)
        L.append(f"  Accuracy without loop   : {lift['accuracy_off']}%")
        L.append(f"  Accuracy with loop      : {lift['accuracy_on']}%")
        L.append(f"  Lift                    : +{lift['lift_points']} points")
        L.append(f"  Recovered               : {len(lift['recovered'])}/"
                 f"{len(lift['initially_failed'])} initially-failed "
                 f"({lift['recovered_pct']}%)")
        if lift["recovered"]:
            L.append(f"    fixed by loop         : {', '.join(lift['recovered'])}")
        still = [q for q in lift["initially_failed"] if q not in lift["recovered"]]
        if still:
            L.append(f"    still failing         : {', '.join(still)}")
        L.append("")

    L.append("PER-CASE DETAIL")
    L.append("-" * 64)
    for r in results:
        if r["expect_refusal"]:
            mark = "PASS" if r["correct"] else "FAIL"
            note = "refused (correct)" if r["refused"] else "ANSWERED should-refuse"
        elif r["refused"]:
            mark = "FAIL"
            note = "wrongly refused"
        elif not r["valid"]:
            mark = "FAIL"
            note = f"invalid SQL: {r.get('error', '')[:40]}"
        else:
            mark = "PASS" if r["correct"] else "FAIL"
            note = "match" if r["correct"] else "wrong result set"
        L.append(f"  [{mark}] {r['id']:<5} {r['category']:<20} {note}")
    L.append("")
    return "\n".join(L)
