from django.contrib import admin
from .models import Attendance, Holiday


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'status', 'marked_by', 'created_at')
    list_filter = ('status', 'date')
    search_fields = ('employee__name', 'employee__surname', 'employee__employee_id')
    ordering = ('-date',)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('date', 'name', 'holiday_type')
    list_filter = ('holiday_type',)
    ordering = ('date',)
