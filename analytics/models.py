from django.db import models
import uuid
from users.models import Doctor, Manager


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    class LeaveType(models.TextChoices):
        ANNUAL = 'ANNUAL', 'Annual'
        SICK = 'SICK', 'Sick'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name='leave_requests')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    leave_type = models.CharField(max_length=10, choices=LeaveType.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    manager = models.ForeignKey(Manager, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_leaves')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.doctor} - {self.leave_type} - {self.start_date} / {self.end_date}"