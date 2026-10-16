from django.db import models


class Employee(models.Model):
    """
    Employee model with fields ordered as requested:
    Surname, Name, City, Mobile Number, Date of Joining, 
    Profile Photo, Employee ID, Basic Salary
    """
    # Fields in the requested sequential order
    surname = models.CharField(max_length=50, help_text='Employee surname / last name')
    name = models.CharField(max_length=50, help_text='Employee first name')
    city = models.CharField(max_length=100, help_text='City of residence')
    mobile_number = models.CharField(max_length=15, help_text='Primary mobile number')
    date_of_joining = models.DateField(help_text='Date when the employee joined')
    profile_photo = models.ImageField(
        upload_to='profiles/%Y/%m/',
        blank=True,
        null=True,
        help_text='Employee profile photo'
    )
    employee_id = models.CharField(
        max_length=20,
        unique=True,
        help_text='Unique employee identifier (e.g., EMP001)'
    )
    basic_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Monthly base salary amount'
    )

    # Additional system fields
    email = models.EmailField(blank=True, help_text='Email address (optional)')
    is_active = models.BooleanField(default=True, help_text='Whether employee is currently active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        ordering = ['employee_id']

    def __str__(self):
        return f"{self.employee_id} - {self.name} {self.surname}"

    @property
    def full_name(self):
        return f"{self.name} {self.surname}"

    def get_profile_photo_url(self):
        if self.profile_photo:
            return self.profile_photo.url
        return None
