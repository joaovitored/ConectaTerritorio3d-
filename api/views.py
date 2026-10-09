# api/views.py
from rest_framework import viewsets
from .models import Layer
from .serializers import LayerSerializer
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import mixins, permissions
from .models import ImportJob
from .serializers import ImportJobSerializer, AIQuerySerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from .ai import interpret
from .models import Indicator

class LayerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Layer.objects.filter(is_active=True).select_related('source').order_by('name')
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

    @extend_schema(
        parameters=[OpenApiParameter('q', str, required=True,
                                     description='Nome ou código (mínimo 2 caracteres)')],
        responses=OpenApiTypes.OBJECT,
    )
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
    @extend_schema(responses=OpenApiTypes.OBJECT, operation_id='features_list')
    def get(self, request):
        return Response({
            'count': 0, 'next': None, 'previous': None, 'results': [],
            'message': 'Feições indisponíveis: aguardam o modelo geoespacial (PostGIS).',
        })


class FeatureDetailView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT, operation_id='features_detail')
    def get(self, request, pk):
        return Response({'detail': 'Feição não encontrada.'}, status=status.HTTP_404_NOT_FOUND)


class TilesetListView(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT, operation_id='tilesets_list')
    def get(self, request):
        return Response({'count': 0, 'results': [], 'message': 'Nenhum tileset publicado.'})


class ImportJobViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = ImportJob.objects.select_related('source').order_by('-created_at')
    serializer_class = ImportJobSerializer
    permission_classes = [permissions.IsAdminUser]  # "quando autorizado", como no PDF


class AIQueryView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai'

    @extend_schema(request=AIQuerySerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        if not hasattr(request.data, 'get'):
            return Response({'detail': 'Corpo inválido: envie um JSON como {"question": "..."}.'},
                            status=status.HTTP_400_BAD_REQUEST)
        question = str(request.data.get('question', '')).strip()
        if len(question) < 5:
            return Response({'detail': 'Envie "question" com a pergunta.'},
                            status=status.HTTP_400_BAD_REQUEST)

        params = interpret(question)
        territory, category = params['territory'], params['category']

        # US11: pergunta sem localização
        if territory is None:
            return Response({
                'status': 'needs_more_info',
                'message': 'Não identifiquei o território. Informe o município ou bairro da análise.',
            })

        qs = Indicator.objects.filter(territory=territory)
        if category:
            qs = qs.filter(category=category)
        records = list(qs.select_related('territory', 'source').order_by('-period')[:20])

        # US10: sem dados
        if not records:
            return Response({
                'status': 'no_data',
                'message': f'Não há dados disponíveis para "{territory.name}"'
                           + (f' na categoria "{category}".' if category else '.'),
            })

        # US08/US09: resposta montada só com o que veio do banco, com a fonte de cada item
        lines = [f'{r.name}: {r.value} {r.unit} ({r.period:%Y}) — fonte: {r.source.name}'
                 for r in records]
        return Response({
            'status': 'ok',
            'parameters': {'territory': territory.code, 'category': category},
            'answer': f'Dados encontrados para {territory.name}:\n' + '\n'.join(lines),
            'sources': sorted({r.source.name for r in records}),
            'records': IndicatorSerializer(records, many=True).data,
        })