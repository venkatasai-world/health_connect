from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.db import IntegrityError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime
import json
from .models import MedicalShop, Medicine
from hello.models import LoginLog

# Create your views here.
def medicalDashboard(request):
    if 'medicalshop_id' not in request.session:
        return redirect('medicalLogin')
    
    shop_id = request.session.get('medicalshop_id')
    shop = MedicalShop.objects.get(id=shop_id)
    
    # Get shop's medicines
    medicines = Medicine.objects.filter(shop=shop).order_by('-created_at')
    
    context = {
        'shop_name': shop.shop_name,
        'shop': shop,
        'medicines': medicines,
        'shop_id': shop_id,
    }
    
    return render(request,"dashm.html", context)

@require_http_methods(["POST"])
def addMedicine(request):
    if 'medicalshop_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        data = json.loads(request.body)
        shop_id = request.session.get('medicalshop_id')
        shop = MedicalShop.objects.get(id=shop_id)
        
        name = data.get('name', '').strip()
        quantity = int(data.get('quantity', 0))
        price = float(data.get('price', 0))
        expiry_date = data.get('expiry_date', None)
        medicine_id = data.get('medicine_id', None)  # For editing
        
        if not name:
            return JsonResponse({'error': 'Medicine name is required'}, status=400)
        
        if medicine_id:
            # Edit existing medicine
            try:
                medicine = Medicine.objects.get(id=medicine_id, shop=shop)
                medicine.name = name
                medicine.quantity = quantity
                medicine.price = price
                if expiry_date:
                    medicine.expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                medicine.save()
                message = 'Medicine updated successfully!'
            except Medicine.DoesNotExist:
                return JsonResponse({'error': 'Medicine not found'}, status=404)
        else:
            # Create new medicine
            medicine, created = Medicine.objects.get_or_create(
                shop=shop,
                name=name,
                defaults={
                    'quantity': quantity, 
                    'price': price,
                    'expiry_date': datetime.strptime(expiry_date, '%Y-%m-%d').date() if expiry_date else None
                }
            )
            
            if not created:
                # Update existing medicine
                medicine.quantity = quantity
                medicine.price = price
                if expiry_date:
                    medicine.expiry_date = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                medicine.save()
                message = 'Medicine updated successfully!'
            else:
                message = 'Medicine added successfully!'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'medicine': {
                'id': medicine.id,
                'name': medicine.name,
                'quantity': medicine.quantity,
                'price': str(medicine.price),
                'expiry_date': medicine.expiry_date.strftime('%Y-%m-%d') if medicine.expiry_date else None
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["POST"])
def deleteMedicine(request):
    if 'medicalshop_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        data = json.loads(request.body)
        medicine_id = data.get('medicine_id')
        shop_id = request.session.get('medicalshop_id')
        
        medicine = Medicine.objects.get(id=medicine_id, shop_id=shop_id)
        medicine.delete()
        
        return JsonResponse({'success': True, 'message': 'Medicine deleted successfully!'})
    except Medicine.DoesNotExist:
        return JsonResponse({'error': 'Medicine not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def medicalLogin(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            shop = MedicalShop.objects.get(email=email)
            if shop.check_password(password):
                shop.last_login = timezone.now()
                shop.save()
                LoginLog.objects.create(
                    user_type='medicalshop',
                    email=email,
                    success=True
                )
                request.session['medicalshop_id'] = shop.id
                request.session['medicalshop_name'] = shop.shop_name
                request.session['medicalshop_email'] = shop.email
                return redirect('medicalDashboard')
            else:
                LoginLog.objects.create(
                    user_type='medicalshop',
                    email=email,
                    success=False
                )
                messages.error(request, 'Invalid email or password')
        except MedicalShop.DoesNotExist:
            LoginLog.objects.create(
                user_type='medicalshop',
                email=email,
                success=False
            )
            messages.error(request, 'Invalid email or password')
    
    # If already logged in, redirect to dashboard
    if 'medicalshop_id' in request.session:
        return redirect('medicalDashboard')
    
    return render(request,"loginm.html")

def medicalLogout(request):
    """Logout medical shop and redirect to home"""
    request.session.flush()
    return redirect('home')

def registerMedical(request):
    if request.method == 'POST':
        shop_name = request.POST.get('shop_name')
        email = request.POST.get('email')
        owner_name = request.POST.get('owner_name')
        location = request.POST.get('location')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return render(request,"registerm.html")
        
        if MedicalShop.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return render(request,"registerm.html")
        
        try:
            shop = MedicalShop(
                shop_name=shop_name,
                email=email,
                owner_name=owner_name,
                location=location
            )
            shop.set_password(password)
            shop.save()
            messages.success(request, 'Registration successful! Please login.')
            return redirect('medicalLogin')
        except IntegrityError:
            messages.error(request, 'Email already exists. Please use a different email.')
            return render(request,"registerm.html")
    
    return render(request,"registerm.html")

@require_http_methods(["POST"])
def updateShop(request):
    if 'medicalshop_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        data = json.loads(request.body)
        shop_id = request.session.get('medicalshop_id')
        shop = MedicalShop.objects.get(id=shop_id)
        
        shop.shop_name = data.get('shop_name', shop.shop_name)
        shop.owner_name = data.get('owner_name', shop.owner_name)
        shop.location = data.get('location', shop.location)
        
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if latitude:
            shop.latitude = float(latitude)
        if longitude:
            shop.longitude = float(longitude)
        
        shop.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Shop information updated successfully!'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)