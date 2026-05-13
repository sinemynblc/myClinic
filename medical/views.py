from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import MedicalRecord, Prescription
from .serializers import (
    CreateMedicalRecordSerializer,
    MedicalRecordSerializer,
    CreatePrescriptionSerializer,
    PrescriptionSerializer,
)
from users.models import Doctor, Patient
from appointments.models import Appointment
import threading
from django.db import close_old_connections


class CreateMedicalRecordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            doctor = Doctor.objects.get(user=request.user)
        except Doctor.DoesNotExist:
            return Response(
                {'error': 'Only doctors can create medical records'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CreateMedicalRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            patient = Patient.objects.get(user__id=serializer.validated_data['patient_id'])
        except Patient.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        record = MedicalRecord.objects.create(
            patient=patient,
            doctor=doctor,
            analysis_data=serializer.validated_data.get('analysis_data'),
            doctor_notes=serializer.validated_data.get('doctor_notes', ''),
            ai_suggestions=None,
            doctor_approved=False,
        )

        analysis_data = serializer.validated_data.get('analysis_data')
        if analysis_data:
            test_type = serializer.validated_data.get('test_type', 'general')

            # HTTP 202: AI runs in background; client polls GET /records/<id>/ for results.
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

            return Response(
                {
                    'id': str(record.id),
                    'status': 'ACCEPTED',
                    'detail': 'Medical record created. AI analysis is running in the background.',
                    'poll_url': f'/api/medical/records/{record.id}/',
                },
                status=status.HTTP_202_ACCEPTED,
            )

        return Response(MedicalRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class GetMedicalRecordView(APIView):
    """
    Polling endpoint for AI analysis results after a 202 response.
    Accessible by the treating doctor or the patient themselves.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, record_id):
        try:
            record = MedicalRecord.objects.get(id=record_id)
        except MedicalRecord.DoesNotExist:
            return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        is_treating_doctor = hasattr(user, 'doctor') and record.doctor.user == user
        is_own_patient = hasattr(user, 'patient') and record.patient.user == user

        if not (is_treating_doctor or is_own_patient):
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

        return Response(MedicalRecordSerializer(record).data)


class ApproveMedicalRecordView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, record_id):
        try:
            doctor = Doctor.objects.get(user=request.user)
        except Doctor.DoesNotExist:
            return Response(
                {'error': 'Only doctors can approve records'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            record = MedicalRecord.objects.get(id=record_id, doctor=doctor)
        except MedicalRecord.DoesNotExist:
            return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

        record.doctor_approved = True
        record.save()
        return Response(MedicalRecordSerializer(record).data)


class PatientHistoryView(APIView):
    """
    RBAC:
    - A doctor may view records for any patient (clinical necessity).
    - A patient may only view their own history.
    - Managers have no access to medical records.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        user = request.user
        is_doctor = hasattr(user, 'doctor')
        is_requesting_own_history = (
            hasattr(user, 'patient') and str(user.id) == str(patient_id)
        )

        if not (is_doctor or is_requesting_own_history):
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

        try:
            patient = Patient.objects.get(user__id=patient_id)
        except Patient.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        records = MedicalRecord.objects.filter(patient=patient).order_by('-date')[:20]
        prescriptions = Prescription.objects.filter(patient=patient).order_by('-created_at')[:20]

        return Response({
            'records': MedicalRecordSerializer(records, many=True).data,
            'prescriptions': PrescriptionSerializer(prescriptions, many=True).data,
        })


class CreatePrescriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            doctor = Doctor.objects.get(user=request.user)
        except Doctor.DoesNotExist:
            return Response(
                {'error': 'Only doctors can create prescriptions'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CreatePrescriptionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            patient = Patient.objects.get(user__id=serializer.validated_data['patient_id'])
        except Patient.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        # Validate: appointment must belong to this doctor + patient and be completed.
        try:
            appointment = Appointment.objects.get(
                id=serializer.validated_data['appointment_id'],
                doctor=doctor,
                patient=patient,
                status=Appointment.Status.COMPLETED,
            )
        except Appointment.DoesNotExist:
            return Response(
                {'error': 'No completed appointment found for this doctor and patient'},
                status=status.HTTP_404_NOT_FOUND,
            )

        prescription = Prescription.objects.create(
            patient=patient,
            appointment=appointment,
            doctor=doctor,
            drugs=serializer.validated_data['drugs'],
        )

        return Response(PrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)