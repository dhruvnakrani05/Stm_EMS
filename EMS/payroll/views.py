import calendar
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from employees.models import Employee
from .models import PayrollPeriod, PayrollRecord, SalaryAdvance, PayrollAuditLog
from .forms import GeneratePayrollForm, ModifyPayrollForm, SalaryAdvanceForm, PayrollFilterForm
from .services import PayrollService, PayrollServiceError, PeriodLockedError
from accounts.decorators import admin_required, hr_or_admin_required


# ─── Payroll Generation ────────────────────────────────────────────────

@admin_required
def generate_payroll(request):
    """Generate payroll for all active employees for a specific month."""
    today = timezone.now().date()

    if request.method == 'POST':
        form = GeneratePayrollForm(request.POST)
        if form.is_valid():
            month = form.cleaned_data['month']
            year = form.cleaned_data['year']

            try:
                result = PayrollService.generate_payroll(month, year, request.user)

                msg_parts = []
                if result['generated']:
                    msg_parts.append(f"{result['generated']} new payroll(s) generated")
                if result['updated']:
                    msg_parts.append(f"{result['updated']} existing payroll(s) updated")
                if result['skipped']:
                    msg_parts.append(f"{result['skipped']} manually modified record(s) skipped")

                messages.success(request, '. '.join(msg_parts) + '.')
                return redirect('payroll:list')

            except PeriodLockedError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error generating payroll: {str(e)}')
    else:
        form = GeneratePayrollForm(initial={
            'month': today.month,
            'year': today.year,
        })

    # Preview data
    employees = Employee.objects.filter(is_active=True)
    preview = []
    for emp in employees:
        preview.append({
            'employee': emp,
            'base_salary': emp.basic_salary,
        })

    # Check if period already exists for preview
    existing_period = PayrollPeriod.objects.filter(
        month=today.month, year=today.year
    ).first()

    return render(request, 'payroll/generate_payroll.html', {
        'form': form,
        'preview': preview,
        'total_employees': employees.count(),
        'existing_period': existing_period,
    })


# ─── Payroll List ──────────────────────────────────────────────────────

@login_required
def payroll_list(request):
    """View all payroll records with filters."""
    form = PayrollFilterForm(request.GET)
    records = PayrollRecord.objects.select_related(
        'employee', 'period'
    ).all()

    month = request.GET.get('month')
    year = request.GET.get('year')
    employee_id = request.GET.get('employee')
    status = request.GET.get('status')

    if month:
        records = records.filter(period__month=int(month))
    if year:
        records = records.filter(period__year=int(year))
    if employee_id:
        records = records.filter(employee_id=int(employee_id))
    if status == 'paid':
        records = records.filter(is_paid=True)
    elif status == 'unpaid':
        records = records.filter(is_paid=False)

    # Totals
    total_salary = records.aggregate(total=Sum('net_salary'))['total'] or Decimal('0')
    total_paid = records.filter(is_paid=True).aggregate(total=Sum('net_salary'))['total'] or Decimal('0')
    total_unpaid = records.filter(is_paid=False).aggregate(total=Sum('net_salary'))['total'] or Decimal('0')

    # Get periods for grouping context
    periods = PayrollPeriod.objects.all().order_by('-year', '-month')

    context = {
        'records': records,
        'form': form,
        'total_salary': total_salary,
        'total_paid': total_paid,
        'total_unpaid': total_unpaid,
        'periods': periods,
    }
    return render(request, 'payroll/payroll_list.html', context)


# ─── Payroll Detail ────────────────────────────────────────────────────

@login_required
def payroll_detail(request, pk):
    """View detailed payroll slip with line-item breakdown."""
    record = get_object_or_404(
        PayrollRecord.objects.select_related('employee', 'period'),
        pk=pk
    )

    # Line items grouped by category
    earnings = record.line_items.filter(category='earning')
    deductions = record.line_items.filter(category='deduction')

    # Advances for this period
    advances = SalaryAdvance.objects.filter(
        employee=record.employee,
        date__year=record.period.year,
        date__month=record.period.month
    )

    # Recent audit logs for this record
    audit_logs = PayrollAuditLog.objects.filter(
        payroll_record=record
    ).select_related('user')[:10]

    context = {
        'record': record,
        'earnings': earnings,
        'deductions': deductions,
        'advances': advances,
        'audit_logs': audit_logs,
    }
    return render(request, 'payroll/payroll_detail.html', context)


# ─── Modify Salary ────────────────────────────────────────────────────

