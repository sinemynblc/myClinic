from django.urls import path
from .views import (
    AvailableSlotsView,
    CreateAppointmentView,
    CancelAppointmentView,
    RateAppointmentView
)

urlpatterns = [
    path('available/', AvailableSlotsView.as_view(), name='available-slots'),
    path('', CreateAppointmentView.as_view(), name='create-appointment'),
    path('<uuid:appointment_id>/cancel/', CancelAppointmentView.as_view(), name='cancel-appointment'),
    path('<uuid:appointment_id>/rate/', RateAppointmentView.as_view(), name='rate-appointment'),
]