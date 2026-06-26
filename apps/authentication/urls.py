from django.urls import path
from . import views

urlpatterns = [
    path('ping', views.ping, name='ping'),
    path('otp/send', views.send_otp, name='send_otp'),
    path('otp/verify', views.verify_otp_endpoint, name='verify_otp'),
    path('token/refresh', views.refresh_token, name='refresh_token'),
]
