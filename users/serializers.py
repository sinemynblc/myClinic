from rest_framework import serializers
from .models import User, Patient, Doctor, Manager


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=User.Role.choices, required=False)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'role']

    def create(self, validated_data):
        requested_role = validated_data.pop('role', None)
        # Public registration is restricted to patients only.
        if requested_role and requested_role != User.Role.PATIENT:
            raise serializers.ValidationError({'role': 'Only PATIENT registration is allowed.'})

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=User.Role.PATIENT
        )
        Patient.objects.create(
            user=user,
            full_name=validated_data.get('username')
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    