from django.urls import path
from . import views

urlpatterns = [
    path('create',  views.create_ride,    name='create_ride'),
    path('search',  views.search_rides,   name='search_rides'),
    path('request', views.request_ride,   name='request_ride'),
    path('respond', views.respond_ride,   name='respond_ride'),
]
