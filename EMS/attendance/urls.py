from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('mark/', views.mark_attendance, name='mark'),
    path('daily/', views.daily_view, name='daily_today'),
    path('daily/<str:date>/', views.daily_view, name='daily'),
    path('employee/<int:pk>/', views.employee_attendance, name='employee'),
    path('monthly/', views.monthly_report, name='monthly'),
    path('yearly/', views.yearly_report, name='yearly'),
    path('<int:pk>/edit/', views.edit_attendance, name='edit'),
    path('holidays/', views.manage_holidays, name='holidays'),
    path('holidays/<int:pk>/delete/', views.delete_holiday, name='delete_holiday'),
]
