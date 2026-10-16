from django.urls import path
from . import views

app_name = 'payroll'

urlpatterns = [
    # Payroll records
    path('', views.payroll_list, name='list'),
    path('generate/', views.generate_payroll, name='generate'),
    path('<int:pk>/', views.payroll_detail, name='detail'),
    path('<int:pk>/modify/', views.modify_salary, name='modify'),
    path('<int:pk>/mark-paid/', views.mark_paid, name='mark_paid'),
    path('<int:pk>/mark-unpaid/', views.mark_unpaid, name='mark_unpaid'),

    # Period management
    path('period/<int:period_pk>/finalize/', views.finalize_period, name='finalize'),
    path('period/<int:period_pk>/mark-all-paid/', views.mark_period_paid, name='mark_period_paid'),

    # Employee history
    path('employee/<int:pk>/history/', views.employee_payroll_history, name='employee_history'),

    # Yearly summary
    path('yearly/', views.yearly_summary, name='yearly'),

    # Salary advances
    path('advances/', views.advance_list, name='advances'),
    path('advances/add/', views.add_advance, name='add_advance'),
    path('advances/<int:pk>/edit/', views.edit_advance, name='edit_advance'),
    path('advances/<int:pk>/delete/', views.delete_advance, name='delete_advance'),

    # Audit log
    path('audit-log/', views.audit_log, name='audit_log'),
]
