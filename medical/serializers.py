from rest_framework import serializers
from .models import MedicalRecord, Prescription


class MedicalRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        fields = ['id', 'patient', 'doctor', 'date', 'analysis_data', 
                  'doctor_notes', 'ai_suggestions', 'doctor_approved']
        read_only_fields = ['id', 'date', 'ai_suggestions', 'doctor_approved']


class CreateMedicalRecordSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    analysis_data = serializers.JSONField(required=False)
    doctor_notes = serializers.CharField(required=False, allow_blank=True)


class PrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = ['id', 'patient', 'appointment', 'doctor', 'drugs', 'created_at']
        read_only_fields = ['id', 'created_at']


class CreatePrescriptionSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    appointment_id = serializers.UUIDField()
    drugs = serializers.ListField(
        child=serializers.DictField()
    )

    def validate_drugs(self, value):
        for drug in value:
            if 'name' not in drug or 'dosage' not in drug:
                raise serializers.ValidationError("Each drug must have 'name' and 'dosage'.")
        return value