from django.urls import path
from .views import SubmitLeaveRequestView, ApproveLeaveRequestView, AnalyticsView

urlpatterns = [
    path('leave-requests/', SubmitLeaveRequestView.as_view(), name='submit-leave'),
    path('leave-requests/<uuid:leave_id>/', ApproveLeaveRequestView.as_view(), name='approve-leave'),
    path('analytics/', AnalyticsView.as_view(), name='analytics'),
]