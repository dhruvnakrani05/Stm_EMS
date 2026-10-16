import calendar
from datetime import date
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.conf import settings
from django.utils import timezone

from employees.models import Employee
from attendance.models import Attendance, Holiday
from .models import (
    PayrollPeriod,
    PayrollRecord,
    PayrollLineItem,
    SalaryAdvance,
    PayrollAuditLog,
)


class PayrollServiceError(Exception):
    """Base exception for payroll service errors."""
    pass


class PeriodLockedError(PayrollServiceError):
    """Raised when trying to modify a finalized/paid period."""
    pass


class PayrollService:
    """
    Service layer encapsulating all payroll business logic.
    Every write method is wrapped in @transaction.atomic to ensure
    ACID compliance — either everything succeeds or nothing changes.
    """

    # ─── Working Days Calculation ──────────────────────────────────────

    @staticmethod
    def calculate_working_days(year, month):
        """
        Calculate working days for a given month, excluding:
        - Weekly off days (configured in settings.WEEKLY_OFF_DAY)
        - Non-weekly holidays from the Holiday model
        """
        num_days = calendar.monthrange(year, month)[1]

        weekly_off_day = getattr(settings, 'WEEKLY_OFF_DAY', 3)  # Default Thursday
        weekly_offs = sum(
            1 for d in range(1, num_days + 1)
            if date(year, month, d).weekday() == weekly_off_day
        )

        holidays_count = Holiday.objects.filter(
            date__year=year,
            date__month=month
        ).exclude(holiday_type='weekly').count()

        return num_days - weekly_offs - holidays_count

    # ─── Attendance Snapshot ───────────────────────────────────────────

    @staticmethod
    def _get_attendance_snapshot(employee, year, month):
        """
        Get attendance counts for an employee in a given month.
        Returns a dict with present, absent, half_day, and casual_leave counts.
        """
        records = Attendance.objects.filter(
            employee=employee,
            date__year=year,
            date__month=month
        )
        return {
            'days_present': records.filter(status='present').count(),
            'days_absent': records.filter(status='absent').count(),
            'half_days': records.filter(status='half_day').count(),
            'casual_leaves': records.filter(status='casual_leave').count(),
        }

    # ─── Payroll Generation ────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def generate_payroll(month, year, generated_by):
        """
        Atomically generate payroll for ALL active employees for a given month/year.

        Process:
        1. Create or retrieve PayrollPeriod (must be in 'draft' status)
        2. Calculate working days
        3. For each active employee:
           a. Snapshot attendance data
           b. Sum pending salary advances
           c. Create PayrollRecord with calculated salary
           d. Create PayrollLineItems for transparency
           e. Mark advances as 'deducted'
        4. Log the action in PayrollAuditLog

        Returns a summary dict with counts of generated/updated/skipped.
        """
        # 1. Get or create period
        period, period_created = PayrollPeriod.objects.select_for_update().get_or_create(
            month=month,
            year=year,
            defaults={
                'total_working_days': PayrollService.calculate_working_days(year, month),
                'generated_by': generated_by,
            }
        )

        if not period.can_modify:
            raise PeriodLockedError(
                f"Payroll period {period.get_month_display()} {period.year} is "
                f"{period.get_status_display()} and cannot be modified."
            )

        # Update working days if period already existed
        if not period_created:
            period.total_working_days = PayrollService.calculate_working_days(year, month)
            period.save(update_fields=['total_working_days', 'updated_at'])

        working_days = period.total_working_days

        # 2. Get all active employees
        employees = Employee.objects.filter(is_active=True).select_for_update()

        generated = 0
        updated = 0
        skipped = 0
        affected_employees = []

        for emp in employees:
            # Get attendance snapshot
            att = PayrollService._get_attendance_snapshot(emp, year, month)

            # Get pending advances for this employee in this month
            pending_advances = SalaryAdvance.objects.select_for_update().filter(
                employee=emp,
                date__year=year,
                date__month=month,
                status='pending'
            )
            total_advances = pending_advances.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0')

            # Check for existing record
            existing = PayrollRecord.objects.filter(
                period=period,
                employee=emp
            ).first()

            if existing:
                # Skip manually modified records to preserve admin overrides
                if existing.salary_modified:
                    skipped += 1
                    continue

                # Unlink previously deducted advances so they can be re-evaluated
                SalaryAdvance.objects.filter(
                    deducted_in=existing,
                    status='deducted'
                ).update(status='pending', deducted_in=None)

                # Delete old line items
                existing.line_items.all().delete()

                # Update fields
                existing.base_salary = emp.basic_salary
                existing.total_working_days = working_days
                existing.days_present = att['days_present']
                existing.days_absent = att['days_absent']
                existing.half_days = att['half_days']
                existing.casual_leaves = att['casual_leaves']
                existing.total_advances = total_advances
                existing.calculate_salary()
                existing.save()

                record = existing
                updated += 1
            else:
                # Create new payroll record
                record = PayrollRecord(
                    period=period,
                    employee=emp,
                    base_salary=emp.basic_salary,
                    total_working_days=working_days,
                    days_present=att['days_present'],
                    days_absent=att['days_absent'],
                    half_days=att['half_days'],
                    casual_leaves=att['casual_leaves'],
                    total_advances=total_advances,
                    net_salary=Decimal('0'),  # Will be calculated
                )
                record.calculate_salary()
                record.save()
                generated += 1

            # Create line items for transparency
            PayrollService._create_line_items(record, pending_advances)

            # Mark advances as deducted
            pending_advances.update(status='deducted', deducted_in=record)

            affected_employees.append({
                'id': emp.employee_id,
                'name': emp.full_name,
                'net_salary': str(record.net_salary),
            })

        # Audit log
        action = 'generated' if period_created else 'regenerated'
        PayrollAuditLog.objects.create(
            action=action,
            period=period,
            user=generated_by,
            details={
                'generated': generated,
                'updated': updated,
                'skipped': skipped,
                'working_days': working_days,
                'employees': affected_employees,
            }
        )

        return {
            'period': period,
            'generated': generated,
            'updated': updated,
            'skipped': skipped,
        }

    @staticmethod
    def _create_line_items(record, advances_qs):
        """Create PayrollLineItems for a payroll record."""
        items = []

        # Earning: Base salary
        items.append(PayrollLineItem(
            payroll_record=record,
            category='earning',
            item_type='base_salary',
            description=f'Base Salary ({record.total_working_days} working days)',
            amount=record.base_salary,
        ))

        # Earning: Bonus (if any)
        if record.bonuses > 0:
            items.append(PayrollLineItem(
                payroll_record=record,
                category='earning',
                item_type='bonus',
                description='Bonus',
                amount=record.bonuses,
            ))

        # Deduction: Attendance
        if record.attendance_deduction > 0:
            items.append(PayrollLineItem(
                payroll_record=record,
                category='deduction',
                item_type='attendance_deduction',
                description=(
                    f'Attendance Deduction ({record.days_absent} absent, '
                    f'{record.half_days} half days)'
                ),
                amount=record.attendance_deduction,
            ))

        # Deduction: Individual advances
        for adv in advances_qs:
            items.append(PayrollLineItem(
                payroll_record=record,
                category='deduction',
                item_type='advance_deduction',
                description=f'Salary Advance on {adv.date.strftime("%d %b %Y")}',
                amount=adv.amount,
                reference_id=adv.pk,
            ))

        # Deduction: Other deductions
        if record.other_deductions > 0:
            items.append(PayrollLineItem(
                payroll_record=record,
                category='deduction',
                item_type='other_deduction',
                description='Other Deductions',
                amount=record.other_deductions,
            ))

        PayrollLineItem.objects.bulk_create(items)

    # ─── Modify Record ─────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def modify_record(record_pk, modified_by, base_salary=None, bonuses=None,
                      total_advances=None, other_deductions=None, modification_note=''):
        """
        Modify a payroll record with full audit trail.
        Only allowed on draft periods.
        """
        record = PayrollRecord.objects.select_for_update().select_related(
            'period'
        ).get(pk=record_pk)

        if not record.period.can_modify:
            raise PeriodLockedError(
                f"Cannot modify record — period is {record.period.get_status_display()}."
            )

        # Capture old values for audit
        old_values = {
            'base_salary': str(record.base_salary),
            'bonuses': str(record.bonuses),
            'total_advances': str(record.total_advances),
            'other_deductions': str(record.other_deductions),
            'net_salary': str(record.net_salary),
        }

        # Apply changes
        if base_salary is not None:
            record.base_salary = base_salary
        if bonuses is not None:
            record.bonuses = bonuses
        if total_advances is not None:
            record.total_advances = total_advances
        if other_deductions is not None:
            record.other_deductions = other_deductions

        record.calculate_salary()
        record.salary_modified = True
        record.modification_note = modification_note
        record.modified_by = modified_by
        record.save()

        # Rebuild line items
        record.line_items.all().delete()
        advances_qs = SalaryAdvance.objects.filter(deducted_in=record)
        PayrollService._create_line_items(record, advances_qs)

        # Audit log
        new_values = {
            'base_salary': str(record.base_salary),
            'bonuses': str(record.bonuses),
            'total_advances': str(record.total_advances),
            'other_deductions': str(record.other_deductions),
            'net_salary': str(record.net_salary),
        }
        PayrollAuditLog.objects.create(
            action='modified',
            period=record.period,
            payroll_record=record,
            user=modified_by,
            details={
                'employee': record.employee.full_name,
                'employee_id': record.employee.employee_id,
                'old_values': old_values,
                'new_values': new_values,
                'note': modification_note,
            }
        )

        return record

    # ─── Finalize Period ───────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def finalize_period(period_pk, finalized_by):
        """
        Finalize a payroll period — locks it from further modifications.
        Only draft periods can be finalized.
        """
        period = PayrollPeriod.objects.select_for_update().get(pk=period_pk)

        if not period.is_draft:
            raise PayrollServiceError(
                f"Period is already {period.get_status_display()}. "
                f"Only draft periods can be finalized."
            )

        if period.record_count == 0:
            raise PayrollServiceError(
                "Cannot finalize a period with no payroll records."
            )

        period.status = 'finalized'
        period.finalized_by = finalized_by
        period.finalized_at = timezone.now()
        period.save(update_fields=['status', 'finalized_by', 'finalized_at', 'updated_at'])

        PayrollAuditLog.objects.create(
            action='finalized',
            period=period,
            user=finalized_by,
            details={
                'record_count': period.record_count,
                'total_net_salary': str(period.total_net_salary),
            }
        )

        return period

    # ─── Payment Management ────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def mark_paid(record_pk, paid_by):
        """Mark a single payroll record as paid."""
        record = PayrollRecord.objects.select_for_update().select_related(
            'period', 'employee'
        ).get(pk=record_pk)

        record.is_paid = True
        record.paid_date = timezone.now().date()
        record.paid_by = paid_by
        record.save(update_fields=['is_paid', 'paid_date', 'paid_by', 'updated_at'])

        PayrollAuditLog.objects.create(
            action='paid',
            period=record.period,
            payroll_record=record,
            user=paid_by,
            details={
                'employee': record.employee.full_name,
                'net_salary': str(record.net_salary),
                'paid_date': str(record.paid_date),
            }
        )

        # Check if all records in the period are now paid
        unpaid_count = record.period.payroll_records.filter(is_paid=False).count()
        if unpaid_count == 0:
            record.period.status = 'paid'
            record.period.save(update_fields=['status', 'updated_at'])

        return record

    @staticmethod
    @transaction.atomic
    def mark_unpaid(record_pk, user):
        """Mark a single payroll record as unpaid."""
        record = PayrollRecord.objects.select_for_update().select_related(
            'period', 'employee'
        ).get(pk=record_pk)

        record.is_paid = False
        record.paid_date = None
        record.paid_by = None
        record.save(update_fields=['is_paid', 'paid_date', 'paid_by', 'updated_at'])

        # If period was marked as 'paid', revert to 'finalized'
        if record.period.status == 'paid':
            record.period.status = 'finalized'
            record.period.save(update_fields=['status', 'updated_at'])

        PayrollAuditLog.objects.create(
            action='unpaid',
            period=record.period,
            payroll_record=record,
            user=user,
            details={
                'employee': record.employee.full_name,
                'net_salary': str(record.net_salary),
            }
        )

        return record

    @staticmethod
    @transaction.atomic
    def mark_period_paid(period_pk, paid_by):
        """Batch-mark all unpaid records in a period as paid."""
        period = PayrollPeriod.objects.select_for_update().get(pk=period_pk)

        today = timezone.now().date()
        unpaid_records = period.payroll_records.select_for_update().filter(is_paid=False)
        count = unpaid_records.count()

        if count == 0:
            raise PayrollServiceError("All records are already paid.")

        unpaid_records.update(
            is_paid=True,
            paid_date=today,
            paid_by=paid_by,
        )

        period.status = 'paid'
        period.save(update_fields=['status', 'updated_at'])

        PayrollAuditLog.objects.create(
            action='batch_paid',
            period=period,
            user=paid_by,
            details={
                'records_paid': count,
                'paid_date': str(today),
                'total_amount': str(period.total_net_salary),
            }
        )

        return count

    # ─── Salary Advance Management ─────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def add_advance(employee_pk, amount, advance_date, reason, added_by):
        """Record a new salary advance with validation."""
        employee = Employee.objects.get(pk=employee_pk)

        if amount <= 0:
            raise PayrollServiceError("Advance amount must be positive.")

        advance = SalaryAdvance.objects.create(
            employee=employee,
            amount=amount,
            date=advance_date,
            reason=reason,
            status='pending',
            added_by=added_by,
        )

        PayrollAuditLog.objects.create(
            action='advance_added',
            user=added_by,
            details={
                'employee': employee.full_name,
                'employee_id': employee.employee_id,
                'amount': str(amount),
                'date': str(advance_date),
                'reason': reason,
                'advance_pk': advance.pk,
            }
        )

        return advance

    @staticmethod
    @transaction.atomic
    def edit_advance(advance_pk, amount, advance_date, reason, edited_by):
        """Edit a salary advance. Only pending advances can be edited."""
        advance = SalaryAdvance.objects.select_for_update().get(pk=advance_pk)

        if advance.status != 'pending':
            raise PayrollServiceError(
                f"Cannot edit advance — status is '{advance.get_status_display()}'."
            )

        old_values = {
            'amount': str(advance.amount),
            'date': str(advance.date),
            'reason': advance.reason,
        }

        advance.amount = amount
        advance.date = advance_date
        advance.reason = reason
        advance.added_by = edited_by
        advance.save()

        PayrollAuditLog.objects.create(
            action='advance_edited',
            user=edited_by,
            details={
                'employee': advance.employee.full_name,
                'advance_pk': advance.pk,
                'old_values': old_values,
                'new_values': {
                    'amount': str(amount),
                    'date': str(advance_date),
                    'reason': reason,
                },
            }
        )

        return advance

    @staticmethod
    @transaction.atomic
    def delete_advance(advance_pk, deleted_by):
        """Delete a salary advance. Only pending advances can be deleted."""
        advance = SalaryAdvance.objects.select_for_update().select_related(
            'employee'
        ).get(pk=advance_pk)

        if advance.status == 'deducted':
            raise PayrollServiceError(
                "Cannot delete a deducted advance. Cancel it instead."
            )

        details = {
            'employee': advance.employee.full_name,
            'amount': str(advance.amount),
            'date': str(advance.date),
            'reason': advance.reason,
        }

        advance.delete()

        PayrollAuditLog.objects.create(
            action='advance_deleted',
            user=deleted_by,
            details=details,
        )

    @staticmethod
    @transaction.atomic
    def cancel_advance(advance_pk, cancelled_by):
        """
        Cancel a deducted advance. This does NOT automatically recalculate
        the payroll — the admin should regenerate payroll afterwards.
        """
        advance = SalaryAdvance.objects.select_for_update().select_related(
            'employee'
        ).get(pk=advance_pk)

        advance.status = 'cancelled'
        advance.deducted_in = None
        advance.save(update_fields=['status', 'deducted_in', 'updated_at'])

        PayrollAuditLog.objects.create(
            action='advance_cancelled',
            user=cancelled_by,
            details={
                'employee': advance.employee.full_name,
                'amount': str(advance.amount),
                'date': str(advance.date),
            }
        )

        return advance
