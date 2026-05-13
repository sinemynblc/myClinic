from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from django.db.models import Avg

from .models import Appointment
from .serializers import CreateAppointmentSerializer, AppointmentSerializer, RateAppointmentSerializer
from users.models import Doctor, Patient
from analytics.models import LeaveRequest

# 1. ADIM: Yeni izin sınıfımızı çağırıyoruz
from users.permissions import IsPatient 

class AvailableSlotsView(APIView):
    # Bu view hem doktorlar hem hastalar tarafından görüntülenebilir (Bilgi amaçlı)
    permission_classes = [IsAuthenticated]

    def get(self, request):
        doctor_id = request.query_params.get('doctor_id')
        date = request.query_params.get('date')

        if not doctor_id or not date:
            return Response(
                {'error': 'doctor_id and date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Burada doctor_id dışarıdan geldiği için try-except kalmalı
            doctor = Doctor.objects.get(user__id=doctor_id)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)

        from datetime import datetime
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        on_leave = LeaveRequest.objects.filter(
            doctor=doctor,
            status=LeaveRequest.Status.APPROVED,
            start_date__lte=date_obj,
            end_date__gte=date_obj
        ).exists()

        if on_leave:
            return Response({'available_slots': [], 'reason': 'Doctor is on leave'})

        booked = Appointment.objects.filter(
            doctor=doctor,
            date_time__date=date_obj,
            status__in=[Appointment.Status.BOOKED, Appointment.Status.PENDING]
        ).values_list('date_time', flat=True)

        return Response({
            'doctor_id': str(doctor_id),
            'date': date,
            'booked_slots': [str(slot) for slot in booked]
        })


class CreateAppointmentView(APIView):
    # 2. ADIM: Kapıya IsPatient'ı diktik
    permission_classes = [IsPatient]

    def post(self, request):
        serializer = CreateAppointmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # ❌ ESKİ TRY-EXCEPT SİLİNDİ!
        # IsPatient sayesinde request.user.patient'ın varlığı garanti altında.
        patient = request.user.patient

        doctor = Doctor.objects.get(user__id=serializer.validated_data['doctor_id'])
        date_time = serializer.validated_data['date_time']
        appointment_date = date_time.date()
        timeslot = date_time.timetz().replace(tzinfo=None)

        with transaction.atomic():
            # DSD C6: İzin kontrolü
            on_leave = LeaveRequest.objects.filter(
                doctor=doctor,
                status=LeaveRequest.Status.APPROVED,
                start_date__lte=appointment_date,
                end_date__gte=appointment_date
            ).exists()
            
            if on_leave:
                return Response(
                    {'error': 'Doctor is on approved leave for this date'},
                    status=status.HTTP_409_CONFLICT
                )

            # Çakışma kontrolü (C2)
            existing = Appointment.objects.select_for_update().filter(
                doctor=doctor,
                appointment_date=appointment_date,
                timeslot=timeslot,
                status__in=[Appointment.Status.BOOKED, Appointment.Status.PENDING]
            ).exists()

            if existing:
                return Response({'error': 'This slot is already booked'}, status=status.HTTP_409_CONFLICT)

            # Dinamik Ücret Hesaplama (AI)
            from ai_integration.services import calculate_dynamic_fee
            
            booked_count = Appointment.objects.filter(
                doctor=doctor,
                date_time__date=appointment_date,
                status__in=[Appointment.Status.BOOKED, Appointment.Status.PENDING]
            ).count()

            avg_rating = Appointment.objects.filter(
                doctor=doctor,
                status=Appointment.Status.COMPLETED,
                patient_rating__isnull=False
            ).aggregate(avg=Avg('patient_rating'))['avg']

            calculated_fee = calculate_dynamic_fee(
                doctor_id=str(doctor.user.id),
                base_fee=doctor.base_consultation_fee,
                booked_slots=booked_count,
                total_slots=10,
                avg_patient_rating=avg_rating
            )

            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                date_time=date_time,
                appointment_date=appointment_date,
                timeslot=timeslot,
                status=Appointment.Status.BOOKED,
                payment_status=Appointment.PaymentStatus.UNPAID,
                calculated_fee=calculated_fee
            )

        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)


class CancelAppointmentView(APIView):
    # 3. ADIM: Sadece hastalar kendi randevusunu iptal edebilir
    permission_classes = [IsPatient]

    def delete(self, request, appointment_id):
        # ❌ PATIENT KONTROLÜ SİLİNDİ, DOĞRUDAN KULLANIYORUZ
        patient = request.user.patient
        
        try:
            appointment = Appointment.objects.get(id=appointment_id, patient=patient)
        except Appointment.DoesNotExist:
            return Response({'error': 'Appointment not found'}, status=status.HTTP_404_NOT_FOUND)

        if appointment.status == Appointment.Status.COMPLETED:
            return Response({'error': 'Cannot cancel a completed appointment'}, status=status.HTTP_400_BAD_REQUEST)

        appointment.status = Appointment.Status.CANCELLED
        appointment.save()
        return Response({'message': 'Appointment cancelled'})


class RateAppointmentView(APIView):
    # 4. ADIM: Sadece hastalar puan verebilir
    permission_classes = [IsPatient]

    def post(self, request, appointment_id):
        patient = request.user.patient
        
        try:
            appointment = Appointment.objects.get(
                id=appointment_id,
                patient=patient,
                status=Appointment.Status.COMPLETED
            )
        except Appointment.DoesNotExist:
            return Response({'error': 'Appointment not found or not completed'}, status=status.HTTP_404_NOT_FOUND)

        serializer = RateAppointmentSerializer(data=request.data)
        if serializer.is_valid():
            appointment.patient_rating = serializer.validated_data['rating']
            appointment.save()
            return Response({'message': 'Rating saved'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)