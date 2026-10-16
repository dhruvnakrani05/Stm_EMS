from django.contrib import admin
from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'name', 'surname', 'city', 'mobile_number', 'basic_salary', 'is_active')
    list_filter = ('is_active', 'city')
    search_fields = ('name', 'surname', 'employee_id', 'mobile_number')
    ordering = ('employee_id',)
