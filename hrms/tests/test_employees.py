"""Correctness tests for the employees app's REST views.

Run with pytest from the hrms/ directory, against a disposable SQLite
file so this never touches the real hayavega.sqlite3 development
database or its 100k-row seeded dataset.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hayavega.runtime import create_application
from hayavega.testing import TestClient

import employees.views as views
from employees.models import Department
from employees.routes import urlpatterns


class EmployeesApiTests(unittest.TestCase):
    """employees/views.py binds _database once at import time from the
    real project settings (config/settings.py's hayavega.sqlite3) -- these
    tests monkeypatch that module attribute to a disposable temp file for
    the duration of each test, so they never touch the real development
    database or its seeded dataset."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = str(Path(self.directory.name) / "test.sqlite3")
        self._original_database = views._database
        views._database = self.database
        Department.collection(self.database).append(name="Engineering", code="ENG")
        self.client = TestClient(create_application(urlpatterns))

    def tearDown(self):
        views._database = self._original_database
        self.directory.cleanup()

    def _create_employee(self, **overrides):
        payload = {
            "employee_code": "E0001",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@example.com",
            "job_title": "Engineer",
            "department_id": 1,
            "date_joined": "2024-01-15T00:00:00+00:00",
            **overrides,
        }
        return self.client.post("/api/employees", json_data=payload)

    def test_list_departments_returns_seeded_department(self):
        response = self.client.get("/api/departments")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [{"id": 1, "name": "Engineering", "code": "ENG"}])

    def test_create_and_fetch_employee_round_trips(self):
        created = self._create_employee()
        self.assertEqual(created.status_code, 201)
        employee_id = created.json()["id"]

        detail = self.client.get(f"/api/employees/{employee_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["email"], "alice@example.com")

    def test_detail_404s_for_a_missing_employee(self):
        response = self.client.get("/api/employees/999")
        self.assertEqual(response.status_code, 404)

    def test_create_rejects_a_missing_required_field(self):
        payload = {"employee_code": "E0002"}
        response = self.client.post("/api/employees", json_data=payload)
        self.assertEqual(response.status_code, 400)

    def test_create_rejects_a_duplicate_employee_code(self):
        self._create_employee()
        response = self._create_employee(email="different@example.com")
        self.assertEqual(response.status_code, 400)

    def test_list_employees_is_paginated(self):
        for index in range(3):
            self._create_employee(employee_code=f"E000{index}", email=f"person{index}@example.com")
        response = self.client.get("/api/employees?page=1&page_size=2")
        body = response.json()
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["count"], 3)

    def test_list_employees_filters_by_department_id(self):
        Department.collection(self.database).append(name="Sales", code="SAL")
        self._create_employee()
        self._create_employee(employee_code="E0002", email="bob@example.com", department_id=2)

        response = self.client.get("/api/employees?department_id=2")
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["department_id"], 2)


if __name__ == "__main__":
    unittest.main()
