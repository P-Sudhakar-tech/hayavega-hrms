"""Employee/Department REST views.

Two real routing gaps shaped this file -- see ../FINDINGS.md for the
full writeup, this is not a design choice being demonstrated:

1. No named/typed path-parameter routing (no `/employees/<id:int>`) --
   only a single trailing `/<path>` wildcard suffix, documented in
   Hayavega's own docs/topics/routing.md as "matches any suffix, handed
   to the view via the request's path info." `employees_collection`'s
   detail branch below parses the id itself, the same technique
   hayavega.static's static_routes() uses internally.
2. Registering two routes with the *same* pattern but different methods
   silently shadows the first one -- route_list is collapsed into a
   dict keyed by pattern with no duplicate check at all
   (hayavega.runtime.create_application's `routes = {route.pattern:
   route for route in route_list}`). The framework's own convention,
   confirmed in hayavega.admin's internal routes, is one view per path
   branching on `request.method` -- followed here instead of the
   Flask/Django-style "one function per method" a developer coming
   from those frameworks would otherwise reach for and get silently
   broken.
"""

from hayavega.conf import load_settings
from hayavega.response import json_response

from .models import Department, Employee

_settings = load_settings()
_database = _settings.database

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50


def _pagination(request) -> tuple[int, int]:
    """(limit, offset) from ?page=&page_size= -- clamped, never trusting
    client input directly against a database LIMIT/OFFSET."""
    try:
        page = max(1, int(request.query_params.get("page", ["1"])[0]))
    except ValueError:
        page = 1
    try:
        page_size = int(request.query_params.get("page_size", [str(DEFAULT_PAGE_SIZE)])[0])
    except ValueError:
        page_size = DEFAULT_PAGE_SIZE
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    return page_size, (page - 1) * page_size


def list_departments(request):
    rows = Department.collection(_database).browse().arrange("name").values("id", "name", "code")
    return {"results": rows, "count": len(rows)}


_EMPLOYEE_FIELDS = ("id", "employee_code", "first_name", "last_name", "email", "job_title", "department_id", "manager_id", "is_active")


def employees_collection(request):
    """GET: paginated list, optionally filtered by department_id -- the
    single most common real HRMS query ("who's in engineering"), which is
    exactly why employees_department_id_idx exists (see
    migrations/0001_initial.py). POST: create. One view branching on
    request.method, not two views on the same path -- see this module's
    docstring, point 2."""
    if request.method == "POST":
        return _create_employee(request)
    limit, offset = _pagination(request)
    selection = Employee.collection(_database).browse()
    department_id = request.query_params.get("department_id", [None])[0]
    if department_id is not None:
        try:
            selection = selection.match(department_id__exact=int(department_id))
        except ValueError:
            return json_response({"error": "department_id must be an integer"}, status=400)
    total = selection.total()
    rows = selection.arrange("id").window(limit, offset).values(*_EMPLOYEE_FIELDS)
    return {"results": rows, "count": total, "page_size": limit, "offset": offset}


def _create_employee(request):
    data = request.json()
    required = ("employee_code", "first_name", "last_name", "email", "job_title", "department_id", "date_joined")
    missing = [field for field in required if field not in data]
    if missing:
        return json_response({"error": f"missing required field(s): {', '.join(missing)}"}, status=400)
    try:
        employee = Employee.collection(_database).append(
            employee_code=data["employee_code"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            email=data["email"],
            job_title=data["job_title"],
            department_id=int(data["department_id"]),
            manager_id=int(data["manager_id"]) if data.get("manager_id") is not None else None,
            date_joined=data["date_joined"],
        )
    except Exception as error:  # noqa: BLE001 -- a UNIQUE-constraint violation (duplicate employee_code/email) is the realistic failure here, surfaced as a 400 rather than a 500
        return json_response({"error": str(error)}, status=400)
    return json_response({"id": employee.id}, status=201)


def employee_detail(request):
    suffix = request.path.strip("/").removeprefix("api/employees").lstrip("/")
    try:
        employee_id = int(suffix)
    except ValueError:
        return json_response({"error": "employee id must be an integer"}, status=400)
    rows = Employee.collection(_database).seek(id__exact=employee_id).values(*_EMPLOYEE_FIELDS)
    if not rows:
        return json_response({"error": "not found"}, status=404)
    return rows[0]
