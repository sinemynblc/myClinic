from rest_framework import serializers
from .models import LeaveRequest


class LeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = ['id', 'doctor', 'start_date', 'end_date', 'reason', 'leave_type', 'status', 'manager']
        read_only_fields = ['id', 'status', 'manager']


class CreateLeaveRequestSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField()
    leave_type = serializers.ChoiceField(choices=['ANNUAL', 'SICK'])

    def validate(self, data):
        from django.utils import timezone
        if data['start_date'] < timezone.now().date():
            raise serializers.ValidationError("Cannot request leave for past dates.")
        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError("End date cannot be before start date.")
        return data


class ApproveLeaveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['APPROVED', 'REJECTED'])
    