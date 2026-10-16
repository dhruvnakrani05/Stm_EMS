from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Employee
from .forms import EmployeeForm, EmployeeSearchForm
from accounts.decorators import admin_required


@login_required
def employee_list(request):
    """List all employees with search and filter."""
    form = EmployeeSearchForm(request.GET)
    employees = Employee.objects.all()

    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    if search_query:
        employees = employees.filter(
            Q(name__icontains=search_query) |
            Q(surname__icontains=search_query) |
            Q(employee_id__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(mobile_number__icontains=search_query)
        )

    if status_filter == 'active':
        employees = employees.filter(is_active=True)
    elif status_filter == 'inactive':
        employees = employees.filter(is_active=False)

    context = {
        'employees': employees,
        'form': form,
        'total_count': employees.count(),
        'active_count': employees.filter(is_active=True).count(),
    }
    return render(request, 'employees/employee_list.html', context)


@login_required
def employee_detail(request, pk):
    """View detailed employee profile with attendance and payroll summary."""
    employee = get_object_or_404(Employee, pk=pk)

    # Recent attendance
    recent_attendance = employee.attendances.order_by('-date')[:30]

    # Recent payroll
    recent_payroll = employee.payroll_records.select_related(
    'period'
    ).order_by('-period__year', '-period__month')[:12]

    # Attendance summary for current month
    from django.utils import timezone
    today = timezone.now().date()
    current_month_attendance = employee.attendances.filter(
        date__year=today.year,
        date__month=today.month
    )
    present_count = current_month_attendance.filter(status='present').count()
    absent_count = current_month_attendance.filter(status='absent').count()
    halfday_count = current_month_attendance.filter(status='half_day').count()
    casual_count = current_month_attendance.filter(status='casual_leave').count()

    # Salary advances
    recent_advances = employee.salary_advances.order_by('-date')[:10]

    context = {
        'employee': employee,
        'recent_attendance': recent_attendance,
        'recent_payroll': recent_payroll,
        'recent_advances': recent_advances,
        'present_count': present_count,
        'absent_count': absent_count,
        'halfday_count': halfday_count,
        'casual_count': casual_count,
        'current_month': today.strftime('%B %Y'),
    }
    return render(request, 'employees/employee_detail.html', context)


@admin_required
def employee_create(request):
    """Add a new employee. Admin only."""
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Employee "{employee.full_name}" added successfully.')
            return redirect('employees:detail', pk=employee.pk)
    else:
        form = EmployeeForm()

    return render(request, 'employees/employee_form.html', {
        'form': form,
        'title': 'Add New Employee',
        'button_text': 'Add Employee',
    })


@admin_required
def employee_edit(request, pk):
    """Edit employee details. Admin only."""
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, f'Employee "{employee.full_name}" updated successfully.')
            return redirect('employees:detail', pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee)

    return render(request, 'employees/employee_form.html', {
        'form': form,
        'title': f'Edit Employee: {employee.full_name}',
        'button_text': 'Update Employee',
        'employee': employee,
    })


@admin_required
def employee_delete(request, pk):
    """Deactivate/delete an employee. Admin only."""
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action', 'deactivate')
        if action == 'delete':
            name = employee.full_name
            employee.delete()
            messages.success(request, f'Employee "{name}" permanently deleted.')
        else:
            employee.is_active = False
            employee.save()
            messages.success(request, f'Employee "{employee.full_name}" deactivated.')
        return redirect('employees:list')

    return render(request, 'employees/employee_confirm_delete.html', {
        'employee': employee,
    })
