from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from users.models import User, Patient, Doctor, Manager
from appointments.models import Appointment
from analytics.models import LeaveRequest
from messaging.models import Message
from medical.models import MedicalRecord
from appointments.emails import send_booking_confirmation, send_doctor_notification, send_followup_reminder
import threading
from django.db import close_old_connections
import requests as http_requests


def available_slots(request):
    doctor_id = request.GET.get('doctor_id')
    date_str  = request.GET.get('date')
    if not doctor_id or not date_str:
        return JsonResponse({'slots': []})

    all_slots = []
    current = datetime.strptime(f"{date_str} 09:00", "%Y-%m-%d %H:%M")
    end     = datetime.strptime(f"{date_str} 16:00", "%Y-%m-%d %H:%M")
    while current < end:
        all_slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=10)

    booked_qs = Appointment.objects.filter(
        doctor__user__id=doctor_id,
        date_time__date=date_str,
        status__in=[Appointment.Status.BOOKED, Appointment.Status.PENDING],
    ).values_list('date_time', flat=True)
    booked_times = {dt.strftime("%H:%M") for dt in booked_qs}

    slots = [{'time': s, 'available': s not in booked_times} for s in all_slots]
    return JsonResponse({'slots': slots})


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
        form_type = request.POST.get('form_type')

        if form_type == 'message':
            doctor_id = request.POST.get('doctor_id')
            content   = request.POST.get('content', '').strip()
            if not content:
                messages.error(request, 'Message cannot be empty.')
            else:
                try:
                    doctor = Doctor.objects.get(user__id=doctor_id)
                    Message.objects.create(
                        sender=patient,
                        receiver=doctor,
                        encrypted_content=content,
                    )
                    messages.success(request, f'Message sent to Dr. {doctor.full_name}.')
                except Doctor.DoesNotExist:
                    messages.error(request, 'Doctor not found.')
                except Exception as e:
                    messages.error(request, f'Error: {e}')

        else:  # default: booking
            date_time_str = request.POST.get('date_time')
            try:
                date_time_obj = timezone.make_aware(
                    datetime.strptime(date_time_str, "%Y-%m-%d %H:%M")
                )
            except (ValueError, TypeError):
                messages.error(request, 'Invalid date/time. Please select a slot and try again.')
                return redirect('/patient/dashboard/')

            try:
                doctor = Doctor.objects.get(user__id=request.POST.get('doctor_id'))
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

                apt = Appointment.objects.create(
                    patient=patient,
                    doctor=doctor,
                    date_time=date_time_obj,
                    status=Appointment.Status.BOOKED,
                    calculated_fee=fee
                )
                try:
                    send_booking_confirmation(apt)
                    send_doctor_notification(apt)
                    send_followup_reminder(apt)   # demo placeholder
                except Exception:
                    pass  # emails are non-critical
                messages.success(request, f'Appointment booked! Fee: {fee:.0f} TRY')
            except Exception as e:
                messages.error(request, f'Could not book appointment: {e}')

    now = timezone.now()
    all_appointments = Appointment.objects.filter(patient=patient)
    completed_count  = all_appointments.filter(status=Appointment.Status.COMPLETED).count()
    upcoming_count   = all_appointments.filter(
        status__in=[Appointment.Status.BOOKED, Appointment.Status.PENDING],
        date_time__gte=now
    ).count()
    recent_appointments = all_appointments.order_by('-date_time')[:10]
    doctors = Doctor.objects.all()
    sent_messages   = Message.objects.filter(sender=patient).order_by('-sent_at')[:20]
    health_records  = MedicalRecord.objects.filter(
        patient=patient, doctor_approved=True
    ).order_by('-date')[:10]

    return render(request, 'patient/dashboard.html', {
        'appointments':     recent_appointments,
        'total_count':      all_appointments.count(),
        'completed_count':  completed_count,
        'upcoming_count':   upcoming_count,
        'doctors':          doctors,
        'sent_messages':    sent_messages,
        'health_records':   health_records,
    })


