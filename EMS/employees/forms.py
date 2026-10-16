from django import forms
from .models import Employee
import re

class EmployeeForm(forms.ModelForm):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Auto-generate Employee ID only while creating
        if not self.instance.pk:
            last_employee = Employee.objects.order_by('-id').first()
            if last_employee and last_employee.employee_id:
                match = re.search(r'(\d+)$', last_employee.employee_id)
                if match:
                    next_id = int(match.group(1)) + 1
                else:
                    next_id = 1
            else:
                next_id = 1
            self.fields['employee_id'].initial = f"EMP{next_id:03d}"

        # Make Employee ID read-only
        self.fields['employee_id'].widget.attrs['readonly'] = True
    """
    Employee form with fields in the requested sequential order:
    Surname, Name, City, Mobile Number, Date of Joining, 
    Profile Photo, Employee ID, Basic Salary
    """
    class Meta:
        model = Employee
        fields = [
            'surname', 'name', 'city', 'mobile_number',
            'date_of_joining', 'profile_photo', 'employee_id',
            'basic_salary', 'email', 'is_active',
        ]
        widgets = {
            'surname': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter surname'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter first name'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter city'
            }),
            'mobile_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter mobile number',
                'maxlength': '10',
                'inputmode': 'numeric',
                'pattern': '[0-9]{10}',
            }),
            'date_of_joining': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'profile_photo': forms.ClearableFileInput(attrs={
                'class': 'form-file',
                'accept': 'image/*'
            }),
            'employee_id': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., EMP001'
            }),
            'basic_salary': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter basic salary',
                'step': '0.01'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter email (optional)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),
        }

        def clean_mobile_number(self):
            mobile = self.cleaned_data.get('mobile_number', '')

            mobile = mobile.replace(" ", "").replace("-", "")

            if not mobile.isdigit():
                raise forms.ValidationError(
                "Mobile number must contain only digits."
            )

            if len(mobile) != 10:
                raise forms.ValidationError(
            "Mobile number must be exactly 10 digits."
            )

            return mobile

    def clean_basic_salary(self):
        salary = self.cleaned_data.get('basic_salary')
        if salary and salary <= 0:
            raise forms.ValidationError('Salary must be a positive amount.')
        return salary


class EmployeeSearchForm(forms.Form):
    """Form for searching and filtering employees."""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input search-input',
            'placeholder': 'Search by name, ID, or city...',
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Status'), ('active', 'Active'), ('inactive', 'Inactive')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
