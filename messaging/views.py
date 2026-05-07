from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from cryptography.fernet import Fernet
from django.conf import settings
import base64
from .models import Message
from .serializers import SendMessageSerializer, MessageSerializer
from users.models import Doctor, Patient
from appointments.models import Appointment


def get_cipher():
    key = base64.urlsafe_b64encode(settings.SECRET_KEY[:32].encode().ljust(32)[:32])
    return Fernet(key)


class SendMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            patient = Patient.objects.get(user=request.user)
        except Patient.DoesNotExist:
            return Response({'error': 'Only patients can send messages'}, status=status.HTTP_403_FORBIDDEN)

        serializer = SendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            doctor = Doctor.objects.get(user__id=serializer.validated_data['doctor_id'])
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check appointment relationship
        has_appointment = Appointment.objects.filter(
            patient=patient,
            doctor=doctor,
            status=Appointment.Status.COMPLETED
        ).exists()

        if not has_appointment:
            return Response(
                {'error': 'You can only message doctors you have had a completed appointment with'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Encrypt message
        cipher = get_cipher()
        encrypted = cipher.encrypt(serializer.validated_data['message_text'].encode()).decode()

        message = Message.objects.create(
            sender=patient,
            receiver=doctor,
            encrypted_content=encrypted,
            is_read=False
        )

        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


class GetConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, doctor_id):
        try:
            patient = Patient.objects.get(user=request.user)
        except Patient.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            doctor = Doctor.objects.get(user__id=doctor_id)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)

        messages = Message.objects.filter(sender=patient, receiver=doctor).order_by('sent_at')

        cipher = get_cipher()
        result = []
        for msg in messages:
            try:
                decrypted = cipher.decrypt(msg.encrypted_content.encode()).decode()
            except Exception:
                decrypted = '[encrypted]'
            result.append({
                'id': str(msg.id),
                'text': decrypted,
                'sent_at': msg.sent_at,
                'is_read': msg.is_read
            })

        # Mark as read
        messages.filter(is_read=False).update(is_read=True)

        return Response(result)