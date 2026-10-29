from django.urls import path
from rest_framework.routers import DefaultRouter

from .auth import LoginView, LogoutView, MeView
from .views import (AIQueryView, FeatureDetailView, FeatureListView, FeatureQueryView, ImportJobViewSet,
                    IndicatorViewSet, LayerViewSet, SearchView, TerritoryViewSet, TilesetViewSet)

router = DefaultRouter()

router.register('layers', LayerViewSet, basename='layer')
router.register('territories', TerritoryViewSet, basename='territory')
router.register('indicators', IndicatorViewSet, basename='indicator')
router.register('tilesets', TilesetViewSet, basename='tileset')
router.register('imports', ImportJobViewSet, basename='import')

urlpatterns = router.urls + [
    path('search/', SearchView.as_view(), name='search'),
    path('features/', FeatureListView.as_view(), name='feature-list'),
    path('features/query/', FeatureQueryView.as_view(), name='feature-query'),
    path('features/<str:kind>/<int:pk>/', FeatureDetailView.as_view(), name='feature-detail'),
    path('ai/query/', AIQueryView.as_view(), name='ai-query'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
]