def doctor_dashboard(request):
    if not request.user.is_authenticated or request.user.role != 'DOCTOR':
        return redirect('/login/')
    
    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return redirect('/login/')
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'reply':
            msg_id        = request.POST.get('message_id')
            reply_content = request.POST.get('reply_content', '').strip()
            if not reply_content:
                messages.error(request, 'Reply cannot be empty.')
            else:
                try:
                    msg = Message.objects.get(id=msg_id, receiver=doctor)
                    msg.reply_content = reply_content
                    msg.replied_at    = timezone.now()
                    msg.is_read       = True
                    msg.save()
                    messages.success(request, 'Reply sent.')
                except Message.DoesNotExist:
                    messages.error(request, 'Message not found.')

        elif form_type == 'medical_record':
            patient_id   = request.POST.get('patient_id')
            test_type    = request.POST.get('test_type', 'Blood Test')
            doctor_notes = request.POST.get('doctor_notes', '').strip()
            param_keys   = request.POST.getlist('param_key')
            param_values = request.POST.getlist('param_value')
            analysis_data = {
                'test_type': test_type,
                'parameters': {k: v for k, v in zip(param_keys, param_values) if k and v},
            }
            try:
                patient = Patient.objects.get(user__id=patient_id)
                record  = MedicalRecord.objects.create(
                    patient=patient,
                    doctor=doctor,
                    analysis_data=analysis_data,
                    doctor_notes=doctor_notes,
                    ai_suggestions=None,
                    doctor_approved=False,
                )

                def _run_ai(record_id, test_data, t_type):
                    close_old_connections()
                    try:
                        from ai_integration.services import analyze_test_results
                        suggestions = analyze_test_results(test_data=test_data, test_type=t_type)
                        MedicalRecord.objects.filter(id=record_id).update(ai_suggestions=suggestions)
                    finally:
                        close_old_connections()

                threading.Thread(
                    target=_run_ai,
                    args=(record.id, analysis_data, test_type),
                    daemon=True,
                ).start()
                messages.success(request, 'Record created. AI analysis is running — results appear below in seconds.')
            except Patient.DoesNotExist:
                messages.error(request, 'Patient not found.')
            except Exception as e:
                messages.error(request, f'Error creating record: {e}')

        else:  # leave request
            start_date = request.POST.get('start_date')
            end_date   = request.POST.get('end_date')
            reason     = request.POST.get('reason')
            leave_type = request.POST.get('leave_type')
            if start_date and end_date and start_date > end_date:
                messages.error(request, 'Start date cannot be later than end date.')
            else:
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

    inbox = Message.objects.filter(receiver=doctor).order_by('-sent_at')[:20]
    unread_count = Message.objects.filter(receiver=doctor, is_read=False).count()
    Message.objects.filter(receiver=doctor, is_read=False).update(is_read=True)

    medical_records = MedicalRecord.objects.filter(doctor=doctor).order_by('-date')[:15]
    all_patients    = Patient.objects.all()

    return render(request, 'doctor/dashboard.html', {
        'doctor':          doctor,
        'appointments':    appointments,
        'inbox':           inbox,
        'unread_count':    unread_count,
        'medical_records': medical_records,
        'all_patients':    all_patients,
    })


def approve_record(request, record_id):
    if not request.user.is_authenticated or request.user.role != 'DOCTOR':
        return redirect('/login/')
    if request.method == 'POST':
        try:
            doctor = Doctor.objects.get(user=request.user)
            record = MedicalRecord.objects.get(id=record_id, doctor=doctor)
            record.doctor_approved = True
            record.save()
            messages.success(request, 'Record approved.')
        except MedicalRecord.DoesNotExist:
            messages.error(request, 'Record not found.')
    return redirect('/doctor/dashboard/')


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