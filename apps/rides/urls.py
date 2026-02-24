from django.urls import path
from . import views

urlpatterns = [
    path('create', views.create_ride,  name='create_ride'),
    path('search', views.search_rides, name='search_rides'),
]
