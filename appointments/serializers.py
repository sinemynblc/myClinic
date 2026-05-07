from rest_framework import serializers
from .models import Appointment
from users.models import Doctor, Patient


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'doctor', 'date_time',
            'status', 'calculated_fee', 'patient_rating'
        ]
        read_only_fields = ['id', 'status', 'calculated_fee']


class CreateAppointmentSerializer(serializers.Serializer):
    doctor_id = serializers.UUIDField()
    date_time = serializers.DateTimeField()

    def validate_doctor_id(self, value):
        if not Doctor.objects.filter(user__id=value).exists():
            raise serializers.ValidationError("Doctor not found.")
        return value

    def validate_date_time(self, value):
        from django.utils import timezone
        if value < timezone.now():
            raise serializers.ValidationError("Cannot book a past date.")
        return value


class RateAppointmentSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)