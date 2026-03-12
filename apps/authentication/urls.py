from django.urls import path
from . import views

urlpatterns = [
    path('ping', views.ping, name='ping'),
    path('otp/send', views.send_otp, name='send_otp'),
    path('otp/verify', views.verify_otp_endpoint, name='verify_otp'),
    path('signup', views.signup, name='signup'),
    path('login', views.login, name='login'),
]
