"""Create and populate a 3-table demo database (so joins + aggregations are real).

  students(id, name, year, city)
  subjects(id, subject_name, department)
  grades(id, student_id, subject_id, score, grade)
"""
from __future__ import annotations

import os
import sqlite3

STUDENTS = [
    (1, "Aman", 2, "Bangalore"), (2, "Anshu", 1, "Hyderabad"),
    (3, "Akshu", 3, "Bangalore"), (4, "Rahul", 2, "Chennai"),
    (5, "Divyansh", 1, "Hyderabad"), (6, "Nandini", 3, "Chennai"),
    (7, "Priya", 2, "Bangalore"), (8, "Karthik", 1, "Chennai"),
]
SUBJECTS = [
    (1, "Math", "Science"), (2, "History", "Humanities"), (3, "Physics", "Science"),
]
GRADES = [
    (1, 1, 1, 95, "A"), (2, 2, 1, 78, "C"), (3, 3, 2, 88, "B"),
    (4, 4, 2, 92, "A"), (5, 5, 3, 85, "B"), (6, 6, 1, 65, "D"),
    (7, 7, 3, 91, "A"), (8, 8, 2, 73, "C"), (9, 1, 3, 80, "B"),
    (10, 2, 2, 69, "D"), (11, 3, 1, 90, "A"), (12, 4, 3, 82, "B"),
]


def create(db_path: str) -> None:
    if os.path.dirname(db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS grades;
        DROP TABLE IF EXISTS students;
        DROP TABLE IF EXISTS subjects;
        CREATE TABLE students  (id INTEGER PRIMARY KEY, name TEXT, year INTEGER, city TEXT);
        CREATE TABLE subjects  (id INTEGER PRIMARY KEY, subject_name TEXT, department TEXT);
        CREATE TABLE grades    (id INTEGER PRIMARY KEY, student_id INTEGER, subject_id INTEGER,
                                score INTEGER, grade TEXT,
                                FOREIGN KEY (student_id) REFERENCES students(id),
                                FOREIGN KEY (subject_id) REFERENCES subjects(id));
        """
    )
    cur.executemany("INSERT INTO students VALUES (?,?,?,?)", STUDENTS)
    cur.executemany("INSERT INTO subjects VALUES (?,?,?)", SUBJECTS)
    cur.executemany("INSERT INTO grades VALUES (?,?,?,?,?)", GRADES)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    from .config import settings
    create(settings.db_path)
    print(f"created {settings.db_path}")
