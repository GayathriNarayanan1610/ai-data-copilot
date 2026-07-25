from __future__ import annotations

from datacopilot.data import GRADES, STUDENTS, SUBJECTS, build_dataset, grade_for


def test_dataset_is_deterministic():
    a = build_dataset()
    b = build_dataset()
    assert a == b


def test_dataset_sizes():
    assert len(STUDENTS) == 60
    assert len(SUBJECTS) == 12
    assert len(GRADES) > 200


def test_grades_reference_valid_ids():
    student_ids = {s[0] for s in STUDENTS}
    subject_ids = {s[0] for s in SUBJECTS}
    for _gid, sid, subid, score, letter in GRADES:
        assert sid in student_ids
        assert subid in subject_ids
        assert 0 <= score <= 100
        assert letter == grade_for(score)


def test_grade_boundaries():
    assert grade_for(90) == "A"
    assert grade_for(89) == "B"
    assert grade_for(59) == "F"
