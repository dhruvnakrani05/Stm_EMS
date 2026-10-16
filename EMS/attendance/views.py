import calendar
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from employees.models import Employee
from .models import Attendance, Holiday
from .forms import BulkAttendanceForm, AttendanceForm, HolidayForm
from accounts.decorators import hr_or_admin_required, admin_required


@hr_or_admin_required
def mark_attendance(request):
    """Bulk mark attendance for all active employees for a date."""
    employees = Employee.objects.filter(is_active=True).order_by('employee_id')
    today = timezone.now().date()

    if request.method == 'POST':
        att_date_str = request.POST.get('date', '')
        try:
            att_date = date.fromisoformat(att_date_str)
        except (ValueError, TypeError):
            att_date = today

        # Check if it's a Wednesday (weekly off)
        # if att_date.weekday() == settings.WEEKLY_OFF_DAY:
        #     messages.warning(request, f'{att_date.strftime("%A, %d %B %Y")} is a weekly off (Wednesday).')
        #     return redirect('attendance:mark')

        # Check if it's a holiday
        holiday = Holiday.objects.filter(date=att_date).first()
        if holiday:
            messages.warning(request, f'{att_date.strftime("%d %B %Y")} is a holiday: {holiday.name}')
            return redirect('attendance:mark')

        saved_count = 0
        for emp in employees:
            status = request.POST.get(f'status_{emp.id}', 'present')
            notes = request.POST.get(f'notes_{emp.id}', '')

            att, created = Attendance.objects.update_or_create(
                employee=emp,
                date=att_date,
                defaults={
                    'status': status,
                    'notes': notes,
                    'marked_by': request.user,
                }
            )
            saved_count += 1

        messages.success(
            request,
            f'Attendance marked for {saved_count} employees on {att_date.strftime("%d %B %Y")}.'
        )
        return redirect('attendance:daily', date=att_date.isoformat())

    # Check existing attendance for today
    existing = {}
    existing_records = Attendance.objects.filter(date=today)
    for record in existing_records:
        existing[record.employee_id] = record

    context = {
        'employees': employees,
        'today': today,
        'existing': existing,
        'is_thursday': today.weekday() == settings.WEEKLY_OFF_DAY,
        'holiday': Holiday.objects.filter(date=today).first(),
    }
    return render(request, 'attendance/mark_attendance.html', context)


@login_required
def daily_view(request, date=None):
    """View all employees' attendance for a specific date."""
    if date:
        try:
            view_date = date if isinstance(date, type(timezone.now().date())) else type(timezone.now().date()).fromisoformat(date)
        except (ValueError, TypeError):
            view_date = timezone.now().date()
    else:
        date_str = request.GET.get('date', '')
        try:
            view_date = type(timezone.now().date()).fromisoformat(date_str) if date_str else timezone.now().date()
        except (ValueError, TypeError):
            view_date = timezone.now().date()

    records = Attendance.objects.filter(date=view_date).select_related('employee')
    employees = Employee.objects.filter(is_active=True)

    # Build attendance map
    attendance_map = {r.employee_id: r for r in records}

    # Stats
    present = records.filter(status='present').count()
    absent = records.filter(status='absent').count()
    half_day = records.filter(status='half_day').count()
    casual = records.filter(status='casual_leave').count()
    unmarked = employees.count() - records.count()

    context = {
        'view_date': view_date,
        'records': records,
        'employees': employees,
        'attendance_map': attendance_map,
        'present': present,
        'absent': absent,
        'half_day': half_day,
        'casual': casual,
        'unmarked': unmarked,
        'total': employees.count(),
        'is_thursday': view_date.weekday() == settings.WEEKLY_OFF_DAY,
        'holiday': Holiday.objects.filter(date=view_date).first(),
    }
    return render(request, 'attendance/daily_view.html', context)


@login_required
def employee_attendance(request, pk):
    """View individual employee's attendance (daily/monthly/yearly)."""
    employee = get_object_or_404(Employee, pk=pk)
    today = timezone.now().date()

    view_type = request.GET.get('view', 'monthly')
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))

    if view_type == 'monthly':
        records = Attendance.objects.filter(
            employee=employee,
            date__year=year,
            date__month=month
        ).order_by('date')

        # Build calendar data
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(year, month)
        attendance_map = {r.date.day: r for r in records}

        # Stats
        present = records.filter(status='present').count()
        absent = records.filter(status='absent').count()
        half_day = records.filter(status='half_day').count()
        casual = records.filter(status='casual_leave').count()

        context = {
            'employee': employee,
            'records': records,
            'month_days': month_days,
            'attendance_map': attendance_map,
            'month': month,
            'year': year,
            'month_name': calendar.month_name[month],
            'present': present,
            'absent': absent,
            'half_day': half_day,
            'casual': casual,
            'view_type': view_type,
        }

    elif view_type == 'yearly':
        records = Attendance.objects.filter(
            employee=employee,
            date__year=year
        )

        monthly_data = []
        for m in range(1, 13):
            month_records = records.filter(date__month=m)
            monthly_data.append({
                'month': calendar.month_name[m],
                'month_num': m,
                'present': month_records.filter(status='present').count(),
                'absent': month_records.filter(status='absent').count(),
                'half_day': month_records.filter(status='half_day').count(),
                'casual': month_records.filter(status='casual_leave').count(),
                'total': month_records.count(),
            })

        context = {
            'employee': employee,
            'monthly_data': monthly_data,
            'year': year,
            'view_type': view_type,
        }

    else:  # daily
        records = Attendance.objects.filter(
            employee=employee
        ).order_by('-date')[:90]

        context = {
            'employee': employee,
            'records': records,
            'view_type': view_type,
        }

    return render(request, 'attendance/employee_attendance.html', context)


