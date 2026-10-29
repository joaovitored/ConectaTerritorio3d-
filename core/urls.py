"""
URL configuration for core project.

/api/v1/  → versão atual da API (documentada no Swagger)
/api/     → alias da v1 mantido para não quebrar o front; será removido na v2
"""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/', include(('api.urls', 'api'), namespace='v1')),
    path('api/', include('api.urls')),
]
