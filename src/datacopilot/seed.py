"""Create and populate the demo database (so joins + aggregations are real).

Schema:
    students(id, name, year, city)
    subjects(id, subject_name, department)
    grades(id, student_id, subject_id, score, grade)

The row data lives in ``data.py`` (deterministic, ~60 students / 12 subjects /
~300 grades). This module only owns DDL + bulk insert.
"""
from __future__ import annotations

import os
import sqlite3

from .data import GRADES, STUDENTS, SUBJECTS, summary
from .logging_config import get_logger

log = get_logger(__name__)

_DDL = """
DROP TABLE IF EXISTS grades;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS subjects;
CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, year INTEGER, city TEXT);
CREATE TABLE subjects (id INTEGER PRIMARY KEY, subject_name TEXT, department TEXT);
CREATE TABLE grades   (id INTEGER PRIMARY KEY, student_id INTEGER, subject_id INTEGER,
                       score INTEGER, grade TEXT,
                       FOREIGN KEY (student_id) REFERENCES students(id),
                       FOREIGN KEY (subject_id) REFERENCES subjects(id));
"""


def create(db_path: str) -> None:
    """(Re)create the database at ``db_path`` and populate it."""
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.executescript(_DDL)
        cur.executemany("INSERT INTO students VALUES (?,?,?,?)", STUDENTS)
        cur.executemany("INSERT INTO subjects VALUES (?,?,?)", SUBJECTS)
        cur.executemany("INSERT INTO grades VALUES (?,?,?,?,?)", GRADES)
        conn.commit()
    finally:
        conn.close()
    log.info("database seeded", extra={"db_path": db_path, **summary()})


if __name__ == "__main__":
    from .config import settings

    create(settings.db_path)
    print(f"created {settings.db_path} -> {summary()}")
