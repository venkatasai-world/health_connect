from django.contrib import admin
from .models import MedicalShop, Medicine, PrescriptionMedicineMatch

# Register your models here.
@admin.register(MedicalShop)
class MedicalShopAdmin(admin.ModelAdmin):
    list_display = ('shop_name', 'owner_name', 'email', 'location', 'latitude', 'longitude', 'created_at', 'last_login')
    search_fields = ('shop_name', 'owner_name', 'email', 'location')
    list_filter = ('created_at',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('shop_name', 'owner_name', 'email', 'password')
        }),
        ('Location Information', {
            'fields': ('location', 'latitude', 'longitude'),
            'description': 'Enter location address. For GIS functionality, add latitude and longitude coordinates.'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_login'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'quantity', 'price', 'created_at')
    search_fields = ('name', 'shop__shop_name')
    list_filter = ('shop', 'created_at')

@admin.register(PrescriptionMedicineMatch)
class PrescriptionMedicineMatchAdmin(admin.ModelAdmin):
    list_display = ('medicine_name', 'shop', 'prescription', 'matched_at', 'notified')
    search_fields = ('medicine_name', 'shop__shop_name')
    list_filter = ('notified', 'matched_at')
