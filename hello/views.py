from django.shortcuts import render
from .models import LoginLog
from doctor.models import Doctor
from user.models import User
from medicalshop.models import MedicalShop

def home(request):
    # Get login stats only (removed account counts)
    total_logins = LoginLog.objects.filter(success=True).count()
    successful_logins = LoginLog.objects.filter(success=True).count()
    failed_logins = LoginLog.objects.filter(success=False).count()
    
    context = {
        'total_logins': total_logins,
        'successful_logins': successful_logins,
        'failed_logins': failed_logins,
    }
    
    return render(request,"index.html", context)

# Create your views here.
