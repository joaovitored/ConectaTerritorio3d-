from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (LayerViewSet, TerritoryViewSet, IndicatorViewSet, SearchView,
                    FeatureListView, FeatureDetailView, TilesetListView, ImportJobViewSet)


router = DefaultRouter()

router.register('layers', LayerViewSet, basename='layer')
router.register('territories', TerritoryViewSet, basename='territory')
router.register('indicators', IndicatorViewSet, basename='indicator')
from .views import AIQueryView
from .auth import LoginView, MeView, LogoutView

router.register('imports', ImportJobViewSet, basename='import')

urlpatterns = router.urls + [
    path('search/', SearchView.as_view(), name='search'),
    path('features/', FeatureListView.as_view(), name='feature-list'),
    path('features/<int:pk>/', FeatureDetailView.as_view(), name='feature-detail'),
    path('tilesets/', TilesetListView.as_view(), name='tileset-list'),
    path('ai/query/', AIQueryView.as_view(), name='ai-query'),
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),

]