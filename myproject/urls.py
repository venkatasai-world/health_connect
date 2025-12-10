
from django.contrib import admin
from django.urls import path
from hello.views import *
from doctor.views import *
from medicalshop.views import *
from user.views import *


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name="home"),
    path('dllogin/', doctorLogin, name="doctorLogin"),
    path('dregister/', register, name="register"),
    path('ddashboard/', doctorDashboard, name="doctorDashboard"),
    path('mdashboard/', medicalDashboard, name="medicalDashboard"),
    path('mlogin/',medicalLogin, name="medicalLogin"),
    path('mregister/', registerMedical, name="registerMedical"),
    path('ulogin/', userLogin, name="userLogin"),
    path('uregister/', registerUser, name="registerUser"),
    path('udashboard/', userDashboard, name="userDashboard"),
    path('ai-assistant/', aiAssistant, name="aiAssistant"),
    path('analyze-prescription/', analyzePrescription, name="analyzePrescription"),
    path('chat-prescription/', chatPrescription, name="chatPrescription"),
    path('save-prescription/', savePrescription, name="savePrescription"),
    path('add-medicine/', addMedicine, name="addMedicine"),
    path('delete-medicine/', deleteMedicine, name="deleteMedicine"),
    path('search-medicine/', searchMedicine, name="searchMedicine"),
    path('place-order/', placeOrder, name="placeOrder"),
    path('book-appointment/', bookAppointment, name="bookAppointment"),
    path('update-shop/', updateShop, name="updateShop"),
    path('update-appointment/', updateAppointment, name="updateAppointment"),
    path('user-logout/', userLogout, name="userLogout"),
    path('doctor-logout/', doctorLogout, name="doctorLogout"),
    path('medical-logout/', medicalLogout, name="medicalLogout"),
]
