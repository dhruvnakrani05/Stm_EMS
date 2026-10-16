from django.contrib import admin
from .models import PayrollPeriod, PayrollRecord, PayrollLineItem, SalaryAdvance, PayrollAuditLog


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'status', 'total_working_days', 'record_count', 'generated_by', 'created_at')
    list_filter = ('status', 'year', 'month')
    search_fields = ('notes',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PayrollRecord)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = ('employee', 'period', 'base_salary', 'net_salary', 'is_paid', 'salary_modified')
    list_filter = ('period__month', 'period__year', 'is_paid', 'salary_modified')
    search_fields = ('employee__name', 'employee__surname', 'employee__employee_id')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('employee', 'period')


class PayrollLineItemInline(admin.TabularInline):
    model = PayrollLineItem
    extra = 0
    readonly_fields = ('category', 'item_type', 'description', 'amount', 'reference_id')


@admin.register(PayrollLineItem)
class PayrollLineItemAdmin(admin.ModelAdmin):
    list_display = ('payroll_record', 'category', 'item_type', 'description', 'amount')
    list_filter = ('category', 'item_type')
    raw_id_fields = ('payroll_record',)


@admin.register(SalaryAdvance)
class SalaryAdvanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'amount', 'date', 'status', 'deducted_in', 'added_by')
    list_filter = ('status', 'date')
    search_fields = ('employee__name', 'employee__surname')
    raw_id_fields = ('employee', 'deducted_in')


@admin.register(PayrollAuditLog)
class PayrollAuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'period', 'user', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('details',)
    readonly_fields = ('action', 'period', 'payroll_record', 'user', 'details', 'timestamp')
