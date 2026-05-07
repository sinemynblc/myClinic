from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from .models import Appointment
from .serializers import CreateAppointmentSerializer, AppointmentSerializer, RateAppointmentSerializer
from users.models import Doctor, Patient
from analytics.models import LeaveRequest


class AvailableSlotsView(APIView):
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
            doctor = Doctor.objects.get(user__id=doctor_id)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check approved leaves
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

        # Get booked slots
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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateAppointmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            patient = Patient.objects.get(user=request.user)
        except Patient.DoesNotExist:
            return Response({'error': 'Only patients can book appointments'}, status=status.HTTP_403_FORBIDDEN)

        doctor = Doctor.objects.get(user__id=serializer.validated_data['doctor_id'])
        date_time = serializer.validated_data['date_time']

        with transaction.atomic():
            # Check for double booking
            existing = Appointment.objects.select_for_update().filter(
                doctor=doctor,
                date_time=date_time,
                status__in=[Appointment.Status.BOOKED, Appointment.Status.PENDING]
            ).exists()

            if existing:
                return Response(
                    {'error': 'This slot is already booked'},
                    status=status.HTTP_409_CONFLICT
                )

            # Get fee from AI (placeholder for now)
            calculated_fee = doctor.base_consultation_fee

            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                date_time=date_time,
                status=Appointment.Status.BOOKED,
                calculated_fee=calculated_fee
            )

        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_201_CREATED
        )


class CancelAppointmentView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, appointment_id):
        try:
            patient = Patient.objects.get(user=request.user)
            appointment = Appointment.objects.get(id=appointment_id, patient=patient)
        except (Patient.DoesNotExist, Appointment.DoesNotExist):
            return Response({'error': 'Appointment not found'}, status=status.HTTP_404_NOT_FOUND)

        if appointment.status == Appointment.Status.COMPLETED:
            return Response({'error': 'Cannot cancel a completed appointment'}, status=status.HTTP_400_BAD_REQUEST)

        appointment.status = Appointment.Status.CANCELLED
        appointment.save()
        return Response({'message': 'Appointment cancelled'})


class RateAppointmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, appointment_id):
        try:
            patient = Patient.objects.get(user=request.user)
            appointment = Appointment.objects.get(
                id=appointment_id,
                patient=patient,
                status=Appointment.Status.COMPLETED
            )
        except (Patient.DoesNotExist, Appointment.DoesNotExist):
            return Response({'error': 'Appointment not found or not completed'}, status=status.HTTP_404_NOT_FOUND)

        serializer = RateAppointmentSerializer(data=request.data)
        if serializer.is_valid():
            appointment.patient_rating = serializer.validated_data['rating']
            appointment.save()
            return Response({'message': 'Rating saved'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)