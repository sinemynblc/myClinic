from rest_framework import serializers
from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    # Maps the encrypted_content field to a clean 'content' key.
    # django_cryptography decrypts transparently in memory; the views
    # that use this serializer only serve sender or receiver, never third parties.
    content = serializers.CharField(source='encrypted_content', read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'sender', 'receiver', 'content', 'sent_at', 'is_read']
        read_only_fields = ['id', 'sender', 'receiver', 'content', 'sent_at', 'is_read']


class SendMessageSerializer(serializers.Serializer):
    doctor_id = serializers.UUIDField()
    message_text = serializers.CharField(max_length=500)