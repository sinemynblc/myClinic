from rest_framework.permissions import BasePermission
from .models import User


class IsPatient(BasePermission):
    message = 'Only patients can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.PATIENT
        )


class IsDoctor(BasePermission):
    message = 'Only doctors can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.DOCTOR
        )


class IsManager(BasePermission):
    message = 'Only managers can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.MANAGER
        )


class IsDoctorOrPatient(BasePermission):
    """For endpoints accessible by both roles with different object-level rules."""
    message = 'Only doctors or patients can perform this action.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in (User.Role.DOCTOR, User.Role.PATIENT)
        )