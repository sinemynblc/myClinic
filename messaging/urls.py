from django.urls import path
from .views import SendMessageView, GetConversationView, DoctorInboxView

urlpatterns = [
    path('messages/', SendMessageView.as_view(), name='send-message'),
    path('messages/inbox/', DoctorInboxView.as_view(), name='doctor-inbox'),
    path('messages/<uuid:doctor_id>/', GetConversationView.as_view(), name='get-conversation'),
]