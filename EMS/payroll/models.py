import calendar
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from employees.models import Employee


class PayrollPeriod(models.Model):
    """
    Represents a payroll cycle for a specific month/year.
    Acts as the batch container for all payroll records in that period.

    Status lifecycle: draft → finalized → paid
    - draft: payroll can be regenerated/modified
    - finalized: locked — no modifications allowed (except admin override with audit)
    - paid: all records marked as paid
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('finalized', 'Finalized'),
        ('paid', 'Paid'),
    ]

    month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text='Payroll month (1-12)'
    )
    year = models.IntegerField(
        validators=[MinValueValidator(2020)],
        help_text='Payroll year'
    )
    total_working_days = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text='Total working days in this period (excluding weekly off and holidays)'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='draft',
        help_text='Period status: draft → finalized → paid'
    )
    notes = models.TextField(
        blank=True,
        help_text='Optional notes about this payroll period'
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_periods',
        help_text='User who generated this payroll period'
    )
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finalized_periods',
        help_text='User who finalized this period'
    )
    finalized_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this period was finalized'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payroll Period'
        verbose_name_plural = 'Payroll Periods'
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(
                fields=['month', 'year'],
                name='unique_payroll_period'
            ),
            models.CheckConstraint(
                condition=models.Q(month__gte=1, month__lte=12),
                name='valid_payroll_month'
            ),
            models.CheckConstraint(
                condition=models.Q(year__gte=2020),
                name='valid_payroll_year'
            ),
            models.CheckConstraint(
                condition=models.Q(total_working_days__gte=0),
                name='non_negative_working_days'
            ),
        ]

    def __str__(self):
        return f"{self.get_month_display()} {self.year} ({self.get_status_display()})"

    def get_month_display(self):
        """Return month name."""
        return calendar.month_name[self.month]

    @property
    def is_draft(self):
        return self.status == 'draft'

    @property
    def is_finalized(self):
        return self.status == 'finalized'

    @property
    def is_paid(self):
        return self.status == 'paid'

    @property
    def can_modify(self):
        """Only draft periods allow modifications."""
        return self.status == 'draft'

    @property
    def record_count(self):
        return self.payroll_records.count()

    @property
    def total_net_salary(self):
        from django.db.models import Sum
        return self.payroll_records.aggregate(
            total=Sum('net_salary')
        )['total'] or Decimal('0')

    @property
    def total_paid_salary(self):
        from django.db.models import Sum
        return self.payroll_records.filter(is_paid=True).aggregate(
            total=Sum('net_salary')
        )['total'] or Decimal('0')

    @property
    def total_unpaid_salary(self):
        return self.total_net_salary - self.total_paid_salary


class PayrollRecord(models.Model):
    """
    Monthly payroll record for a single employee within a PayrollPeriod.
    Contains denormalized summary fields for quick access, while
    PayrollLineItems provide the full itemized breakdown.

    Calculation flow:
    1. daily_rate = base_salary / total_working_days
    2. attendance_deduction = (days_absent * daily_rate) + (half_days * daily_rate * 0.5)
    3. gross_earnings = base_salary + bonuses
    4. total_deductions = attendance_deduction + total_advances + other_deductions
    5. net_salary = gross_earnings - total_deductions
    """
    period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.CASCADE,
        related_name='payroll_records',
        help_text='The payroll period this record belongs to'
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        related_name='payroll_records',
        help_text='Employee this payroll record belongs to'
    )

    # Salary snapshot at generation time
    base_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Base salary snapshot at time of payroll generation'
    )

    # Attendance snapshot
    total_working_days = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text='Working days in this period'
    )
    days_present = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Days marked present'
    )
    days_absent = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Days marked absent'
    )
    half_days = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Days marked half day'
    )
    casual_leaves = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Days marked casual leave'
    )

    # Calculated salary fields (denormalized for query performance)
    daily_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        help_text='Per-day salary (base_salary / working_days)'
    )
    attendance_deduction = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Total deduction based on absent and half days'
    )
    total_advances = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Total salary advances deducted'
    )
    bonuses = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Total bonus amount'
    )
    other_deductions = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Any other deductions'
    )
    gross_earnings = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        help_text='Total earnings (base_salary + bonuses)'
    )
    total_deductions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Total deductions (attendance + advances + other)'
    )
    net_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Final salary after all deductions and additions'
    )

    # Modification tracking
    salary_modified = models.BooleanField(
        default=False,
        help_text='Whether salary was manually modified after generation'
    )
    modification_note = models.TextField(
        blank=True,
        help_text='Reason for salary modification'
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_payrolls',
        help_text='Admin who last modified the salary'
    )

    # Payment tracking
    is_paid = models.BooleanField(
        default=False,
        help_text='Whether salary has been paid'
    )
    paid_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date when salary was paid'
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paid_payrolls',
        help_text='User who marked this as paid'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payroll Record'
        verbose_name_plural = 'Payroll Records'
        ordering = ['-period__year', '-period__month', 'employee__employee_id']
        constraints = [
            models.UniqueConstraint(
                fields=['period', 'employee'],
                name='unique_employee_per_period'
            ),
            models.CheckConstraint(
                condition=models.Q(base_salary__gte=0),
                name='non_negative_base_salary'
            ),
            models.CheckConstraint(
                condition=models.Q(days_present__gte=0),
                name='non_negative_days_present'
            ),
            models.CheckConstraint(
                condition=models.Q(days_absent__gte=0),
                name='non_negative_days_absent'
            ),
            models.CheckConstraint(
                condition=models.Q(half_days__gte=0),
                name='non_negative_half_days'
            ),
            models.CheckConstraint(
                condition=models.Q(total_deductions__gte=0),
                name='non_negative_total_deductions'
            ),
        ]

    def __str__(self):
        return (
            f"{self.employee.full_name} — "
            f"{self.period.get_month_display()}/{self.period.year} — "
            f"₹{self.net_salary}"
        )

    def get_month_display(self):
        """Return month name from the parent period."""
        return self.period.get_month_display()

    def calculate_salary(self):
        """
        Calculate all salary fields based on current values.
        Does NOT save — caller is responsible for saving within a transaction.
        """
        # Daily rate
        if self.total_working_days > 0:
            self.daily_rate = self.base_salary / Decimal(self.total_working_days)
        else:
            self.daily_rate = Decimal('0')

        # Attendance deduction
        absent_deduction = Decimal(self.days_absent) * self.daily_rate
        halfday_deduction = Decimal(self.half_days) * self.daily_rate * Decimal('0.5')
        self.attendance_deduction = absent_deduction + halfday_deduction

        # Gross earnings
        self.gross_earnings = self.base_salary + self.bonuses

        # Total deductions
        self.total_deductions = (
            self.attendance_deduction
            + self.total_advances
            + self.other_deductions
        )

        # Net salary (floor at 0 to prevent negative payroll)
        self.net_salary = max(
            self.gross_earnings - self.total_deductions,
            Decimal('0')
        )
        return self.net_salary

    @property
    def effective_days_worked(self):
        """Total effective working days (present + half of half-days)."""
        return Decimal(self.days_present) + (Decimal(self.half_days) * Decimal('0.5'))

    @property
    def payable_salary(self):
        """Salary payable based on attendance (before advance deductions)."""
        return self.base_salary - self.attendance_deduction

    @property
    def month(self):
        """Convenience: month from period."""
        return self.period.month

    @property
    def year(self):
        """Convenience: year from period."""
        return self.period.year


class PayrollLineItem(models.Model):
    """
    Itemized breakdown of a payroll record's earnings and deductions.
    Provides full transparency into how net_salary was computed.

    Each line item represents a single earning or deduction with its
    amount and a reference back to the source (e.g., advance PK).
    """
    CATEGORY_CHOICES = [
        ('earning', 'Earning'),
        ('deduction', 'Deduction'),
    ]
    ITEM_TYPE_CHOICES = [
        ('base_salary', 'Base Salary'),
        ('bonus', 'Bonus'),
        ('attendance_deduction', 'Attendance Deduction'),
        ('advance_deduction', 'Advance Deduction'),
        ('other_earning', 'Other Earning'),
        ('other_deduction', 'Other Deduction'),
    ]

    payroll_record = models.ForeignKey(
        PayrollRecord,
        on_delete=models.CASCADE,
        related_name='line_items',
        help_text='Parent payroll record'
    )
    category = models.CharField(
        max_length=10,
        choices=CATEGORY_CHOICES,
        help_text='Whether this is an earning or deduction'
    )
    item_type = models.CharField(
        max_length=25,
        choices=ITEM_TYPE_CHOICES,
        help_text='Type of line item'
    )
    description = models.CharField(
        max_length=255,
        help_text='Human-readable description'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Line item amount (always positive)'
    )
    reference_id = models.IntegerField(
        null=True,
        blank=True,
        help_text='Optional reference to source record PK (e.g., SalaryAdvance PK)'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Payroll Line Item'
        verbose_name_plural = 'Payroll Line Items'
        ordering = ['category', 'item_type']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='positive_line_item_amount'
            ),
        ]

    def __str__(self):
        sign = '+' if self.category == 'earning' else '-'
        return f"{sign}₹{self.amount} — {self.description}"


class SalaryAdvance(models.Model):
    """
    Tracks salary advances (money borrowed by employees mid-month).
    Enhanced with status tracking to prevent double-deduction.

    Status lifecycle: pending → deducted (or cancelled)
    - pending: advance recorded but not yet deducted from any payroll
    - deducted: advance has been deducted from a payroll record
    - cancelled: advance was cancelled (not deducted)
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('deducted', 'Deducted'),
        ('cancelled', 'Cancelled'),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='salary_advances',
        help_text='Employee who took the advance'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Amount of advance taken'
    )
    date = models.DateField(
        help_text='Date when advance was taken'
    )
    reason = models.TextField(
        blank=True,
        help_text='Reason for advance'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        help_text='Advance status: pending → deducted or cancelled'
    )
    deducted_in = models.ForeignKey(
        PayrollRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deducted_advances',
        help_text='Payroll record this advance was deducted in'
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_advances',
        help_text='User who recorded this advance'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Salary Advance'
        verbose_name_plural = 'Salary Advances'
        ordering = ['-date']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='positive_advance_amount'
            ),
        ]

    def __str__(self):
        return f"{self.employee.full_name} — ₹{self.amount} on {self.date} ({self.get_status_display()})"


