from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.utils import timezone
from users.models import User, Patient, Doctor, Manager
from appointments.models import Appointment
from analytics.models import LeaveRequest
from messaging.models import Message
import requests as http_requests


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
                user = User.objects.get(email=email)
                if user.check_password(password):
                    user.backend = 'django.contrib.auth.backends.ModelBackend'
                    login(request, user)
                if user.role == 'PATIENT':
                    return redirect('/patient/dashboard/')
                elif user.role == 'DOCTOR':
                    return redirect('/doctor/dashboard/')
                elif user.role == 'MANAGER':
                    return redirect('/manager/dashboard/')
        except User.DoesNotExist:
            pass
        
        return render(request, 'login.html', {'error': 'Invalid credentials'})
    
    return render(request, 'login.html')


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if User.objects.filter(email=email).exists():
            return render(request, 'register.html', {'error': 'Email already exists'})
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=User.Role.PATIENT
        )
        Patient.objects.create(user=user, full_name=username)
        login(request, user)
        return redirect('/patient/dashboard/')
    
    return render(request, 'register.html')


def logout_view(request):
    logout(request)
    return redirect('/login/')


def patient_dashboard(request):
    if not request.user.is_authenticated or request.user.role != 'PATIENT':
        return redirect('/login/')
    
    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        return redirect('/login/')
    
    if request.method == 'POST':
        doctor_id = request.POST.get('doctor_id')
        date_time = request.POST.get('date_time')
        
        try:
            doctor = Doctor.objects.get(user__id=doctor_id)
            from django.db import transaction
            from ai_integration.services import calculate_dynamic_fee
            from django.db.models import Avg
            
            booked_count = Appointment.objects.filter(
                doctor=doctor,
                status__in=[Appointment.Status.BOOKED, Appointment.Status.PENDING]
            ).count()
            
            avg_rating = Appointment.objects.filter(
                doctor=doctor,
                status=Appointment.Status.COMPLETED,
                patient_rating__isnull=False
            ).aggregate(avg=Avg('patient_rating'))['avg']
            
            fee = calculate_dynamic_fee(
                doctor_id=str(doctor.user.id),
                base_fee=doctor.base_consultation_fee,
                booked_slots=booked_count,
                total_slots=10,
                avg_patient_rating=avg_rating
            )
            
            Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                date_time=date_time,
                status=Appointment.Status.BOOKED,
                calculated_fee=fee
            )
            messages.success(request, f'Appointment booked! Fee: {fee} TRY')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    
    appointments = Appointment.objects.filter(patient=patient).order_by('-date_time')[:10]
    doctors = Doctor.objects.all()
    
    return render(request, 'patient/dashboard.html', {
        'appointments': appointments,
        'doctors': doctors
    })


def doctor_dashboard(request):
    if not request.user.is_authenticated or request.user.role != 'DOCTOR':
        return redirect('/login/')
    
    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return redirect('/login/')
    
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')
        leave_type = request.POST.get('leave_type')
        
        LeaveRequest.objects.create(
            doctor=doctor,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            leave_type=leave_type,
            status=LeaveRequest.Status.PENDING
        )
        messages.success(request, 'Leave request submitted!')
    
    today = timezone.now().date()
    appointments = Appointment.objects.filter(
        doctor=doctor,
        date_time__date=today
    ).order_by('date_time')
    
    unread = Message.objects.filter(receiver=doctor, is_read=False)
    
    return render(request, 'doctor/dashboard.html', {
        'doctor': doctor,
        'appointments': appointments,
        'messages_list': unread,
        'unread_count': unread.count()
    })


def manager_dashboard(request):
    if not request.user.is_authenticated or request.user.role != 'MANAGER':
        return redirect('/login/')
    
    try:
        manager = Manager.objects.get(user=request.user)
    except Manager.DoesNotExist:
        return redirect('/login/')
    
    analytics_data = None
    start_date = request.GET.get('start_date', timezone.now().date().replace(day=1).strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', timezone.now().date().strftime('%Y-%m-%d'))
    
    from django.db.models import Sum, Avg, Count
    appointments = Appointment.objects.filter(
        date_time__date__gte=start_date,
        date_time__date__lte=end_date
    )
    completed = appointments.filter(status=Appointment.Status.COMPLETED)
    total_revenue = completed.aggregate(total=Sum('calculated_fee'))['total'] or 0
    avg_satisfaction = completed.aggregate(avg=Avg('patient_rating'))['avg']
    total_slots = appointments.count()
    booked_slots = appointments.filter(status=Appointment.Status.BOOKED).count()
    vacancy_rate = round(1 - (booked_slots / total_slots), 2) if total_slots > 0 else 1.0

    analytics_data = {
        'total_appointments': appointments.count(),
        'total_revenue': float(total_revenue),
        'vacancy_rate': vacancy_rate,
        'avg_satisfaction_score': round(avg_satisfaction, 2) if avg_satisfaction else None
    }

    leave_requests = LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING)

    return render(request, 'manager/dashboard.html', {
        'analytics': analytics_data,
        'leave_requests': leave_requests,
        'start_date': start_date,
        'end_date': end_date
    })


def approve_leave(request, leave_id):
    if not request.user.is_authenticated or request.user.role != 'MANAGER':
        return redirect('/login/')
    
    if request.method == 'POST':
        try:
            manager = Manager.objects.get(user=request.user)
            leave = LeaveRequest.objects.get(id=leave_id)
            leave.status = request.POST.get('status')
            leave.manager = manager
            leave.save()
            messages.success(request, f'Leave request {leave.status.lower()}.')
        except Exception as e:
            messages.error(request, str(e))
    
    return redirect('/manager/dashboard/')