@admin_required
def modify_salary(request, pk):
    """Admin: modify salary for a payroll record."""
    record = get_object_or_404(
        PayrollRecord.objects.select_related('period', 'employee'),
        pk=pk
    )

    if not record.period.can_modify:
        messages.error(
            request,
            f'Cannot modify — period is {record.period.get_status_display()}.'
        )
        return redirect('payroll:detail', pk=record.pk)

    if request.method == 'POST':
        form = ModifyPayrollForm(request.POST, instance=record)
        if form.is_valid():
            try:
                PayrollService.modify_record(
                    record_pk=record.pk,
                    modified_by=request.user,
                    base_salary=form.cleaned_data['base_salary'],
                    bonuses=form.cleaned_data['bonuses'],
                    total_advances=form.cleaned_data['total_advances'],
                    other_deductions=form.cleaned_data.get('other_deductions', Decimal('0')),
                    modification_note=form.cleaned_data['modification_note'],
                )
                messages.success(
                    request,
                    f'Salary modified for {record.employee.full_name} — '
                    f'{record.period.get_month_display()} {record.period.year}.'
                )
                return redirect('payroll:detail', pk=record.pk)
            except PayrollServiceError as e:
                messages.error(request, str(e))
    else:
        form = ModifyPayrollForm(instance=record)

    return render(request, 'payroll/modify_salary.html', {
        'form': form,
        'record': record,
    })


# ─── Payment Management ───────────────────────────────────────────────

@admin_required
def mark_paid(request, pk):
    """Mark a payroll record as paid."""
    if request.method == 'POST':
        try:
            record = PayrollService.mark_paid(pk, request.user)
            messages.success(
                request,
                f'Payroll marked as paid for {record.employee.full_name}.'
            )
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    return redirect('payroll:detail', pk=pk)


@admin_required
def mark_unpaid(request, pk):
    """Mark a payroll record as unpaid."""
    if request.method == 'POST':
        try:
            record = PayrollService.mark_unpaid(pk, request.user)
            messages.success(
                request,
                f'Payroll marked as unpaid for {record.employee.full_name}.'
            )
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    return redirect('payroll:detail', pk=pk)


@admin_required
def mark_period_paid(request, period_pk):
    """Batch-mark all unpaid records in a period as paid."""
    if request.method == 'POST':
        try:
            count = PayrollService.mark_period_paid(period_pk, request.user)
            messages.success(request, f'{count} payroll record(s) marked as paid.')
        except PayrollServiceError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    return redirect('payroll:list')


# ─── Finalize Period ───────────────────────────────────────────────────

@admin_required
def finalize_period(request, period_pk):
    """Finalize a payroll period — locks it from modifications."""
    period = get_object_or_404(PayrollPeriod, pk=period_pk)

    if request.method == 'POST':
        try:
            PayrollService.finalize_period(period_pk, request.user)
            messages.success(
                request,
                f'Payroll period {period.get_month_display()} {period.year} has been finalized.'
            )
            return redirect('payroll:list')
        except PayrollServiceError as e:
            messages.error(request, str(e))

    # GET — confirmation page
    records = period.payroll_records.select_related('employee').all()
    total = records.aggregate(total=Sum('net_salary'))['total'] or Decimal('0')

    return render(request, 'payroll/finalize_period.html', {
        'period': period,
        'records': records,
        'total_salary': total,
    })


# ─── Employee Payroll History ──────────────────────────────────────────

@login_required
def employee_payroll_history(request, pk):
    """View full payroll history for an employee."""
    employee = get_object_or_404(Employee, pk=pk)
    records = PayrollRecord.objects.filter(
        employee=employee
    ).select_related('period').order_by('-period__year', '-period__month')

    # Yearly totals
    years = records.values_list('period__year', flat=True).distinct()
    yearly_data = []
    for yr in years:
        yr_records = records.filter(period__year=yr)
        yearly_data.append({
            'year': yr,
            'total_salary': yr_records.aggregate(total=Sum('net_salary'))['total'] or 0,
            'total_paid': yr_records.filter(is_paid=True).aggregate(total=Sum('net_salary'))['total'] or 0,
            'records': yr_records,
        })

    # All advances
    advances = SalaryAdvance.objects.filter(employee=employee).order_by('-date')

    context = {
        'employee': employee,
        'records': records,
        'yearly_data': yearly_data,
        'advances': advances,
    }
    return render(request, 'payroll/employee_history.html', context)


# ─── Yearly Summary ───────────────────────────────────────────────────