class PayrollAuditLog(models.Model):
    """
    Immutable audit trail for every payroll mutation.
    Records who did what, when, and captures before/after state.
    """
    ACTION_CHOICES = [
        ('generated', 'Payroll Generated'),
        ('regenerated', 'Payroll Regenerated'),
        ('modified', 'Record Modified'),
        ('finalized', 'Period Finalized'),
        ('paid', 'Record Marked Paid'),
        ('unpaid', 'Record Marked Unpaid'),
        ('batch_paid', 'Period Batch Paid'),
        ('advance_added', 'Advance Added'),
        ('advance_edited', 'Advance Edited'),
        ('advance_deleted', 'Advance Deleted'),
        ('advance_cancelled', 'Advance Cancelled'),
    ]

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        help_text='Type of action performed'
    )
    period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text='Related payroll period'
    )
    payroll_record = models.ForeignKey(
        PayrollRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text='Related payroll record'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payroll_audit_logs',
        help_text='User who performed the action'
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text='Snapshot of changes — old/new values, affected employees, etc.'
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text='When the action was performed'
    )

    class Meta:
        verbose_name = 'Payroll Audit Log'
        verbose_name_plural = 'Payroll Audit Logs'
        ordering = ['-timestamp']

    def __str__(self):
        user_str = self.user.get_full_name() if self.user else 'System'
        return f"{self.get_action_display()} by {user_str} at {self.timestamp}"
