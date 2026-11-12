from hayavega import Response, api_route, path
from hayavega.admin import admin_routes
from hayavega.auth_api import auth_routes
from hayavega.conf import load_settings

from employees.admin import department_admin, employee_admin
from employees.routes import urlpatterns as employee_urlpatterns

_settings = load_settings()


def home(request):
    return Response("<h1>Hayavega HRMS</h1><p>See /api/employees, /api/departments, /admin, and /openapi.json.</p>")


def health(request):
    return {"status": "ok"}


urlpatterns = [
    path("", home),
    api_route("api/health", health),
    *employee_urlpatterns,
    *auth_routes(_settings.database, secret_key=_settings.secret_key),
    *admin_routes(_settings.database, models=[department_admin, employee_admin]),
]
