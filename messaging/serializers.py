from rest_framework import serializers
from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'sender', 'receiver', 'sent_at', 'is_read']
        read_only_fields = ['id', 'sent_at']


class SendMessageSerializer(serializers.Serializer):
    doctor_id = serializers.UUIDField()
    message_text = serializers.CharField(max_length=500)