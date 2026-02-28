from django.urls import path
from . import views

urlpatterns = [
    path('create',      views.create_ride,    name='create_ride'),
    path('search',      views.search_rides,   name='search_rides'),
    path('request',     views.request_ride,   name='request_ride'),
    path('respond',     views.respond_ride,   name='respond_ride'),
    path('complete',    views.complete_ride,  name='complete_ride'),
    path('my-active',   views.my_active_ride, name='my_active_ride'),
    path('my-requests', views.my_requests,    name='my_requests'),
    path('cancel',      views.cancel_ride,    name='cancel_ride'),
]
