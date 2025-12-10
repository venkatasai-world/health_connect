from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.mail import EmailMessage
from django.db import models, IntegrityError
from django.utils import timezone
from datetime import datetime
import json
import time
from .models import User, Order
from doctor.models import Prescription
from medicalshop.models import Medicine, PrescriptionMedicineMatch
from hello.models import LoginLog

# Rate limiting for API calls
last_api_call = 0
rate_limit_delay = 2  # seconds

def rate_limit_api_call():
    global last_api_call
    current_time = time.time()
    if current_time - last_api_call < rate_limit_delay:
        time.sleep(rate_limit_delay - (current_time - last_api_call))
    last_api_call = time.time()

def userLogin(request):
    # If already logged in, redirect to dashboard
    if 'user_id' in request.session:
        return redirect('userDashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                user.last_login = timezone.now()
                user.save()
                LoginLog.objects.create(
                    user_type='user',
                    email=email,
                    success=True
                )
                request.session['user_id'] = user.id
                request.session['user_name'] = user.name
                request.session['user_email'] = user.email
                return redirect('userDashboard')
            else:
                LoginLog.objects.create(
                    user_type='user',
                    email=email,
                    success=False
                )
                messages.error(request, 'Invalid email or password')
        except User.DoesNotExist:
            LoginLog.objects.create(
                user_type='user',
                email=email,
                success=False
            )
            messages.error(request, 'Invalid email or password')
    
    return render(request,"loginu.html")

def userLogout(request):
    """Logout user and redirect to home"""
    request.session.flush()
    return redirect('home')

def registerUser(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return render(request,"resisteru.html")
        
        try:
            user = User.objects.create(
                name=name,
                email=email
            )
            user.set_password(password)
            user.save()
            messages.success(request, 'Registration successful! Please login.')
            return redirect('userLogin')
        except IntegrityError:
            messages.error(request, 'Email already exists')
    

    
    return render(request,"resisteru.html")

def userDashboard(request):
    if 'user_id' not in request.session:
        return redirect('userLogin')
    
    user_id = request.session.get('user_id')
    user_email = request.session.get('user_email')
    
    # Get prescriptions for this user
    from doctor.models import Prescription
    from medicalshop.models import PrescriptionMedicineMatch
    prescriptions = Prescription.objects.filter(
        models.Q(user_id=user_id) | models.Q(patient_email=user_email)
    ).order_by('-created_at')
    
    # Get matched medicines for user's prescriptions - prevent duplicates
    # Use distinct on medicine_id and shop_id to avoid showing same medicine-shop combination twice
    all_matches = PrescriptionMedicineMatch.objects.filter(
        prescription__in=prescriptions
    ).select_related('shop', 'medicine', 'prescription').order_by('-matched_at')
    
    # Deduplicate by medicine and shop combination
    seen = set()
    matched_medicines = []
    for match in all_matches:
        key = (match.medicine_id, match.shop_id)
        if key not in seen:
            seen.add(key)
            matched_medicines.append(match)
    
    # Get available doctors for appointments
    from doctor.models import Doctor
    available_doctors = Doctor.objects.all().order_by('name')
    
    # Get user's appointments
    from .models import Appointment
    appointments = Appointment.objects.filter(user_id=user_id).order_by('-appointment_date', '-appointment_time')
    
    context = {
        'prescriptions': prescriptions,
        'user_name': request.session.get('user_name', 'User'),
        'matched_medicines': matched_medicines,
        'available_doctors': available_doctors,
        'appointments': appointments,
    }
    
    return render(request,"dashu.html", context)

@require_http_methods(["POST"])
def placeOrder(request):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        data = json.loads(request.body)
        user_id = request.session.get('user_id')
        user = User.objects.get(id=user_id)
        
        medicine_id = data.get('medicine_id')
        shop_id = data.get('shop_id')
        quantity = int(data.get('quantity', 1))
        
        if not medicine_id or not shop_id:
            return JsonResponse({'error': 'Medicine and shop are required'}, status=400)
        
        medicine = Medicine.objects.get(id=medicine_id, shop_id=shop_id)
        
        order = Order.objects.create(
            user=user,
            medicine=medicine,
            quantity=quantity,
            status='pending'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Order placed successfully!',
            'order_id': order.id
        })
    except Medicine.DoesNotExist:
        return JsonResponse({'error': 'Medicine not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["POST"])
def bookAppointment(request):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        data = json.loads(request.body)
        user_id = request.session.get('user_id')
        user = User.objects.get(id=user_id)
        
        doctor_id = data.get('doctor_id')
        appointment_date = data.get('appointment_date')
        appointment_time = data.get('appointment_time')
        reason = data.get('reason', '')
        
        if not doctor_id or not appointment_date or not appointment_time:
            return JsonResponse({'error': 'Doctor, date, and time are required'}, status=400)
        
        from doctor.models import Doctor
        from datetime import date, time as time_obj
        
        doctor = Doctor.objects.get(id=doctor_id)
        
        # Parse date and time
        appointment_date_obj = datetime.strptime(appointment_date, "%Y-%m-%d").date()
        appointment_time_obj = datetime.strptime(appointment_time, "%H:%M").time()
        
        # Check if appointment is in the past
        appointment_datetime = datetime.combine(appointment_date_obj, appointment_time_obj)
        if appointment_datetime < datetime.now():
            return JsonResponse({'error': 'Cannot book appointment in the past'}, status=400)
        
        from .models import Appointment
        existing = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=appointment_date_obj,
            appointment_time=appointment_time_obj,
            status__in=['scheduled', 'confirmed']
        ).exists()
        
        if existing:
            return JsonResponse({'error': 'An appointment with this doctor at this time already exists'}, status=400)
        
        appointment = Appointment.objects.create(
            user=user,
            doctor=doctor,
            appointment_date=appointment_date_obj,
            appointment_time=appointment_time_obj,
            reason=reason,
            status='scheduled'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Appointment booked successfully!',
            'appointment_id': appointment.id
        })
    except Doctor.DoesNotExist:
        return JsonResponse({'error': 'Doctor not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# AI Assistant and Prescription Analysis functions remain the same
def aiAssistant(request):
    if 'user_id' not in request.session:
        return redirect('userLogin')
    return render(request, "ai_assistant.html")

@require_http_methods(["POST"])
def analyzePrescription(request):
    """
    Analyze a prescription sent either as:
    - multipart/form-data with 'prescription_image' and/or 'prescription_text'
    - application/json with 'prescription' field
    """
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    # Simple rate limit
    rate_limit_api_call()

    try:
        import google.generativeai as genai
        from myproject.config import GEMINI_API_KEY
        import base64
        import re

        if not GEMINI_API_KEY:
            return JsonResponse(
                {'error': 'AI analysis is not configured. Please set GEMINI_API_KEY in .env.'},
                status=500,
            )

        genai.configure(api_key=GEMINI_API_KEY)

        content_type = request.META.get("CONTENT_TYPE", "")
        prescription_text = ""
        image_parts = None

        # Multipart form: handle image + optional text
        if content_type.startswith("multipart/form-data"):
            uploaded_file = request.FILES.get("prescription_image")
            prescription_text = (request.POST.get("prescription_text") or "").strip()

            if uploaded_file:
                if uploaded_file.size > 10 * 1024 * 1024:
                    return JsonResponse(
                        {'error': 'File too large. Maximum size is 10MB.'},
                        status=400,
                    )
                if not uploaded_file.content_type.startswith("image/"):
                    return JsonResponse(
                        {'error': 'Invalid file type. Please upload an image (JPG, PNG, WEBP).'},
                        status=400,
                    )

                image_bytes = uploaded_file.read()
                image_parts = [
                    {
                        "inline_data": {
                            "mime_type": uploaded_file.content_type,
                            "data": base64.b64encode(image_bytes).decode("utf-8"),
                        }
                    }
                ]

        # JSON body: text-only analysis
        else:
            body = request.body or b"{}"
            try:
                data = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
            prescription_text = (data.get("prescription") or "").strip()

        if not prescription_text and not image_parts:
            return JsonResponse(
                {'error': 'Please upload an image or enter prescription text.'},
                status=400,
            )

        # Build prompt parts similar to your Flask logic
        prompt_parts = [
            "You are a helpful AI assistant specializing in explaining medical prescriptions. "
            "Analyze the following prescription details (either text or from the image provided). "
            "Present the information clearly and engagingly using Markdown with emojis for visual appeal. "
            "For each medication found, provide:\n"
            "1.  💊 **Medication Name:** Clearly state the name.\n"
            "2.  ℹ️ **Purpose:** Briefly explain what the medication is typically used for.\n"
            "3.  ⏰ **Dosage Instructions:** Extract or infer dosage, frequency, and duration. "
            "If unclear, say that it is unclear.\n"
            "4.  ⚠️ **Common Side Effects:** List 2-3 common potential side effects.\n"
            "5.  🚫 **Important Warnings/Interactions:** Mention 1-2 crucial warnings.\n"
            "6.  💡 **Alternatives:** Mention any available alternatives if any.\n"
            "7.  🚨 **Recommendation:** Recommend if a reminder is needed in the format "
            "[Reminder: 8:00 AM].\n"
            "8.  📝 **Disclaimer:** Add a clear disclaimer that this is AI-generated and not medical advice.\n\n"
            "Prescription Details:\n",
        ]

        image_summary = None

        if image_parts:
            # Multi-modal prompt: image + text
            prompt_parts.extend(image_parts)
            prompt_parts.append(
                "\n(The prescription details are in the provided image.)"
            )
            image_summary = "Image-based prescription uploaded by user."

            if prescription_text:
                prompt_parts.append(
                    f"\nAdditional text provided by user: {prescription_text}"
                )
        else:
            # Text-only
            prompt_parts.append(prescription_text)
            image_summary = prescription_text

        # Use a multimodal-capable Gemini 2.5 Flash model
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt_parts)
        analysis_text = getattr(response, "text", "") or ""

        if not analysis_text:
            return JsonResponse(
                {'error': 'AI did not return any analysis. Please try again.'},
                status=500,
            )

        # Extract reminder times like [Reminder: 8:00 AM]
        reminder_times = re.findall(
            r"\[Reminder: (\d{1,2}:\d{2} (?:AM|PM))\]", analysis_text
        )

        # Store summary in session for optional use
        request.session["image_summary"] = image_summary or ""

        return JsonResponse(
            {
                "success": True,
                "analysis": analysis_text,
                "image_summary": image_summary,
                "reminder_times": reminder_times,
            }
        )
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["POST"])
def chatPrescription(request):
    """
    Chat about a previously analyzed prescription.
    Frontend sends JSON: { message, history, image_summary }
    """
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    # Simple rate limit
    rate_limit_api_call()

    try:
        body = request.body or b"{}"
        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        user_message = (data.get("message") or "").strip()
        image_summary = (data.get("image_summary") or "").strip()

        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)

        import google.generativeai as genai
        from myproject.config import GEMINI_API_KEY

        if not GEMINI_API_KEY:
            return JsonResponse(
                {'error': 'AI chat is not configured. Please set GEMINI_API_KEY in .env.'},
                status=500,
            )

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")

        # Build prompt with optional context
        prompt = [
            "You are an AI assistant knowledgeable about medications. "
            "Provide clear and concise answers. Use a friendly tone and emojis, "
            "but NEVER give definitive medical advice. Always recommend that the "
            "user consult their doctor or pharmacist.\n"
        ]

        if image_summary:
            prompt.append(
                f"\nPrescription Context (from previous analysis): {image_summary}\n"
            )

        prompt.append(f"User question: {user_message}\n")
        prompt.append(
            "Answer in a short, structured way using Markdown, and end with a disclaimer."
        )

        response = model.generate_content(prompt)
        answer = getattr(response, "text", "") or "Sorry, I could not generate a response."

        return JsonResponse(
            {
                "success": True,
                "reply": answer,
                # Optional fields kept for frontend compatibility
                "reminder_time": None,
                "reminder_medication": None,
            }
        )
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["POST"])
def searchMedicine(request):
    """Search for medicines across all medical shops"""
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        data = json.loads(request.body)
        search_term = data.get('search_term', '').strip().lower()
        
        if not search_term:
            return JsonResponse({'error': 'Search term is required'}, status=400)
        
        from medicalshop.models import Medicine
        # Search medicines by name (case-insensitive)
        medicines = Medicine.objects.filter(
            name__icontains=search_term
        ).select_related('shop').order_by('name')
        
        results = []
        for medicine in medicines:
            results.append({
                'medicine_id': medicine.id,
                'medicine_name': medicine.name,
                'shop_id': medicine.shop.id,
                'shop_name': medicine.shop.shop_name,
                'shop_location': medicine.shop.location,
                'quantity': medicine.quantity,
                'price': float(medicine.price),
            })
        
        return JsonResponse({
            'success': True,
            'results': results,
            'count': len(results)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
