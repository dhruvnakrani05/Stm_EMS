from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_index, name='index'),
    path('attendance/download/', views.download_attendance_report, name='download_attendance'),
    path('payroll/download/', views.download_payroll_report, name='download_payroll'),
    path('share/', views.share_report, name='share'),
]
