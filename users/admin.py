from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from .models import User, Patient, Doctor, Manager

# 1. Yeni ekleme ekranı için form oluşturuyoruz ki e-postayı sormaya mecbur kalsın
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'username', 'role') # Şifre alanları form tarafından otomatik eklenir

# users/admin.py dosyasının ilgili kısmı:

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['email', 'role', 'is_staff', 'is_active']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )
    
    add_form = CustomUserCreationForm
    
    # İŞTE BURASI DEĞİŞTİ: Şifre alanlarını ekrana çizdiriyoruz
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            # password1 ve password2 Django'nun kalıplaşmış şifre alanlarıdır
            'fields': ('email', 'username', 'password1', 'password2', 'role'),
        }),
    )
    
   

admin.site.register(User, CustomUserAdmin)
admin.site.register(Patient)
admin.site.register(Doctor)
admin.site.register(Manager)