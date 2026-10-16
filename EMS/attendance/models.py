from django.db import models
from django.conf import settings
from employees.models import Employee


class Holiday(models.Model):
    """
    Tracks holidays - both weekly offs (Thursdays) and 
    festival/cultural holidays.
    """
    HOLIDAY_TYPE_CHOICES = [
        ('weekly', 'Weekly Off'),       # Thursdays
        ('festival', 'Festival'),       # Festival holidays
        ('cultural', 'Cultural'),       # Cultural holidays
    ]
    date = models.DateField(unique=True, help_text='Date of the holiday')
    name = models.CharField(max_length=100, help_text='Name of the holiday')
    holiday_type = models.CharField(
        max_length=10,
        choices=HOLIDAY_TYPE_CHOICES,
        default='festival',
        help_text='Type of holiday'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Holiday'
        verbose_name_plural = 'Holidays'
        ordering = ['date']

    def __str__(self):
        return f"{self.name} ({self.date})"


class Attendance(models.Model):
    """
    Daily attendance record for each employee.
    Status: Present, Absent, Half Day, or Casual Leave.
    """
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('half_day', 'Half Day'),
        ('casual_leave', 'Casual Leave'),
    ]
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='attendances',
        help_text='Employee this attendance belongs to'
    )
    date = models.DateField(help_text='Date of attendance')
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='present',
        help_text='Attendance status'
    )
    check_in = models.TimeField(null=True, blank=True, help_text='Check-in time')
    check_out = models.TimeField(null=True, blank=True, help_text='Check-out time')
    notes = models.TextField(blank=True, help_text='Additional notes')
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='User who marked this attendance'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendance Records'
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee__employee_id']

    def __str__(self):
        return f"{self.employee.full_name} - {self.date} - {self.get_status_display()}"

    @property
    def status_color(self):
        """Return CSS color class for status."""
        colors = {
            'present': 'status-present',
            'absent': 'status-absent',
            'half_day': 'status-halfday',
            'casual_leave': 'status-casual',
        }
        return colors.get(self.status, '')
