from __future__ import annotations


def test_success_path(copilot):
    result = copilot.ask("How many students are there?")
    assert result.status == "success"
    assert result.rows[0]["student_count"] == 60
    assert result.attempts == 1
    assert result.latency_ms >= 0


def test_refusal_on_offtopic(copilot):
    result = copilot.ask("What is the capital of France?")
    assert result.status == "refused"
    assert not result.rows


def test_blocked_on_write(copilot):
    result = copilot.ask("Delete all grades")
    assert result.status == "blocked"
    assert result.error


def test_empty_question_is_refused(copilot):
    result = copilot.ask("   ")
    assert result.status == "refused"


def test_self_correction_recovers(copilot):
    # 'hometown' is a non-existent column; the fix() step rewrites it to 'city'.
    result = copilot.ask("What is the average score by hometown?")
    assert result.status == "success"
    assert result.attempts == 2
    assert "city" in result.sql.lower()
    assert "hometown" not in result.sql.lower()


def test_result_serialisation(copilot):
    payload = copilot.ask("How many students are there?").to_dict()
    for key in ("question", "status", "sql", "rows", "row_count", "latency_ms", "mode"):
        assert key in payload
