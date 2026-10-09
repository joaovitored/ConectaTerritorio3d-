# api/views.py
from rest_framework import viewsets
from .models import Layer
from .serializers import LayerSerializer
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import mixins, permissions
from .models import ImportJob
from .serializers import ImportJobSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter


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



class SearchView(APIView):
    MAX_RESULTS = 20

    @extend_schema(parameters=[
        OpenApiParameter('q', str, required=True, description='Nome ou código (mínimo 2 caracteres)'),
    ])

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response(
                {'detail': 'Informe "q" com pelo menos 2 caracteres (nome ou código de território, ou nome de camada).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        territories = Territory.objects.filter(
            Q(name__icontains=q) | Q(code__icontains=q)
        ).order_by('name')[:self.MAX_RESULTS]

        layers = Layer.objects.filter(
            is_active=True, name__icontains=q
        ).select_related('source').order_by('name')[:self.MAX_RESULTS]

        data = {
            'query': q,
            'territories': TerritorySerializer(territories, many=True).data,
            'layers': LayerSerializer(layers, many=True).data,
        }
        if not data['territories'] and not data['layers']:
            data['message'] = f'Nenhum dado encontrado para "{q}".'
        return Response(data)


class FeatureListView(APIView):
    def get(self, request):
        return Response({
            'count': 0, 'next': None, 'previous': None, 'results': [],
            'message': 'Feições indisponíveis: aguardam o modelo geoespacial (PostGIS).',
        })


class FeatureDetailView(APIView):
    def get(self, request, pk):
        return Response({'detail': 'Feição não encontrada.'}, status=status.HTTP_404_NOT_FOUND)


class TilesetListView(APIView):
    def get(self, request):
        return Response({'count': 0, 'results': [], 'message': 'Nenhum tileset publicado.'})


class ImportJobViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = ImportJob.objects.select_related('source').order_by('-created_at')
    serializer_class = ImportJobSerializer
    permission_classes = [permissions.IsAdminUser]  # "quando autorizado", como no PDF