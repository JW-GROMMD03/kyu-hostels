from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from two_factor.urls import urlpatterns as tf_urls

schema_view = get_schema_view(
    openapi.Info(
        title="Kirinyaga Hostels API",
        default_version='v1',
        description="Complete API for Kirinyaga University Smart Hostel Booking Platform",
        terms_of_service="https://www.kirinyagahostels.com/terms/",
        contact=openapi.Contact(email="admin@kirinyagahostels.com"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    path('admin-panel/', include('two_factor.urls', 'two_factor')),
    
    # API Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # API Endpoints
    path('api/auth/', include('apps.accounts.urls')),
    path('api/hostels/', include('apps.hostels.urls')),
    path('api/bookings/', include('apps.bookings.urls')),
    path('api/payments/', include('apps.payments.urls')),
    path('api/admin/', include('apps.admin_panel.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/roommate/', include('apps.roommate.urls')),
    
    # JWT endpoints
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # Debug toolbar
    path('__debug__/', include('debug_toolbar.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)