import pytest

from app.copilot import Copilot
from app.seed import create


@pytest.fixture
def copilot(tmp_path):
    db = str(tmp_path / "copilot.db")
    create(db)
    return Copilot(db_path=db)


def test_answerable_question_succeeds(copilot):
    res = copilot.ask("How many students are there?")
    assert res.status == "success"
    assert res.rows and res.rows[0]["student_count"] == 8


def test_multi_table_aggregation(copilot):
    res = copilot.ask("What is the average score per city?")
    assert res.status == "success"
    assert "city" in res.columns and "avg_score" in res.columns
    assert len(res.rows) >= 2          # multiple cities -> a real GROUP BY join


def test_unsafe_query_is_blocked(copilot):
    res = copilot.ask("delete all grades")
    assert res.status == "blocked"
    assert "students" not in res.columns   # nothing ran


def test_offtopic_is_refused(copilot):
    res = copilot.ask("What will the weather be tomorrow?")
    assert res.status == "refused"
    assert res.sql == ""


def test_self_correction_recovers(copilot):
    # 'hometown' is a wrong column; the planner's fix maps it to 'city'
    res = copilot.ask("What is the average score by hometown?")
    assert res.status == "success"
    assert res.attempts > 1            # it failed once, then self-corrected
