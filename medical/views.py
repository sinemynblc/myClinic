from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import MedicalRecord, Prescription
from .serializers import CreateMedicalRecordSerializer, MedicalRecordSerializer, CreatePrescriptionSerializer, PrescriptionSerializer
from users.models import Doctor, Patient
from appointments.models import Appointment


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

        # Call AI for analysis if analysis_data provided
        ai_suggestions = None
        if serializer.validated_data.get('analysis_data'):
            from ai_integration.services import analyze_test_results
            ai_suggestions = analyze_test_results(
                test_data=serializer.validated_data['analysis_data'],
                test_type='general'
            )

        record = MedicalRecord.objects.create(
            patient=patient,
            doctor=doctor,
            analysis_data=serializer.validated_data.get('analysis_data'),
            doctor_notes=serializer.validated_data.get('doctor_notes', ''),
            ai_suggestions=ai_suggestions,
            doctor_approved=False
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