import io
import calendar
from decimal import Decimal
from datetime import date
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.template.loader import render_to_string
from django.db.models import Sum
from employees.models import Employee
from attendance.models import Attendance
from payroll.models import PayrollRecord, SalaryAdvance
from accounts.decorators import admin_required
import urllib.parse


@login_required
def report_index(request):
    """Report generation index page."""
    employees = Employee.objects.filter(is_active=True)
    today = timezone.now().date()
    context = {
        'employees': employees,
        'current_month': today.month,
        'current_year': today.year,
    }
    return render(request, 'reports/report_index.html', context)


@login_required
def download_attendance_report(request):
    """Download attendance report as PDF."""
    employee_id = request.GET.get('employee')
    month = int(request.GET.get('month', timezone.now().date().month))
    year = int(request.GET.get('year', timezone.now().date().year))
    report_type = request.GET.get('type', 'individual')  # individual or overall

    if report_type == 'overall':
        return _generate_overall_attendance_pdf(month, year)
    else:
        if not employee_id:
            return HttpResponse('Employee ID is required for individual reports.', status=400)
        employee = get_object_or_404(Employee, pk=employee_id)
        return _generate_individual_attendance_pdf(employee, month, year)


@login_required
def download_payroll_report(request):
    """Download payroll report as PDF."""
    employee_id = request.GET.get('employee')
    month = int(request.GET.get('month', timezone.now().date().month))
    year = int(request.GET.get('year', timezone.now().date().year))
    report_type = request.GET.get('type', 'individual')

    if report_type == 'overall':
        return _generate_overall_payroll_pdf(month, year)
    else:
        if not employee_id:
            return HttpResponse('Employee ID is required for individual reports.', status=400)
        employee = get_object_or_404(Employee, pk=employee_id)
        return _generate_individual_payroll_pdf(employee, month, year)


@login_required
def share_report(request):
    """Generate shareable text for WhatsApp/SMS."""
    employee_id = request.GET.get('employee')
    month = int(request.GET.get('month', timezone.now().date().month))
    year = int(request.GET.get('year', timezone.now().date().year))
    report_type = request.GET.get('report', 'attendance')
    share_via = request.GET.get('via', 'whatsapp')

    month_name = calendar.month_name[month]

    if employee_id:
        employee = get_object_or_404(Employee, pk=employee_id)
        if report_type == 'attendance':
            text = _generate_attendance_share_text(employee, month, year, month_name)
        else:
            text = _generate_payroll_share_text(employee, month, year, month_name)
    else:
        if report_type == 'attendance':
            text = _generate_overall_attendance_share_text(month, year, month_name)
        else:
            text = _generate_overall_payroll_share_text(month, year, month_name)

    encoded_text = urllib.parse.quote(text)

    if share_via == 'whatsapp':
        share_url = f'https://api.whatsapp.com/send?text={encoded_text}'
    else:  # sms
        share_url = f'sms:?body={encoded_text}'

    return render(request, 'reports/share_redirect.html', {
        'share_url': share_url,
        'text': text,
        'via': share_via,
    })


def _generate_attendance_share_text(employee, month, year, month_name):
    """Generate attendance summary text for sharing."""
    records = Attendance.objects.filter(
        employee=employee, date__year=year, date__month=month
    )
    present = records.filter(status='present').count()
    absent = records.filter(status='absent').count()
    half_day = records.filter(status='half_day').count()
    casual = records.filter(status='casual_leave').count()

    text = (
        f"📋 *Attendance Report*\n"
        f"Employee: {employee.full_name} ({employee.employee_id})\n"
        f"Month: {month_name} {year}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ Present: {present} days\n"
        f"❌ Absent: {absent} days\n"
        f"🔶 Half Day: {half_day} days\n"
        f"🟡 Casual Leave: {casual} days\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Total Marked: {records.count()} days\n"
    )
    return text


def _generate_payroll_share_text(employee, month, year, month_name):
    """Generate payroll summary text for sharing."""
    try:
        record = PayrollRecord.objects.get(
            employee=employee, period__month=month, period__year=year
        )
        text = (
            f"💰 *Payroll Report*\n"
            f"Employee: {employee.full_name} ({employee.employee_id})\n"
            f"Month: {month_name} {year}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Base Salary: ₹{record.base_salary:,.2f}\n"
            f"Attendance Deduction: -₹{record.attendance_deduction:,.2f}\n"
            f"Advances: -₹{record.total_advances:,.2f}\n"
            f"Bonuses: +₹{record.bonuses:,.2f}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"*Net Salary: ₹{record.net_salary:,.2f}*\n"
            f"Status: {'✅ Paid' if record.is_paid else '⏳ Unpaid'}\n"
        )
    except PayrollRecord.DoesNotExist:
        text = f"No payroll record found for {employee.full_name} - {month_name} {year}"
    return text


