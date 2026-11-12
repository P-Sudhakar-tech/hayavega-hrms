from hayavega import api_route

from .views import employee_detail, employees_collection, list_departments

urlpatterns = [
    api_route("api/departments", list_departments, methods=("GET",)),
    api_route("api/employees", employees_collection, methods=("GET", "POST")),
    # api_route(), not path(): a plain path() view that returns a dict gets
    # str()'d into the response body, not JSON-encoded -- only api_route's
    # wrapper does the dict -> json_response conversion. The /<path>
    # wildcard-suffix mechanism works with either; it's generic to Route
    # matching, not api_route-specific.
    api_route("api/employees/<path>", employee_detail, methods=("GET",)),
]
