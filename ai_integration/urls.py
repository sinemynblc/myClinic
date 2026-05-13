from django.urls import path
from .views import RerunAnalysisView

urlpatterns = [
    path('records/<uuid:record_id>/analyze/', RerunAnalysisView.as_view(), name='rerun-analysis'),
]