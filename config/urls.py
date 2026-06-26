"""
Root URL configuration.

URL structure (v1):
  /api/v1/auth/          → Authentication (OTP, token refresh)
  /api/v1/rides/         → Ride lifecycle
  /api/v1/users/         → User profiles
  /api/v1/reviews/       → Reviews
  /api/v1/verification/  → Identity verification
  /health                → Health check (unauthenticated)

Legacy routes (no prefix) are preserved with HTTP 301 redirects
so existing app installs keep working during the transition.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.generic import RedirectView
from apps.verification.admin import verification_admin


# ─── Health check ─────────────────────────────────────────
def health(request):
    return JsonResponse({'status': 'ok', 'version': 'v1'})


# ─── v1 API routes ────────────────────────────────────────
v1_patterns = [
    path('auth/',         include('apps.authentication.urls')),
    path('rides/',        include('apps.rides.urls')),
    path('users/',        include('apps.users.urls')),
    path('reviews/',      include('apps.reviews.urls')),
    path('verification/', include('apps.verification.urls')),
]

urlpatterns = [
    # Internal / admin
    path('admin/',               admin.site.urls),
    path('admin-panel/',  include(verification_admin.get_urls())),

    # Health (no auth required)
    path('health',               health, name='health'),
    path('ping',                 include('apps.core.urls')),

    # ── Versioned API (current) ──────────────────────────
    path('api/v1/',              include(v1_patterns)),

    # ── Legacy unversioned routes (301 → v1) ────────────
    # Allows old app builds to keep working during rollout
    re_path(r'^auth/(?P<rest>.*)$',         RedirectView.as_view(url='/api/v1/auth/%(rest)s',         permanent=True)),
    re_path(r'^rides/(?P<rest>.*)$',        RedirectView.as_view(url='/api/v1/rides/%(rest)s',        permanent=True)),
    re_path(r'^users/(?P<rest>.*)$',        RedirectView.as_view(url='/api/v1/users/%(rest)s',        permanent=True)),
    re_path(r'^reviews/(?P<rest>.*)$',      RedirectView.as_view(url='/api/v1/reviews/%(rest)s',      permanent=True)),
    re_path(r'^api/verification/(?P<rest>.*)$', RedirectView.as_view(url='/api/v1/verification/%(rest)s', permanent=True)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
