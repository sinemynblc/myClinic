from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Patient, Doctor, Manager


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['email', 'role', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )

admin.site.register(User, CustomUserAdmin)
admin.site.register(Patient)
admin.site.register(Doctor)
admin.site.register(Manager)