def _generate_overall_attendance_share_text(month, year, month_name):
    """Generate overall attendance text."""
    employees = Employee.objects.filter(is_active=True)
    records = Attendance.objects.filter(date__year=year, date__month=month)
    text = (
        f"📋 *Overall Attendance Report*\n"
        f"Month: {month_name} {year}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Total Employees: {employees.count()}\n"
        f"Total Present: {records.filter(status='present').count()}\n"
        f"Total Absent: {records.filter(status='absent').count()}\n"
        f"Total Half Days: {records.filter(status='half_day').count()}\n"
        f"Total Casual Leave: {records.filter(status='casual_leave').count()}\n"
    )
    return text


def _generate_overall_payroll_share_text(month, year, month_name):
    """Generate overall payroll text."""
    records = PayrollRecord.objects.filter(
        period__month=month, period__year=year
    )
    total = records.aggregate(total=Sum('net_salary'))['total'] or 0
    paid = records.filter(is_paid=True).aggregate(total=Sum('net_salary'))['total'] or 0
    text = (
        f"💰 *Overall Payroll Report*\n"
        f"Month: {month_name} {year}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Total Records: {records.count()}\n"
        f"Total Salary: ₹{total:,.2f}\n"
        f"Paid: ₹{paid:,.2f}\n"
        f"Unpaid: ₹{total - paid:,.2f}\n"
    )
    return text


def _generate_individual_attendance_pdf(employee, month, year):
    """Generate individual attendance PDF."""
    from xhtml2pdf import pisa

    records = Attendance.objects.filter(
        employee=employee, date__year=year, date__month=month
    ).order_by('date')

    present = records.filter(status='present').count()
    absent = records.filter(status='absent').count()
    half_day = records.filter(status='half_day').count()
    casual = records.filter(status='casual_leave').count()

    html = render_to_string('reports/pdf_attendance_individual.html', {
        'employee': employee,
        'records': records,
        'month_name': calendar.month_name[month],
        'year': year,
        'present': present,
        'absent': absent,
        'half_day': half_day,
        'casual': casual,
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f'attendance_{employee.employee_id}_{month}_{year}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=response)
    return response


def _generate_overall_attendance_pdf(month, year):
    """Generate overall attendance PDF."""
    from xhtml2pdf import pisa

    employees = Employee.objects.filter(is_active=True)
    records = Attendance.objects.filter(date__year=year, date__month=month)

    employee_data = []
    for emp in employees:
        emp_records = records.filter(employee=emp)
        employee_data.append({
            'employee': emp,
            'present': emp_records.filter(status='present').count(),
            'absent': emp_records.filter(status='absent').count(),
            'half_day': emp_records.filter(status='half_day').count(),
            'casual': emp_records.filter(status='casual_leave').count(),
        })

    html = render_to_string('reports/pdf_attendance_overall.html', {
        'employee_data': employee_data,
        'month_name': calendar.month_name[month],
        'year': year,
        'total_employees': employees.count(),
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f'attendance_overall_{month}_{year}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=response)
    return response


def _generate_individual_payroll_pdf(employee, month, year):
    """Generate individual payroll PDF (payslip)."""
    from xhtml2pdf import pisa

    try:
        record = PayrollRecord.objects.get(
            employee=employee, period__month=month, period__year=year
        )
    except PayrollRecord.DoesNotExist:
        return HttpResponse('Payroll record not found.', status=404)

    advances = SalaryAdvance.objects.filter(
        employee=employee, date__year=year, date__month=month
    )

    html = render_to_string('reports/pdf_payroll_individual.html', {
        'record': record,
        'employee': employee,
        'advances': advances,
        'month_name': calendar.month_name[month],
        'year': year,
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f'payroll_{employee.employee_id}_{month}_{year}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=response)
    return response


def _generate_overall_payroll_pdf(month, year):
    """Generate overall payroll PDF."""
    from xhtml2pdf import pisa

    records = PayrollRecord.objects.filter(
        period__month=month, period__year=year
    ).select_related('employee')

    total = records.aggregate(total=Sum('net_salary'))['total'] or 0
    paid = records.filter(is_paid=True).aggregate(total=Sum('net_salary'))['total'] or 0

    html = render_to_string('reports/pdf_payroll_overall.html', {
        'records': records,
        'month_name': calendar.month_name[month],
        'year': year,
        'total': total,
        'paid': paid,
        'unpaid': total - paid,
    })

    response = HttpResponse(content_type='application/pdf')
    filename = f'payroll_overall_{month}_{year}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=response)
    return response