@login_required
def monthly_report(request):
    """Monthly attendance report for all employees."""
    today = timezone.now().date()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))

    employees = Employee.objects.filter(is_active=True)
    records = Attendance.objects.filter(
        date__year=year,
        date__month=month
    ).select_related('employee')

    # Build data per employee
    employee_data = []
    for emp in employees:
        emp_records = records.filter(employee=emp)
        employee_data.append({
            'employee': emp,
            'present': emp_records.filter(status='present').count(),
            'absent': emp_records.filter(status='absent').count(),
            'half_day': emp_records.filter(status='half_day').count(),
            'casual': emp_records.filter(status='casual_leave').count(),
            'total': emp_records.count(),
        })

    # Get working days for the month
    num_days = calendar.monthrange(year, month)[1]
    thursdays = sum(1 for d in range(1, num_days + 1) if date(year, month, d).weekday() == settings.WEEKLY_OFF_DAY)
    holidays = Holiday.objects.filter(
        date__year=year,
        date__month=month
    ).exclude(holiday_type='weekly').count()
    working_days = num_days - thursdays - holidays

    context = {
        'employee_data': employee_data,
        'month': month,
        'year': year,
        'month_name': calendar.month_name[month],
        'working_days': working_days,
        'total_employees': employees.count(),
    }
    return render(request, 'attendance/monthly_report.html', context)


@login_required
def yearly_report(request):
    """Yearly attendance summary."""
    today = timezone.now().date()
    year = int(request.GET.get('year', today.year))

    employees = Employee.objects.filter(is_active=True)
    records = Attendance.objects.filter(date__year=year).select_related('employee')

    # Monthly summary
    monthly_summary = []
    for m in range(1, 13):
        month_records = records.filter(date__month=m)
        monthly_summary.append({
            'month': calendar.month_abbr[m],
            'month_num': m,
            'present': month_records.filter(status='present').count(),
            'absent': month_records.filter(status='absent').count(),
            'half_day': month_records.filter(status='half_day').count(),
            'casual': month_records.filter(status='casual_leave').count(),
        })

    # Per-employee yearly summary
    employee_yearly = []
    for emp in employees:
        emp_records = records.filter(employee=emp)
        employee_yearly.append({
            'employee': emp,
            'present': emp_records.filter(status='present').count(),
            'absent': emp_records.filter(status='absent').count(),
            'half_day': emp_records.filter(status='half_day').count(),
            'casual': emp_records.filter(status='casual_leave').count(),
        })

    context = {
        'year': year,
        'monthly_summary': monthly_summary,
        'employee_yearly': employee_yearly,
        'total_employees': employees.count(),
    }
    return render(request, 'attendance/yearly_report.html', context)


@hr_or_admin_required
def edit_attendance(request, pk):
    """Edit an existing attendance record."""
    record = get_object_or_404(Attendance, pk=pk)
    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=record)
        if form.is_valid():
            att = form.save(commit=False)
            att.marked_by = request.user
            att.save()
            messages.success(request, f'Attendance updated for {record.employee.full_name} on {record.date}.')
            return redirect('attendance:daily', date=record.date.isoformat())
    else:
        form = AttendanceForm(instance=record)

    return render(request, 'attendance/edit_attendance.html', {
        'form': form,
        'record': record,
    })


@admin_required
def manage_holidays(request):
    """Add/view/delete holidays."""
    if request.method == 'POST':
        form = HolidayForm(request.POST)
        if form.is_valid():
            holiday = form.save()
            messages.success(request, f'Holiday "{holiday.name}" added on {holiday.date}.')
            return redirect('attendance:holidays')
    else:
        form = HolidayForm()

    holidays = Holiday.objects.all().order_by('date')
    return render(request, 'attendance/holidays.html', {
        'form': form,
        'holidays': holidays,
    })


@admin_required
def delete_holiday(request, pk):
    """Delete a holiday."""
    holiday = get_object_or_404(Holiday, pk=pk)
    if request.method == 'POST':
        holiday.delete()
        messages.success(request, f'Holiday "{holiday.name}" deleted.')
    return redirect('attendance:holidays')
