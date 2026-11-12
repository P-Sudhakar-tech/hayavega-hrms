"""Core HRMS entities: Department and Employee.

Scale note: Hayavega's ORM has no first-class way to declare a secondary
index on a column (only PRIMARY KEY / UNIQUE) -- see
employees/migrations/0001_initial.py, which adds the real indexes this
app needs (department_id, manager_id, email, employee_code) by hand via
raw SQL, and ../FINDINGS.md for the framework-gap writeup this produced.
"""

from hayavega import Entity, Integer, Text, Timestamp, Toggle


class Department(Entity):
    __table__ = "departments"

    name = Text(unique=True)
    code = Text(unique=True)


class Employee(Entity):
    __table__ = "employees"

    employee_code = Text(unique=True)
    first_name = Text()
    last_name = Text()
    email = Text(unique=True)
    job_title = Text()
    department_id = Integer()
    manager_id = Integer(nullable=True)
    date_joined = Timestamp()  # Hayavega has no date-only column type; a Timestamp at midnight UTC stands in -- see FINDINGS.md
    is_active = Toggle(default=True)
