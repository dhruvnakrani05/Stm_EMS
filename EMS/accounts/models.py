from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    """Custom user model with role-based access control."""
    ROLE_CHOICES = [
        ('admin', 'Admin'),      # Full access to everything
        ('hr', 'HR'),            # Can modify attendance and payroll
        ('owner', 'Owner'),      # View-only access
    ]
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='owner',
        help_text='Determines the user\'s access level in the system.'
    )
    phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin_user(self):
        return self.role == 'admin'

    @property
    def is_hr_user(self):
        return self.role == 'hr'

    @property
    def is_owner_user(self):
        return self.role == 'owner'

    @property
    def can_modify_attendance(self):
        return self.role in ('admin', 'hr')

    @property
    def can_modify_payroll(self):
        return self.role == 'admin'

    @property
    def can_manage_employees(self):
        return self.role == 'admin'
