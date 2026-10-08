# api/views.py
from rest_framework import viewsets
from .models import Layer
from .serializers import LayerSerializer

class LayerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Layer.objects.filter(is_active=True).select_related('source')
    serializer_class = LayerSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        return qs.filter(category=category) if category else qs


# api/views.py (acrescente)
from .models import Layer, Territory, Indicator
from .serializers import LayerSerializer, TerritorySerializer, IndicatorSerializer

class TerritoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Territory.objects.all().order_by('name')
    serializer_class = TerritorySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get('type'):
            qs = qs.filter(type=p['type'])
        if p.get('code'):
            qs = qs.filter(code=p['code'])
        if p.get('name'):
            qs = qs.filter(name__icontains=p['name'])
        if p.get('parent'):
            qs = qs.filter(parent__code=p['parent'])
        return qs


class IndicatorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Indicator.objects.select_related('territory', 'source').order_by('-period')
    serializer_class = IndicatorSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get('territory'):
            qs = qs.filter(territory__code=p['territory'])
        if p.get('category'):
            qs = qs.filter(category=p['category'])
        if p.get('period'):
            qs = qs.filter(period=p['period'])
        return qs



