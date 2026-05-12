from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import MedicalRecord, Prescription
from .serializers import CreateMedicalRecordSerializer, MedicalRecordSerializer, CreatePrescriptionSerializer, PrescriptionSerializer
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
            return Response({'error': 'Only doctors can create medical records'}, status=status.HTTP_403_FORBIDDEN)

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
            doctor_approved=False
        )

        analysis_data = serializer.validated_data.get('analysis_data')
        if analysis_data:
            # DSD Requirement C3: Async AI Analysis to meet 5-second constraint (HTTP 202 + background thread).
            def _run_ai(record_id, test_data):
                close_old_connections()
                try:
                    from ai_integration.services import analyze_test_results
                    suggestions = analyze_test_results(test_data=test_data, test_type='general')
                    MedicalRecord.objects.filter(id=record_id).update(ai_suggestions=suggestions)
                finally:
                    close_old_connections()

            threading.Thread(
                target=_run_ai,
                args=(record.id, analysis_data),
                daemon=True,
            ).start()

            return Response(
                {
                    'id': str(record.id),
                    'status': 'ACCEPTED',
                    'detail': 'AI analysis started in background.',
                },
                status=status.HTTP_202_ACCEPTED,
            )

        return Response(MedicalRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class ApproveMedicalRecordView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, record_id):
        try:
            doctor = Doctor.objects.get(user=request.user)
        except Doctor.DoesNotExist:
            return Response({'error': 'Only doctors can approve records'}, status=status.HTTP_403_FORBIDDEN)

        try:
            record = MedicalRecord.objects.get(id=record_id, doctor=doctor)
        except MedicalRecord.DoesNotExist:
            return Response({'error': 'Record not found'}, status=status.HTTP_404_NOT_FOUND)

        record.doctor_approved = True
        record.save()
        return Response(MedicalRecordSerializer(record).data)


class PatientHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        try:
            patient = Patient.objects.get(user__id=patient_id)
        except Patient.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        records = MedicalRecord.objects.filter(patient=patient).order_by('-date')[:20]
        prescriptions = Prescription.objects.filter(patient=patient).order_by('-created_at')[:20]

        return Response({
            'records': MedicalRecordSerializer(records, many=True).data,
            'prescriptions': PrescriptionSerializer(prescriptions, many=True).data
        })


class CreatePrescriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            doctor = Doctor.objects.get(user=request.user)
        except Doctor.DoesNotExist:
            return Response({'error': 'Only doctors can create prescriptions'}, status=status.HTTP_403_FORBIDDEN)

        serializer = CreatePrescriptionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            patient = Patient.objects.get(user__id=serializer.validated_data['patient_id'])
            appointment = Appointment.objects.get(id=serializer.validated_data['appointment_id'])
        except (Patient.DoesNotExist, Appointment.DoesNotExist):
            return Response({'error': 'Patient or appointment not found'}, status=status.HTTP_404_NOT_FOUND)

        prescription = Prescription.objects.create(
            patient=patient,
            appointment=appointment,
            doctor=doctor,
            drugs=serializer.validated_data['drugs']
        )

        return Response(PrescriptionSerializer(prescription).data, status=status.HTTP_201_CREATED)