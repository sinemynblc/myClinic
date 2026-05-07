from django.db import models
import uuid
from users.models import Patient, Doctor
from appointments.models import Appointment


class MedicalRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='medical_records')
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name='medical_records')
    date = models.DateTimeField(auto_now_add=True)
    analysis_data = models.JSONField(null=True, blank=True)
    doctor_notes = models.TextField(null=True, blank=True)
    ai_suggestions = models.JSONField(null=True, blank=True)
    doctor_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"Record - {self.patient} - {self.date}"


class Prescription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='prescriptions')
    appointment = models.OneToOneField(Appointment, on_delete=models.PROTECT, related_name='prescription')
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name='prescriptions')
    drugs = models.JSONField()  # [{name, dosage, instructions}]
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prescription - {self.patient} - {self.created_at}"