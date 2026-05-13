from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Authentication — /api/auth/register/, /api/auth/login/, /api/auth/logout/
    path('api/auth/', include('users.urls')),

    # Appointments — /api/appointments/  /api/appointments/<id>/cancel/  etc.
    path('api/appointments/', include('appointments.urls')),

    # Medical records & prescriptions — /api/medical/records/  /api/medical/prescriptions/
    path('api/medical/', include('medical.urls')),

    # Leave requests & analytics dashboard — /api/leave-requests/  /api/analytics/
    path('api/', include('analytics.urls')),

    # Messaging — /api/messages/  /api/messages/inbox/  /api/messages/<doctor_id>/
    path('api/', include('messaging.urls')),

    # Frontend — must remain last; acts as catch-all for non-API routes
    path('', include('frontend.urls')),
]