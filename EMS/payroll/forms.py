from django import forms
from django.utils import timezone
from .models import PayrollRecord, SalaryAdvance, PayrollPeriod
from employees.models import Employee


class GeneratePayrollForm(forms.Form):
    """Form for generating payroll for a specific month/year."""
    month = forms.IntegerField(
        min_value=1,
        max_value=12,
        widget=forms.Select(
            choices=[
                (1, 'January'), (2, 'February'), (3, 'March'),
                (4, 'April'), (5, 'May'), (6, 'June'),
                (7, 'July'), (8, 'August'), (9, 'September'),
                (10, 'October'), (11, 'November'), (12, 'December'),
            ],
            attrs={'class': 'form-select', 'id': 'payrollMonth'}
        )
    )
    year = forms.IntegerField(
        min_value=2020,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Year',
            'id': 'payrollYear',
        })
    )

    def clean(self):
        cleaned = super().clean()
        month = cleaned.get('month')
        year = cleaned.get('year')

        if month and year:
            # Check if a finalized/paid period already exists
            existing = PayrollPeriod.objects.filter(month=month, year=year).first()
            if existing and not existing.can_modify:
                raise forms.ValidationError(
                    f"Payroll for {existing.get_month_display()} {year} is already "
                    f"{existing.get_status_display()} and cannot be regenerated."
                )

        return cleaned


class ModifyPayrollForm(forms.ModelForm):
    """Form for admin to modify an employee's salary in a payroll record."""
    class Meta:
        model = PayrollRecord
        fields = ['base_salary', 'bonuses', 'total_advances', 'other_deductions', 'modification_note']
        widgets = {
            'base_salary': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'id': 'modifyBaseSalary',
            }),
            'bonuses': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'placeholder': '0.00',
                'id': 'modifyBonuses',
            }),
            'total_advances': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'placeholder': '0.00',
                'id': 'modifyAdvances',
            }),
            'other_deductions': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'placeholder': '0.00',
                'id': 'modifyOtherDeductions',
            }),
            'modification_note': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Reason for salary modification (required)',
                'id': 'modifyNote',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['modification_note'].required = True
        self.fields['modification_note'].help_text = (
            'A reason is required for audit purposes.'
        )


class SalaryAdvanceForm(forms.ModelForm):
    """Form for recording or editing a salary advance."""
    class Meta:
        model = SalaryAdvance
        fields = ['employee', 'amount', 'date', 'reason']
        widgets = {
            'employee': forms.Select(attrs={
                'class': 'form-select',
                'id': 'advanceEmployee',
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.01',
                'placeholder': 'Enter advance amount',
                'id': 'advanceAmount',
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
                'id': 'advanceDate',
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 2,
                'placeholder': 'Reason for advance (optional)',
                'id': 'advanceReason',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('Amount must be positive.')
        return amount


class PayrollFilterForm(forms.Form):
    """Form for filtering payroll records."""
    month = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=12,
        widget=forms.Select(
            choices=[('', 'All Months')] + [
                (i, name) for i, name in enumerate(
                    ['', 'January', 'February', 'March', 'April', 'May', 'June',
                     'July', 'August', 'September', 'October', 'November', 'December']
                ) if i > 0
            ],
            attrs={'class': 'form-select', 'id': 'filterMonth'}
        )
    )
    year = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Year',
            'id': 'filterYear',
        })
    )
    employee = forms.ModelChoiceField(
        required=False,
        queryset=Employee.objects.filter(is_active=True),
        empty_label='All Employees',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'filterEmployee',
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All'), ('paid', 'Paid'), ('unpaid', 'Unpaid')],
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'filterStatus',
        })
    )
