from django.urls import path
from .views import SendMessageView, GetConversationView

urlpatterns = [
    path('messages/', SendMessageView.as_view(), name='send-message'),
    path('messages/<uuid:doctor_id>/', GetConversationView.as_view(), name='get-conversation'),
]