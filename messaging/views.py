from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Message
from .serializers import SendMessageSerializer, MessageSerializer
from users.models import Doctor, Patient
from appointments.models import Appointment


class SendMessageView(APIView):
    """
    Patients send messages to doctors.
    Requires a prior completed appointment to prevent unsolicited contact.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            patient = Patient.objects.get(user=request.user)
        except Patient.DoesNotExist:
            return Response(
                {'error': 'Only patients can send messages'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = SendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            doctor = Doctor.objects.get(user__id=serializer.validated_data['doctor_id'])
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)

        has_appointment = Appointment.objects.filter(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.COMPLETED,
        ).exists()

        if not has_appointment:
            return Response(
                {'error': 'You can only message doctors you have had a completed appointment with'},
                status=status.HTTP_403_FORBIDDEN,
            )

        message = Message.objects.create(
            sender=patient,
            receiver=doctor,
            encrypted_content=serializer.validated_data['message_text'],
            is_read=False,
        )

        # C5: MessageSerializer returns 'content' (decrypted in memory by django_cryptography)
        # only to the authorized sender here.
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


class GetConversationView(APIView):
    """
    Patient reads their own thread with a specific doctor.
    Does NOT mutate is_read — that flag is set when the doctor reads their inbox.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, doctor_id):
        try:
            patient = Patient.objects.get(user=request.user)
        except Patient.DoesNotExist:
            return Response(
                {'error': 'Only patients can access this endpoint'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            doctor = Doctor.objects.get(user__id=doctor_id)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)

        messages = Message.objects.filter(sender=patient, receiver=doctor).order_by('sent_at')
        return Response(MessageSerializer(messages, many=True).data)


class DoctorInboxView(APIView):
    """
    Doctor reads all messages sent to them.
    Marks messages as read on retrieval.
    Optionally filtered by ?patient_id= to view a specific thread.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            doctor = Doctor.objects.get(user=request.user)
        except Doctor.DoesNotExist:
            return Response(
                {'error': 'Only doctors can access the inbox'},
                status=status.HTTP_403_FORBIDDEN,
            )

        messages = Message.objects.filter(receiver=doctor).order_by('sent_at')

        patient_id = request.query_params.get('patient_id')
        if patient_id:
            messages = messages.filter(sender__user__id=patient_id)

        # is_read marks that the doctor has seen the message.
        messages.filter(is_read=False).update(is_read=True)

        return Response(MessageSerializer(messages, many=True).data)