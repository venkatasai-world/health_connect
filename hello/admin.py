from django.contrib import admin
from .models import LoginLog

# Register your models here.
@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display = ('user_type', 'email', 'login_time', 'success')
    list_filter = ('user_type', 'success', 'login_time')
    search_fields = ('email',)
    readonly_fields = ('login_time',)