@login_required
def yearly_summary(request):
    """Yearly salary summary across all employees."""
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year))

    records = PayrollRecord.objects.filter(
        period__year=year
    ).select_related('employee', 'period')

    # Monthly totals
    monthly_totals = []
    for m in range(1, 13):
        month_records = records.filter(period__month=m)
        monthly_totals.append({
            'month': calendar.month_name[m],
            'month_abbr': calendar.month_abbr[m],
            'total': month_records.aggregate(total=Sum('net_salary'))['total'] or 0,
            'paid': month_records.filter(is_paid=True).aggregate(total=Sum('net_salary'))['total'] or 0,
            'unpaid': month_records.filter(is_paid=False).aggregate(total=Sum('net_salary'))['total'] or 0,
            'count': month_records.count(),
        })

    # Employee-wise totals
    employees = Employee.objects.filter(is_active=True)
    employee_totals = []
    for emp in employees:
        emp_records = records.filter(employee=emp)
        employee_totals.append({
            'employee': emp,
            'total': emp_records.aggregate(total=Sum('net_salary'))['total'] or 0,
            'paid': emp_records.filter(is_paid=True).aggregate(total=Sum('net_salary'))['total'] or 0,
        })

    grand_total = records.aggregate(total=Sum('net_salary'))['total'] or 0
    total_paid = records.filter(is_paid=True).aggregate(total=Sum('net_salary'))['total'] or 0

    context = {
        'year': year,
        'monthly_totals': monthly_totals,
        'employee_totals': employee_totals,
        'grand_total': grand_total,
        'total_paid': total_paid,
    }
    return render(request, 'payroll/yearly_summary.html', context)


# ─── Salary Advance Management ────────────────────────────────────────

@hr_or_admin_required
def add_advance(request):
    """Record a salary advance for an employee."""
    if request.method == 'POST':
        form = SalaryAdvanceForm(request.POST)
        if form.is_valid():
            try:
                advance = PayrollService.add_advance(
                    employee_pk=form.cleaned_data['employee'].pk,
                    amount=form.cleaned_data['amount'],
                    advance_date=form.cleaned_data['date'],
                    reason=form.cleaned_data.get('reason', ''),
                    added_by=request.user,
                )
                messages.success(
                    request,
                    f'Advance of ₹{advance.amount} recorded for {advance.employee.full_name}.'
                )
                return redirect('payroll:advances')
            except PayrollServiceError as e:
                messages.error(request, str(e))
    else:
        form = SalaryAdvanceForm()

    return render(request, 'payroll/add_advance.html', {'form': form})


@login_required
def advance_list(request):
    """List all salary advances with filtering."""
    advances = SalaryAdvance.objects.select_related('employee').order_by('-date')

    employee_id = request.GET.get('employee')
    status = request.GET.get('status')

    if employee_id:
        advances = advances.filter(employee_id=int(employee_id))
    if status:
        advances = advances.filter(status=status)

    context = {
        'advances': advances,
        'employees': Employee.objects.filter(is_active=True),
    }
    return render(request, 'payroll/advance_list.html', context)


@hr_or_admin_required
def edit_advance(request, pk):
    """Edit a salary advance."""
    advance = get_object_or_404(SalaryAdvance, pk=pk)

    if advance.status != 'pending':
        messages.error(
            request,
            f'Cannot edit — advance is {advance.get_status_display()}.'
        )
        return redirect('payroll:advances')

    if request.method == 'POST':
        form = SalaryAdvanceForm(request.POST, instance=advance)
        if form.is_valid():
            try:
                PayrollService.edit_advance(
                    advance_pk=advance.pk,
                    amount=form.cleaned_data['amount'],
                    advance_date=form.cleaned_data['date'],
                    reason=form.cleaned_data.get('reason', ''),
                    edited_by=request.user,
                )
                messages.success(request, 'Advance updated successfully.')
                return redirect('payroll:advances')
            except PayrollServiceError as e:
                messages.error(request, str(e))
    else:
        form = SalaryAdvanceForm(instance=advance)

    return render(request, 'payroll/add_advance.html', {
        'form': form,
        'editing': True,
        'advance': advance,
    })


@admin_required
def delete_advance(request, pk):
    """Delete a salary advance."""
    if request.method == 'POST':
        try:
            PayrollService.delete_advance(pk, request.user)
            messages.success(request, 'Advance deleted successfully.')
        except PayrollServiceError as e:
            messages.error(request, str(e))
    return redirect('payroll:advances')


# ─── Audit Log ─────────────────────────────────────────────────────────

@admin_required
def audit_log(request):
    """View the payroll audit trail."""
    logs = PayrollAuditLog.objects.select_related(
        'period', 'payroll_record', 'user'
    ).order_by('-timestamp')

    # Optional period filter
    period_pk = request.GET.get('period')
    if period_pk:
        logs = logs.filter(period_id=int(period_pk))

    periods = PayrollPeriod.objects.all().order_by('-year', '-month')

    context = {
        'logs': logs[:100],  # Limit to recent 100
        'periods': periods,
        'selected_period': period_pk,
    }
    return render(request, 'payroll/audit_log.html', context)
