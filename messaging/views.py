from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Message
from .serializers import SendMessageSerializer, MessageSerializer
from users.models import Doctor, Patient
from appointments.models import Appointment

# 🛡️ YENİ GÜVENLİK GÖREVLİLERİMİZ
from users.permissions import IsDoctor, IsPatient

class SendMessageView(APIView):
    """
    Hastalar doktorlara mesaj gönderir.
    Daha önce TAMAMLANMIŞ bir randevu şartı aranır.
    """
    permission_classes = [IsPatient]

    def post(self, request):
        # ❌ Eski try-except bloğu silindi.
        # IsPatient sayesinde request.user.patient garantilendi.
        patient = request.user.patient

        serializer = SendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            doctor = Doctor.objects.get(user__id=serializer.validated_data['doctor_id'])
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)

        # Anti-Spam Kontrolü
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

        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


class GetConversationView(APIView):
    """
    Hasta, belirli bir doktorla olan yazışmalarını görür.
    """
    permission_classes = [IsPatient]

    def get(self, request, doctor_id):
        # ❌ Temizlendi!
        patient = request.user.patient

        try:
            doctor = Doctor.objects.get(user__id=doctor_id)
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)

        messages = Message.objects.filter(sender=patient, receiver=doctor).order_by('sent_at')
        return Response(MessageSerializer(messages, many=True).data)


class DoctorInboxView(APIView):
    """
    Doktor, kendisine gelen tüm mesajları listeler.
    Okundu bilgisini (is_read) burada günceller.
    """
    permission_classes = [IsDoctor]

    def get(self, request):
        # ❌ Temizlendi!
        doctor = request.user.doctor

        messages = Message.objects.filter(receiver=doctor).order_by('sent_at')

        patient_id = request.query_params.get('patient_id')
        if patient_id:
            messages = messages.filter(sender__user__id=patient_id)

        # Mesajlar çekildiği an 'okundu' olarak işaretlenir.
        messages.filter(is_read=False).update(is_read=True)

        return Response(MessageSerializer(messages, many=True).data)