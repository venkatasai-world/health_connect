from django.contrib import admin
from .models import Doctor, Prescription

# Register your models here.
@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'specialty', 'created_at', 'last_login')
    search_fields = ('name', 'email', 'specialty')
    list_filter = ('created_at',)

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('patient_name', 'doctor', 'patient_email', 'age', 'created_at', 'sent_via_email')
    search_fields = ('patient_name', 'patient_email', 'doctor__name')
    list_filter = ('created_at', 'sent_via_email')
    readonly_fields = ('created_at',)
