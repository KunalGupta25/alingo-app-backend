from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.verification.admin import verification_admin

urlpatterns = [
    path('admin/', admin.site.urls),
    path('verification-panel/', include(verification_admin.get_urls())),  # Verification admin (no Django auth required)
    path('', include('apps.core.urls')),
    path('auth/', include('apps.authentication.urls')),
    path('api/verification/', include('apps.verification.urls')),
    path('users/', include('apps.users.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
