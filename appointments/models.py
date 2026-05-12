from django.db import models
import uuid
from users.models import Patient, Doctor


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        BOOKED = 'BOOKED', 'Booked'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class PaymentStatus(models.TextChoices):
        UNPAID = 'UNPAID', 'Unpaid'
        PAID = 'PAID', 'Paid'
        REFUNDED = 'REFUNDED', 'Refunded'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name='appointments')
    date_time = models.DateTimeField()
    # DSD Requirement C2: keep explicit date + timeslot for DB integrity constraint.
    appointment_date = models.DateField(null=True, blank=True)
    timeslot = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    payment_status = models.CharField(
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
    )
    calculated_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    patient_rating = models.IntegerField(null=True, blank=True)  # 1-5, nullable

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date_time']
        constraints = [
            # DSD Requirement C2/C6: enforce unique (doctor, date, slot) at DB-level.
            models.UniqueConstraint(
                fields=['doctor', 'appointment_date', 'timeslot'],
                name='uniq_doctor_date_timeslot',
            )
        ]

    def __str__(self):
        return f"{self.patient} - {self.doctor} - {self.date_time}"

    def save(self, *args, **kwargs):
        if self.date_time:
            # Keep derived fields consistent for the UniqueConstraint.
            self.appointment_date = self.date_time.date()
            self.timeslot = self.date_time.timetz().replace(tzinfo=None)
        super().save(*args, **kwargs)