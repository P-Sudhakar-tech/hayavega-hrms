# Hayavega HRMS

A real HR Management System core (employees, departments, auth, admin),
built on the [Hayavega](https://github.com/P-Sudhakar-tech/HayaVega)
Python web framework, as a real-world stress test rather than a toy demo.

**Purpose**: Hayavega is early-stage (`v0.1.0`, no production track
record). This project exists to find out what actually breaks when you
build something real on it -- a dataset sized for a large organization,
real pagination/filtering/auth, and a real load test -- and to document
every gap found honestly, not paper over them. See **[FINDINGS.md](FINDINGS.md)**
for the full, prioritized list; the headline finding is a severe,
quantified performance bug in Hayavega's rate limiter.

## What's here

- `hrms/employees/` -- `Department`/`Employee` models, REST API
  (list/detail/create, paginated, filterable by department), admin
  registration.
- `hrms/employees/migrations/0001_initial.py` -- the schema, including
  hand-written `CREATE INDEX` statements Hayavega's own migration
  generator cannot produce (see FINDINGS.md, gap #1).
- `hrms/seed.py` -- generates a realistic dataset (departments, a
  manager hierarchy) at any scale; bypasses the ORM's one-row-at-a-time
  `append()` (no bulk-insert API exists) via direct `executemany()`.
- `hrms/tests/` -- correctness tests using Hayavega's own `TestClient`.
- `FINDINGS.md` -- every gap found, prioritized, with real data.

## Scale approach

Per the brief: **design for scale, test at a realistic size locally** --
not a real cloud deployment serving real millions of concurrent users.
Concretely: the schema is indexed and the API is paginated as if it
needed to serve millions of employee records, and it was seeded and
load-tested at 100,000 rows locally (SQLite, one machine) rather than
spun up against a sized cloud database.

## Running it

```bash
cd hrms
python -m venv .venv
.venv/Scripts/pip install -e "git+https://github.com/P-Sudhakar-tech/HayaVega.git#egg=hayavega"
# see requirements.txt for why main, not the PyPI release
python manage.py applymigrations
python seed.py --count 100000
python manage.py launch 8000
```

Then: `GET /api/employees?page=1&page_size=50`, `GET
/api/employees?department_id=3`, `GET /api/employees/42`, `POST
/api/employees`, `GET /api/departments`, `GET /admin` (after `python
manage.py createadmin`), `GET /openapi.json`.

## Running the tests

```bash
cd hrms
.venv/Scripts/python -m unittest tests.test_employees -v
```

## Status

Local-only, as scoped. Not deployed publicly. Built against a live
clone of Hayavega's `main` branch at commit `35e03cc`.
