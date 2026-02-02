"""
Verification App URLs
"""
from django.urls import path
from . import views

urlpatterns = [
    path('submit', views.submit_verification, name='submit_verification'),
    path('status', views.get_verification_status, name='verification_status'),
]
