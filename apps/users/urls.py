from django.urls import path
from . import views

urlpatterns = [
    path('me',                    views.get_me,              name='get_me'),
    path('me/rides',              views.my_ride_history,     name='my_ride_history'),
    path('profile',               views.update_profile,      name='update_profile'),
    path('availability',          views.update_availability, name='update_availability'),
    path('location',              views.update_location,     name='update_location'),
    path('push-token',            views.register_push_token, name='register_push_token'),
    path('<str:user_id>/reviews', views.user_reviews,        name='user_reviews'),
    path('<str:user_id>',         views.public_profile,      name='public_profile'),
]
