from django.contrib import admin
from .models import User

# Register your models here.
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at', 'last_login')
    search_fields = ('name', 'email')
    list_filter = ('created_at',)
