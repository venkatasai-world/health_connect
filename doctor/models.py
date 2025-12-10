from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from user.models import User

# Create your models here.
class Doctor(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    specialty = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    def set_password(self, raw_password):
        self.password = make_password(raw_password)
    
    def check_password(self, raw_password):
        return check_password(raw_password, self.password)
    
    def __str__(self):
        return self.name

class Prescription(models.Model):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='prescriptions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prescriptions', null=True, blank=True)
    patient_name = models.CharField(max_length=100)
    patient_email = models.EmailField()
    age = models.IntegerField()
    weight = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    diagnosis = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    medications = models.JSONField(default=list)  # Store medications as JSON
    created_at = models.DateTimeField(auto_now_add=True)
    sent_via_email = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Prescription for {self.patient_name} by Dr. {self.doctor.name}"
