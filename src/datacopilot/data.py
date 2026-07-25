"""Deterministic demo dataset.

The original fixture had 8 students / 3 subjects / 12 grades — too small for joins
and aggregations to tell an interesting story. This module generates a larger, but
fully **reproducible**, dataset (seeded RNG) so that:

  * joins and GROUP BYs return meaningful, non-trivial results, and
  * the evaluation harness stays deterministic run-to-run (same seed -> same rows).

Schema (unchanged from the original):
    students(id, name, year, city)
    subjects(id, subject_name, department)
    grades(id, student_id, subject_id, score, grade)

Import ``STUDENTS``, ``SUBJECTS``, ``GRADES`` (lists of tuples) or call
``build_dataset()`` to regenerate.
"""
from __future__ import annotations

import random

Student = tuple[int, str, int, str]
Subject = tuple[int, str, str]
Grade = tuple[int, int, int, int, str]

SEED = 42
N_STUDENTS = 60

CITIES: list[str] = [
    "Bangalore", "Hyderabad", "Chennai", "Mumbai", "Delhi", "Pune", "Kolkata",
]

# A pool of names; duplicates across the dataset are intentional and realistic.
FIRST_NAMES: list[str] = [
    "Aman", "Anshu", "Akshu", "Rahul", "Divyansh", "Nandini", "Priya", "Karthik",
    "Sneha", "Rohit", "Isha", "Vikram", "Meera", "Arjun", "Kavya", "Siddharth",
    "Ananya", "Rohan", "Pooja", "Aditya", "Neha", "Varun", "Riya", "Nikhil",
    "Shreya", "Gaurav", "Tanvi", "Harsh", "Diya", "Manish", "Sanjana", "Yash",
    "Ira", "Dev", "Aarti", "Kabir", "Lakshmi", "Om", "Bhavya", "Naveen",
]

# (subject_name, department)
SUBJECTS_DEF: list[tuple[str, str]] = [
    ("Math", "Science"),
    ("Physics", "Science"),
    ("Chemistry", "Science"),
    ("Biology", "Science"),
    ("History", "Humanities"),
    ("Geography", "Humanities"),
    ("English", "Humanities"),
    ("Economics", "Commerce"),
    ("Accounting", "Commerce"),
    ("Business Studies", "Commerce"),
    ("Computer Science", "Engineering"),
    ("Electronics", "Engineering"),
]

MIN_SUBJECTS_PER_STUDENT = 4
MAX_SUBJECTS_PER_STUDENT = 6
MIN_SCORE = 40
MAX_SCORE = 100


def grade_for(score: int) -> str:
    """Map a numeric score to a letter grade (standard 5-band scheme)."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def build_dataset(
    n_students: int = N_STUDENTS, seed: int = SEED
) -> tuple[list[Student], list[Subject], list[Grade]]:
    """Build (students, subjects, grades) deterministically for the given seed."""
    rng = random.Random(seed)

    students: list[Student] = []
    for sid in range(1, n_students + 1):
        name = rng.choice(FIRST_NAMES)
        year = rng.randint(1, 4)
        city = rng.choice(CITIES)
        students.append((sid, name, year, city))

    subjects: list[Subject] = [
        (idx, name, dept) for idx, (name, dept) in enumerate(SUBJECTS_DEF, start=1)
    ]

    grades: list[Grade] = []
    gid = 1
    n_subjects = len(subjects)
    for sid in range(1, n_students + 1):
        k = rng.randint(MIN_SUBJECTS_PER_STUDENT, MAX_SUBJECTS_PER_STUDENT)
        chosen = rng.sample(range(1, n_subjects + 1), k)
        for subject_id in chosen:
            score = rng.randint(MIN_SCORE, MAX_SCORE)
            grades.append((gid, sid, subject_id, score, grade_for(score)))
            gid += 1

    return students, subjects, grades


STUDENTS, SUBJECTS, GRADES = build_dataset()


def summary() -> dict:
    """Small helper used by the CLI / logs to report dataset size."""
    return {
        "students": len(STUDENTS),
        "subjects": len(SUBJECTS),
        "grades": len(GRADES),
        "cities": len({s[3] for s in STUDENTS}),
        "departments": len({s[2] for s in SUBJECTS}),
    }
