"""Seed realistic Department/Employee data for scale testing.

Bypasses Collection.append() (one connection open/commit/close per row --
there is no bulk-insert API in Hayavega's ORM at all, see FINDINGS.md)
and uses the underlying DB-API connection's executemany() directly,
batched into transactions, the only way to seed hundreds of thousands of
rows in reasonable time.

Usage:
    python seed.py [--count 100000] [--batch-size 5000]
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hayavega.conf import load_settings  # noqa: E402
from hayavega.db import connect, enable_wal_mode  # noqa: E402

DEPARTMENTS = [
    ("Engineering", "ENG"),
    ("Sales", "SAL"),
    ("Human Resources", "HR"),
    ("Finance", "FIN"),
    ("Marketing", "MKT"),
    ("Customer Support", "SUP"),
    ("Legal", "LEG"),
    ("Operations", "OPS"),
    ("Product", "PRD"),
    ("Design", "DSG"),
    ("Data & Analytics", "DAT"),
    ("Security", "SEC"),
    ("IT", "IT"),
    ("Research & Development", "RND"),
    ("Procurement", "PRC"),
]

FIRST_NAMES = ["James", "Mary", "John", "Priya", "Wei", "Fatima", "Carlos", "Yuki", "Olga", "Ahmed", "Emma", "Liam", "Sofia", "Noah", "Aisha", "Ravi", "Elena", "Mohammed", "Grace", "Daniel"]
LAST_NAMES = ["Smith", "Johnson", "Patel", "Kim", "Garcia", "Chen", "Ivanov", "Khan", "Silva", "Brown", "Nguyen", "Müller", "Rossi", "Sato", "Dubois", "Kowalski", "Singh", "Tanaka", "Lopez", "Novak"]

JOB_TITLES = ["Associate", "Senior Associate", "Specialist", "Analyst", "Senior Analyst", "Manager", "Senior Manager", "Director", "Coordinator", "Lead"]


def seed(count: int, batch_size: int) -> None:
    settings = load_settings()
    database = settings.database
    enable_wal_mode()

    connection = connect(database)
    try:
        connection.execute("DELETE FROM employees")
        connection.execute("DELETE FROM departments")
        connection.commit()

        cursor = connection.raw.cursor()
        cursor.executemany("INSERT INTO departments (id, name, code) VALUES (?, ?, ?)", [(i + 1, name, code) for i, (name, code) in enumerate(DEPARTMENTS)])
        connection.commit()
        department_ids = list(range(1, len(DEPARTMENTS) + 1))

        rng = random.Random(42)  # deterministic, reproducible dataset across runs
        start = time.perf_counter()
        department_heads: dict[int, int] = {}  # department_id -> first employee id in that department (its "head", no manager)
        department_members: dict[int, list[int]] = {department_id: [] for department_id in department_ids}
        batch: list[tuple] = []
        now = datetime.now(timezone.utc)

        for employee_id in range(1, count + 1):
            department_id = department_ids[(employee_id - 1) % len(department_ids)]
            first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
            members = department_members[department_id]
            if department_id not in department_heads:
                manager_id = None
                department_heads[department_id] = employee_id
            else:
                # Report to the department head, or to a random earlier
                # employee already seen in the *same* department -- a
                # shallow, realistic-enough hierarchy, not a claim of real
                # org-chart modeling. Must stay within the same
                # department: an earlier employee_id picked without this
                # constraint is very likely a different department, since
                # department assignment cycles round-robin across all 15.
                manager_id = department_heads[department_id] if rng.random() < 0.3 or len(members) < 2 else rng.choice(members)
            members.append(employee_id)
            joined = now - timedelta(days=rng.randint(0, 3650))
            batch.append(
                (
                    employee_id,
                    f"E{employee_id:08d}",
                    first,
                    last,
                    f"{first.lower()}.{last.lower()}{employee_id}@hrms.example",
                    rng.choice(JOB_TITLES),
                    department_id,
                    manager_id,
                    joined.isoformat(),
                    1,
                )
            )
            if len(batch) >= batch_size:
                cursor.executemany("INSERT INTO employees (id, employee_code, first_name, last_name, email, job_title, department_id, manager_id, date_joined, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", batch)
                connection.commit()
                batch.clear()
                print(f"  {employee_id}/{count} ({time.perf_counter() - start:.1f}s)", end="\r")

        if batch:
            cursor.executemany("INSERT INTO employees (id, employee_code, first_name, last_name, email, job_title, department_id, manager_id, date_joined, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", batch)
            connection.commit()

        elapsed = time.perf_counter() - start
        print(f"\nSeeded {count} employees across {len(DEPARTMENTS)} departments in {elapsed:.1f}s ({count / elapsed:.0f} rows/s).")
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100_000)
    parser.add_argument("--batch-size", type=int, default=5_000)
    args = parser.parse_args()
    seed(args.count, args.batch_size)


if __name__ == "__main__":
    main()
