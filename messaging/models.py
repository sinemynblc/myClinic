from django.db import models
import uuid
from users.models import Patient, Doctor
from django_cryptography.fields import encrypt


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='sent_messages')
    receiver = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name='received_messages')
    # DSD Requirement C5: encrypt sensitive message content at rest.
    encrypted_content = encrypt(models.TextField())
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['sent_at']

    def __str__(self):
        return f"{self.sender} -> {self.receiver} - {self.sent_at}"