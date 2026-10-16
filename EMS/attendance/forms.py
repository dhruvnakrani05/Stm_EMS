from django import forms
from .models import Attendance, Holiday
from employees.models import Employee


class AttendanceForm(forms.ModelForm):
    """Form for marking individual employee attendance."""
    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'status', 'check_in', 'check_out', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'check_in': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'check_out': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Optional notes'}),
        }


class BulkAttendanceForm(forms.Form):
    """
    Dynamic form for marking attendance for all active employees at once.
    """
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        employees = kwargs.pop('employees', Employee.objects.filter(is_active=True))
        super().__init__(*args, **kwargs)

        for emp in employees:
            self.fields[f'status_{emp.id}'] = forms.ChoiceField(
                choices=Attendance.STATUS_CHOICES,
                initial='present',
                widget=forms.Select(attrs={
                    'class': 'form-select attendance-select',
                    'data-employee-id': emp.id,
                }),
                label=f'{emp.employee_id} - {emp.full_name}'
            )
            self.fields[f'notes_{emp.id}'] = forms.CharField(
                required=False,
                widget=forms.TextInput(attrs={
                    'class': 'form-input',
                    'placeholder': 'Notes (optional)',
                }),
                label=''
            )


class AttendanceDateFilterForm(forms.Form):
    """Filter form for attendance views."""
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
    )
    month = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=12,
        widget=forms.Select(
            choices=[(i, i) for i in range(1, 13)],
            attrs={'class': 'form-select'}
        )
    )
    year = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Year'})
    )


class HolidayForm(forms.ModelForm):
    """Form for adding holidays."""
    class Meta:
        model = Holiday
        fields = ['date', 'name', 'holiday_type']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Holiday name'}),
            'holiday_type': forms.Select(attrs={'class': 'form-select'}),
        }
