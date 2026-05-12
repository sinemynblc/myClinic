from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = 'PATIENT', 'Patient'
        DOCTOR = 'DOCTOR', 'Doctor'
        MANAGER = 'MANAGER', 'Manager'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.email} ({self.role})"


class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT, primary_key=True)
    full_name = models.CharField(max_length=200, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.full_name or str(self.user_id)

    def anonymize(self):
        # DSD C4: Right to be Forgotten - wipe all PII then deactivate.
        self.full_name = None
        self.date_of_birth = None
        self.phone_number = None
        self.is_active = False
        self.save()

        suffix = uuid.uuid4().hex[:8]
        self.user.is_active = False
        self.user.email = f"deleted_{suffix}@myclinic.invalid"
        self.user.username = f"deleted_{suffix}"
        self.user.save()

    def delete(self, using=None, keep_parents=False):
        """
        DSD Requirement C4: prevent hard delete; instead deactivate and anonymize PII.
        """
        self.anonymize()
        return (0, {})


class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT, primary_key=True)
    full_name = models.CharField(max_length=200)
    specialty = models.CharField(max_length=100)
    base_consultation_fee = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Dr. {self.full_name} ({self.specialty})"

    def anonymize(self):
        # DSD C4: Right to be Forgotten for staff accounts.
        self.full_name = "Anonymized Doctor"
        self.save()

        suffix = uuid.uuid4().hex[:8]
        self.user.is_active = False
        self.user.email = f"deleted_{suffix}@myclinic.invalid"
        self.user.username = f"deleted_{suffix}"
        self.user.save()

    def delete(self, using=None, keep_parents=False):
        self.anonymize()
        return (0, {})


class Manager(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT, primary_key=True)
    full_name = models.CharField(max_length=200)

    def __str__(self):
        return self.full_name

    def anonymize(self):
        # DSD C4: Right to be Forgotten for staff accounts.
        self.full_name = "Anonymized Manager"
        self.save()

        suffix = uuid.uuid4().hex[:8]
        self.user.is_active = False
        self.user.email = f"deleted_{suffix}@myclinic.invalid"
        self.user.username = f"deleted_{suffix}"
        self.user.save()

    def delete(self, using=None, keep_parents=False):
        self.anonymize()
        return (0, {})


class TokenBlacklist(models.Model):
    """
    Explicit blacklist table (DSD requirement by name).
    SimpleJWT also maintains its own blacklist tables; this model is our
    project-level audit source of truth.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blacklisted_tokens')
    jti = models.CharField(max_length=255, unique=True)
    token_type = models.CharField(max_length=20)
    expires_at = models.DateTimeField(null=True, blank=True)
    blacklisted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-blacklisted_at']

    def __str__(self):
        return f"{self.user.email} - {self.token_type} - {self.jti}"