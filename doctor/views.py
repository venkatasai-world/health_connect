from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.db import IntegrityError, models
from django.db.models import Case, When, Value, IntegerField
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from io import BytesIO
import json
from smtplib import SMTPException
from .models import Doctor, Prescription
from user.models import User
from hello.models import LoginLog
from medicalshop.models import Medicine, PrescriptionMedicineMatch

# Create your views here.
def doctorLogin(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            doctor = Doctor.objects.get(email=email)
            if doctor.check_password(password):
                doctor.last_login = timezone.now()
                doctor.save()
                LoginLog.objects.create(
                    user_type='doctor',
                    email=email,
                    success=True
                )
                request.session['doctor_id'] = doctor.id
                request.session['doctor_name'] = doctor.name
                request.session['doctor_email'] = doctor.email
                return redirect('doctorDashboard')
            else:
                LoginLog.objects.create(
                    user_type='doctor',
                    email=email,
                    success=False
                )
                messages.error(request, 'Invalid email or password')
        except Doctor.DoesNotExist:
            LoginLog.objects.create(
                user_type='doctor',
                email=email,
                success=False
            )
            messages.error(request, 'Invalid email or password')
    
    # If already logged in, redirect to dashboard
    if 'doctor_id' in request.session:
        return redirect('doctorDashboard')
    
    return render(request,"login.html")

def doctorLogout(request):
    """Logout doctor and redirect to home"""
    request.session.flush()
    return redirect('home')

def register(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        specialty = request.POST.get('specialty', '')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return render(request,"registration.html")
        
        if Doctor.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return render(request,"registration.html")
        
        try:
            doctor = Doctor(name=name, email=email, specialty=specialty)
            doctor.set_password(password)
            doctor.save()
            messages.success(request, 'Registration successful! Please login.')
            return redirect('doctorLogin')
        except IntegrityError:
            messages.error(request, 'Email already exists. Please use a different email.')
            return render(request,"registration.html")
    
    return render(request,"registration.html")

@ensure_csrf_cookie
def doctorDashboard(request):
    if 'doctor_id' not in request.session:
        return redirect('doctorLogin')
    
    doctor_id = request.session.get('doctor_id')
    try:
        doctor = Doctor.objects.get(id=doctor_id)
        doctor_name = doctor.name
        doctor_specialty = doctor.specialty or 'General Medicine'
        doctor_email = doctor.email
    except Doctor.DoesNotExist:
        return redirect('doctorLogin')
    
    # Get appointments for this doctor
    # Get appointments for this doctor
    from user.models import Appointment
    appointments = Appointment.objects.filter(doctor=doctor).annotate(
        status_order=Case(
            When(status='scheduled', then=Value(0)),
            When(status='confirmed', then=Value(1)),
            When(status='completed', then=Value(2)),
            When(status='cancelled', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    ).order_by('status_order', 'appointment_date', 'appointment_time')
    
    context = {
        'doctor_name': doctor_name,
        'doctor_specialty': doctor_specialty,
        'doctor_email': doctor_email,
        'appointments': appointments,
    }
    return render(request,"doctor.html", context)

@require_http_methods(["POST"])
def savePrescription(request):
    if 'doctor_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        try:
            data = json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        doctor_id = request.session.get('doctor_id')
        doctor = Doctor.objects.get(id=doctor_id)
        
        patient_name = data.get('patient_name')
        patient_email = data.get('patient_email')
        age = data.get('age')
        weight = data.get('weight')
        height = data.get('height')
        gender = data.get('gender', '')
        diagnosis = data.get('diagnosis', '')
        notes = data.get('notes', '')
        medications = data.get('medications', [])
        
        # Check if user exists
        user = None
        try:
            user = User.objects.get(email=patient_email)
        except User.DoesNotExist:
            pass
        
        prescription = Prescription.objects.create(
            doctor=doctor,
            user=user,
            patient_name=patient_name,
            patient_email=patient_email,
            age=age,
            weight=weight,
            height=height,
            gender=gender,
            diagnosis=diagnosis,
            notes=notes,
            medications=medications
        )
        
        # Send email and PDF if requested
        send_email = data.get('send_email', True)
        email_sent = False
        if send_email:
            email_sent = send_prescription_email(prescription)
        
        # Match prescription medicines with medical shop medicines
        match_prescription_medicines(prescription)
        
        if email_sent:
            return JsonResponse({
                'success': True, 
                'prescription_id': prescription.id,
                'message': 'Prescription saved and email sent successfully!'
            })
        else:
            return JsonResponse({
                'success': True, 
                'prescription_id': prescription.id,
                'message': 'Prescription saved but email sending failed. Please check email settings.',
                'warning': True
            })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def send_prescription_email(prescription):
    try:
        from django.conf import settings
        
        # Generate PDF first
        pdf_buffer = generate_prescription_pdf(prescription)
        
        # Validate patient email
        to_email = prescription.patient_email.strip() if prescription.patient_email else None
        
        if not to_email:
            print("[EMAIL] ERROR: No patient email provided")
            return False
        
        # Simple email validation
        if '@' not in to_email or '.' not in to_email.split('@')[-1]:
            print(f"[EMAIL] ERROR: Invalid email format: {to_email}")
            return False
        
        print(f"[EMAIL] Sending prescription to: {to_email}")
        
        # Create simple email
        subject = f'Your Prescription from Dr. {prescription.doctor.name}'
        
        text_body = f"Dear {prescription.patient_name},\n\nYour prescription is attached.\n\nBest regards,\nHealthConnect"
        
        # Create the email message
        email = EmailMessage(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        
        # Attach PDF
        if pdf_buffer:
            pdf_content = pdf_buffer.getvalue()
            email.attach('prescription.pdf', pdf_content, 'application/pdf')
            print(f"[EMAIL] PDF attached: {len(pdf_content)} bytes")
        
        # Send email
        print(f"[EMAIL] Calling email.send()...")
        result = email.send(fail_silently=False)
        print(f"[EMAIL] Email send returned: {result}")
        
        if result > 0:
            prescription.sent_via_email = True
            prescription.save()
            print(f"[EMAIL] SUCCESS: Email sent to {to_email}")
            return True
        else:
            print(f"[EMAIL] ERROR: email.send() returned {result}")
            return False
            
    except SMTPException as smtp_error:
        print(f"[EMAIL] SMTP ERROR: {smtp_error}")
        return False
    except Exception as e:
        print(f"[EMAIL] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_prescription_pdf(prescription):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Colors
    brand_blue = (37/255, 117/255, 252/255)
    brand_purple = (106/255, 17/255, 203/255)
    brand_yellow = (1, 0.9, 0.0)
    light_gray = (0.96, 0.96, 0.98)
    border_gray = (0.8, 0.8, 0.85)

    # Header band
    p.setFillColorRGB(*brand_purple)
    p.rect(40, height - 70, width - 80, 40, fill=1, stroke=0)
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica-Bold", 18)
    p.drawString(55, height - 45, "HealthConnect — Digital Prescription")
    
    # Doctor Info
    y = height - 100
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, y, f"Dr. {prescription.doctor.name}")
    y -= 20
    p.setFont("Helvetica", 12)
    p.drawString(100, y, f"Specialty: {prescription.doctor.specialty or 'General Medicine'}")
    y -= 20
    p.drawString(100, y, f"Email: {prescription.doctor.email}")
    
    # Patient Info
    y -= 40
    p.setFillColorRGB(*brand_blue)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, y, "Patient Information")
    y -= 20
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica", 12)
    p.drawString(100, y, f"Name: {prescription.patient_name}")
    y -= 20
    p.drawString(100, y, f"Age: {prescription.age} years")
    if prescription.weight:
        y -= 20
        p.drawString(100, y, f"Weight: {prescription.weight} kg")
    if prescription.height:
        y -= 20
        p.drawString(100, y, f"Height: {prescription.height} cm")
    if prescription.gender:
        y -= 20
        p.drawString(100, y, f"Gender: {prescription.gender}")
    
    # Diagnosis
    if prescription.diagnosis:
        y -= 40
        p.setFillColorRGB(*brand_blue)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(100, y, "Diagnosis")
        y -= 20
        p.setFillColorRGB(0, 0, 0)
        p.setFont("Helvetica", 12)
        p.drawString(100, y, prescription.diagnosis)
    
    # Medications Table
    y -= 40
    p.setFillColorRGB(*brand_blue)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(100, y, "Medications")
    y -= 30
    
    # Table header with borders
    table_top = y
    table_left = 100
    col_widths = [50, 200, 100, 120, 100]  # S.No., Medication, Dosage, Frequency, Duration
    table_width = sum(col_widths)
    
    # Draw header background
    p.setFillColorRGB(*brand_purple)
    p.rect(table_left, table_top - 20, table_width, 25, fill=1, stroke=0)
    
    # Header text
    p.setFillColorRGB(1, 1, 1)  # White text
    p.setFont("Helvetica-Bold", 11)
    x_pos = table_left + 5
    p.drawString(x_pos, table_top - 5, "S.No.")
    x_pos += col_widths[0]
    p.drawString(x_pos, table_top - 5, "Medication")
    x_pos += col_widths[1]
    p.drawString(x_pos, table_top - 5, "Dosage")
    x_pos += col_widths[2]
    p.drawString(x_pos, table_top - 5, "Frequency")
    x_pos += col_widths[3]
    p.drawString(x_pos, table_top - 5, "Duration")
    
    y = table_top - 25
    
    # Draw table rows with borders
    p.setFillColorRGB(0, 0, 0)  # Black text
    p.setFont("Helvetica", 10)
    
    for idx, med in enumerate(prescription.medications, 1):
        if y < 120:
            p.showPage()
            y = height - 50
            table_top = y + 20
        
        row_bottom = y - 18
        
        # Alternate row color
        if idx % 2 == 0:
            p.setFillColorRGB(*light_gray)
            p.rect(table_left, row_bottom, table_width, 20, fill=1, stroke=0)
        
        # Draw borders
        p.setStrokeColorRGB(*border_gray)
        p.setLineWidth(1)
        # Top border
        p.line(table_left, y, table_left + table_width, y)
        # Bottom border
        p.line(table_left, row_bottom, table_left + table_width, row_bottom)
        # Vertical borders
        x_pos = table_left
        for width in col_widths:
            x_pos += width
            p.line(x_pos, y, x_pos, row_bottom)
        
        # Draw cell content
        p.setFillColorRGB(0, 0, 0)
        x_pos = table_left + 5
        p.drawString(x_pos, row_bottom + 5, str(idx))
        x_pos += col_widths[0]
        p.drawString(x_pos, row_bottom + 5, med.get('name', '')[:30])  # Limit length
        x_pos += col_widths[1]
        p.drawString(x_pos, row_bottom + 5, med.get('dosage', '')[:15])
        x_pos += col_widths[2]
        p.drawString(x_pos, row_bottom + 5, med.get('frequency', '')[:18])
        x_pos += col_widths[3]
        p.drawString(x_pos, row_bottom + 5, med.get('duration', '')[:15])
        
        y = row_bottom - 2
    
    # Notes
    if prescription.notes:
        y -= 30
        p.setFillColorRGB(*brand_blue)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(100, y, "Notes")
        y -= 20
        p.setFillColorRGB(0, 0, 0)
        p.setFont("Helvetica", 12)
        notes_lines = prescription.notes.split('\n')
        for line in notes_lines:
            if y < 100:
                p.showPage()
                y = height - 50
            p.drawString(100, y, line)
            y -= 15
    
    # Footer
    y = 50
    p.setFillColorRGB(*brand_purple)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(100, y, f"Prescribed on: {prescription.created_at.strftime('%B %d, %Y at %I:%M %p')}")
    y -= 15
    p.drawString(100, y, f"Approved by: Dr. {prescription.doctor.name}")
    
    p.save()
    buffer.seek(0)
    return buffer

@require_http_methods(["POST"])
def updateAppointment(request):
    """Update appointment status (accept/reject/complete)"""
    if 'doctor_id' not in request.session:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        try:
            data = json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        appointment_id = data.get('appointment_id')
        status = data.get('status')
        
        if not appointment_id or not status:
            return JsonResponse({'error': 'Appointment ID and status are required'}, status=400)
        
        if status not in ['confirmed', 'cancelled', 'completed']:
            return JsonResponse({'error': 'Invalid status'}, status=400)
        
        from user.models import Appointment
        appointment = Appointment.objects.get(id=appointment_id, doctor_id=request.session.get('doctor_id'))
        
        old_status = appointment.status
        appointment.status = status
        appointment.save()
        
        # Send email to user when appointment is accepted
        if status == 'confirmed' and old_status == 'scheduled':
            send_appointment_confirmation_email(appointment)
            message = 'Appointment accepted and confirmation email sent to patient!'
        elif status == 'cancelled':
            message = 'Appointment cancelled successfully!'
        elif status == 'completed':
            message = 'Appointment marked as completed!'
        else:
            message = 'Appointment status updated successfully!'
        
        return JsonResponse({
            'success': True,
            'message': message
        })
    except Appointment.DoesNotExist:
        return JsonResponse({'error': 'Appointment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def send_appointment_confirmation_email(appointment):
    """Send confirmation email to user when appointment is accepted"""
    try:
        from django.core.mail import EmailMessage
        from myproject.config import EMAIL_FROM_ADDRESS
        from_email = EMAIL_FROM_ADDRESS
    except ImportError:
        from django.conf import settings
        from django.core.mail import EmailMessage
        from_email = settings.EMAIL_HOST_USER or ''
    
    try:
        subject = f'Appointment Confirmed with Dr. {appointment.doctor.name}'
        message = f'''
Dear {appointment.user.name},

Your appointment has been confirmed!

Appointment Details:
- Doctor: Dr. {appointment.doctor.name} ({appointment.doctor.specialty or 'General Medicine'})
- Date: {appointment.appointment_date.strftime("%B %d, %Y")}
- Time: {appointment.appointment_time.strftime("%I:%M %p")}
- Reason: {appointment.reason or 'Not specified'}

Please arrive on time for your appointment.

Best regards,
HealthConnect Team
        '''
        
        email = EmailMessage(
            subject,
            message,
            from_email,
            [appointment.user.email],
        )
        email.send()
        return True
    except Exception as e:
        print(f"Error sending appointment confirmation email: {e}")
        return False

def match_prescription_medicines(prescription):
    """Match prescription medicines with available medicines in medical shops"""
    from medicalshop.models import MedicalShop
    
    medications = prescription.medications or []
    
    for med in medications:
        med_name = med.get('name', '').strip().lower()
        if not med_name:
            continue
        
        # Search for medicines in all shops (case-insensitive partial match)
        all_medicines = Medicine.objects.filter(
            name__icontains=med_name
        ).select_related('shop')
        
        for medicine in all_medicines:
            # Create match record
            PrescriptionMedicineMatch.objects.get_or_create(
                prescription=prescription,
                medicine=medicine,
                medicine_name=med.get('name', ''),
                shop=medicine.shop,
                defaults={'notified': False}
            )