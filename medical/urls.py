from django.urls import path
from .views import (
    CreateMedicalRecordView,
    GetMedicalRecordView,
    ApproveMedicalRecordView,
    PatientHistoryView,
    CreatePrescriptionView,
)

urlpatterns = [
    path('records/', CreateMedicalRecordView.as_view(), name='create-record'),
    path('records/<uuid:record_id>/', GetMedicalRecordView.as_view(), name='get-record'),
    path('records/<uuid:record_id>/approve/', ApproveMedicalRecordView.as_view(), name='approve-record'),
    path('records/patient/<uuid:patient_id>/', PatientHistoryView.as_view(), name='patient-history'),
    path('prescriptions/', CreatePrescriptionView.as_view(), name='create-prescription'),
]