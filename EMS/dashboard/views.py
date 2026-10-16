from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count
from employees.models import Employee
from attendance.models import Attendance
from payroll.models import PayrollRecord


@login_required
def dashboard(request):
    """Main dashboard with overview stats and charts."""
    today = timezone.now().date()

    # Employee stats
    total_employees = Employee.objects.filter(is_active=True).count()
    inactive_employees = Employee.objects.filter(is_active=False).count()

    # Today's attendance
    today_attendance = Attendance.objects.filter(date=today)
    present_today = today_attendance.filter(status='present').count()
    absent_today = today_attendance.filter(status='absent').count()
    halfday_today = today_attendance.filter(status='half_day').count()
    casual_today = today_attendance.filter(status='casual_leave').count()
    unmarked_today = total_employees - today_attendance.count()

    # Attendance percentage
    attendance_percentage = 0
    if total_employees > 0:
        effective_present = present_today + (halfday_today * 0.5)
        attendance_percentage = round((effective_present / total_employees) * 100, 1)

    # Current month payroll (using period-based lookups)
    current_month_payroll = PayrollRecord.objects.filter(
        period__month=today.month,
        period__year=today.year
    )
    total_salary_current = current_month_payroll.aggregate(
        total=Sum('net_salary')
    )['total'] or Decimal('0')
    paid_salary_current = current_month_payroll.filter(
        is_paid=True
    ).aggregate(total=Sum('net_salary'))['total'] or Decimal('0')
    unpaid_salary_current = total_salary_current - paid_salary_current

    # Last 7 days attendance trend
    from datetime import timedelta
    attendance_trend = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        day_att = Attendance.objects.filter(date=d)
        attendance_trend.append({
            'date': d.strftime('%d %b'),
            'day': d.strftime('%a'),
            'present': day_att.filter(status='present').count(),
            'absent': day_att.filter(status='absent').count(),
            'half_day': day_att.filter(status='half_day').count(),
        })

    # Monthly salary trend (last 6 months)
    salary_trend = []
    import calendar
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        month_payroll = PayrollRecord.objects.filter(
            period__month=m, period__year=y
        )
        salary_trend.append({
            'month': calendar.month_abbr[m],
            'total': float(month_payroll.aggregate(total=Sum('net_salary'))['total'] or 0),
            'paid': float(month_payroll.filter(is_paid=True).aggregate(total=Sum('net_salary'))['total'] or 0),
        })

    # Recent employees
    recent_employees = Employee.objects.filter(is_active=True).order_by('-created_at')[:5]

    # Recent payroll activity
    recent_payroll = PayrollRecord.objects.select_related(
        'employee', 'period'
    ).order_by('-created_at')[:5]

    context = {
        'today': today,
        'total_employees': total_employees,
        'inactive_employees': inactive_employees,
        'present_today': present_today,
        'absent_today': absent_today,
        'halfday_today': halfday_today,
        'casual_today': casual_today,
        'unmarked_today': unmarked_today,
        'attendance_percentage': attendance_percentage,
        'total_salary_current': total_salary_current,
        'paid_salary_current': paid_salary_current,
        'unpaid_salary_current': unpaid_salary_current,
        'attendance_trend': attendance_trend,
        'salary_trend': salary_trend,
        'recent_employees': recent_employees,
        'recent_payroll': recent_payroll,
    }
    return render(request, 'dashboard/dashboard.html', context)
