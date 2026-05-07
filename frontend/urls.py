from django.urls import path
from .views import (
    login_view, register_view, logout_view,
    patient_dashboard, doctor_dashboard,
    manager_dashboard, approve_leave
)

urlpatterns = [
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('patient/dashboard/', patient_dashboard, name='patient-dashboard'),
    path('doctor/dashboard/', doctor_dashboard, name='doctor-dashboard'),
    path('manager/dashboard/', manager_dashboard, name='manager-dashboard'),
    path('approve-leave/<uuid:leave_id>/', approve_leave, name='approve-leave'),
]