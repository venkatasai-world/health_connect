from django.db import models
from django.contrib.auth.hashers import make_password, check_password

# Create your models here.
class MedicalShop(models.Model):
    shop_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    owner_name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Latitude for GIS location")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Longitude for GIS location")
    password = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    def set_password(self, raw_password):
        self.password = make_password(raw_password)
    
    def check_password(self, raw_password):
        return check_password(raw_password, self.password)
    
    def __str__(self):
        return self.shop_name

class Medicine(models.Model):
    shop = models.ForeignKey(MedicalShop, on_delete=models.CASCADE, related_name='medicines')
    name = models.CharField(max_length=200)
    quantity = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    expiry_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['shop', 'name']  # Each shop can have unique medicine names
    
    def __str__(self):
        return f"{self.name} - {self.shop.shop_name}"

class PrescriptionMedicineMatch(models.Model):
    """Tracks which medical shops have medicines from prescriptions"""
    prescription = models.ForeignKey('doctor.Prescription', on_delete=models.CASCADE, related_name='matches')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='prescription_matches')
    medicine_name = models.CharField(max_length=200)  # Store the name from prescription
    shop = models.ForeignKey(MedicalShop, on_delete=models.CASCADE, related_name='prescription_matches')
    matched_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['prescription', 'medicine', 'shop']
    
    def __str__(self):
        return f"{self.medicine_name} available at {self.shop.shop_name}"
