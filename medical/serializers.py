from rest_framework import serializers
from .models import MedicalRecord, Prescription


class MedicalRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalRecord
        fields = [
            'id', 'patient', 'doctor', 'date',
            'analysis_data', 'doctor_notes', 'ai_suggestions', 'doctor_approved',
        ]
        read_only_fields = ['id', 'date', 'ai_suggestions', 'doctor_approved']


class CreateMedicalRecordSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    analysis_data = serializers.JSONField(required=False)
    doctor_notes = serializers.CharField(required=False, allow_blank=True)
    # Passed to the AI service so it can tailor its analysis prompt.
    test_type = serializers.CharField(required=False, default='general')


class PrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = ['id', 'patient', 'appointment', 'doctor', 'drugs', 'created_at']
        read_only_fields = ['id', 'created_at']


class CreatePrescriptionSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    appointment_id = serializers.UUIDField()
    drugs = serializers.ListField(child=serializers.DictField(), min_length=1)

    def validate_drugs(self, value):
        for drug in value:
            if 'name' not in drug or 'dosage' not in drug:
                raise serializers.ValidationError(
                    "Each drug entry must include 'name' and 'dosage'."
                )
        return value