from django.db import models

# Create your models here.
class LoginLog(models.Model):
    user_type = models.CharField(max_length=20, choices=[
        ('doctor', 'Doctor'),
        ('user', 'User'),
        ('medicalshop', 'Medical Shop')
    ])
    email = models.EmailField()
    login_time = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-login_time']
    
    def __str__(self):
        return f"{self.user_type} - {self.email} - {self.login_time}"
