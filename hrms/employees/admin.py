from hayavega.admin import ModelAdmin

from .models import Department, Employee

department_admin = ModelAdmin(
    entity=Department,
    list_fields=("id", "name", "code"),
    search_fields=("name", "code"),
)

employee_admin = ModelAdmin(
    entity=Employee,
    list_fields=("id", "employee_code", "first_name", "last_name", "department_id", "is_active"),
    list_filter=("department_id", "is_active"),
    search_fields=("employee_code", "first_name", "last_name", "email"),
    page_size=50,
)
