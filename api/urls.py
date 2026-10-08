from rest_framework.routers import DefaultRouter
from .views import LayerViewSet, TerritoryViewSet, IndicatorViewSet

router = DefaultRouter()

router.register('layers', LayerViewSet, basename='layer')
router.register('territories', TerritoryViewSet, basename='territory')
router.register('indicators', IndicatorViewSet, basename='indicator')

urlpatterns = router.urls