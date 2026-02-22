from django.urls import path
from . import views

urlpatterns = [
    path('me', views.get_me, name='get_me'),
    path('availability', views.update_availability, name='update_availability'),
    path('location', views.update_location, name='update_location'),
]
