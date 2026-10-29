# api/views.py
from django.contrib.gis.db.models.functions import Envelope
from django.db.models import Avg, Count, FloatField, Q, Sum
from django.db.models.expressions import RawSQL
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import geo
from .ai import interpret
from .etl import run_import
from .models import AuditLog, ImportJob, Indicator, Layer, Territory, Tileset
from .serializers import (AIQueryResponseSerializer, AIQuerySerializer, ErrorSerializer,
                          FeatureCollectionSerializer, FeatureQuerySerializer, GeoJSONFeatureSerializer,
                          ImportJobSerializer, IndicatorSerializer, LayerSerializer,
                          SearchResponseSerializer, TerritorySerializer, TerritorySummarySerializer,
                          TilesetSerializer)


def territories_with_envelope(qs):
    """Traz só o retângulo envolvente (bbox) em vez da geometria completa."""
    return qs.annotate(envelope=Envelope('geometry')).defer('geometry')


@extend_schema_view(list=extend_schema(parameters=[
    OpenApiParameter('category', str, description='Categoria: cadastral, fiscal, zoning, infra, land_use, terrain ou socio_env'),
    OpenApiParameter('kind', str, description='territory, parcel, building, tiles3d ou raster'),
]))
class LayerViewSet(viewsets.ReadOnlyModelViewSet):
    """Catálogo de camadas. Camadas privadas só aparecem para usuários logados."""
    serializer_class = LayerSerializer

    def get_queryset(self):
        qs = geo.visible_layers(self.request.user).select_related('source').order_by('name')
        p = self.request.query_params
        if p.get('category'):
            qs = qs.filter(category=p['category'])
        if p.get('kind'):
            qs = qs.filter(kind=p['kind'])
        return qs


@extend_schema_view(list=extend_schema(parameters=[
    OpenApiParameter('type', str, description='municipio, bairro ou setor'),
    OpenApiParameter('code', str, description='Código exato do território'),
    OpenApiParameter('name', str, description='Parte do nome (sem diferenciar maiúsculas)'),
    OpenApiParameter('parent', str, description='Código do território pai (ex.: município de um bairro)'),
    OpenApiParameter('bbox', str, description='Extensão espacial: minLon,minLat,maxLon,maxLat'),
    OpenApiParameter('contains', str, description='Territórios que contêm o ponto lon,lat'),
]))
class TerritoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TerritorySerializer

    def get_queryset(self):
        qs = territories_with_envelope(Territory.objects.select_related('parent').order_by('name'))
        p = self.request.query_params
        if p.get('type'):
            qs = qs.filter(type=p['type'])
        if p.get('code'):
            qs = qs.filter(code=p['code'])
        if p.get('name'):
            qs = qs.filter(name__icontains=p['name'])
        if p.get('parent'):
            qs = qs.filter(parent__code=p['parent'])
        if p.get('bbox'):
            qs = qs.filter(geometry__intersects=geo.parse_bbox(p['bbox']))
        if p.get('contains'):
            qs = qs.filter(geometry__contains=geo.parse_point(p['contains'], 'contains'))
        return qs

    @extend_schema(responses=TerritorySummarySerializer,
                   description='Agregação espacial: lotes, edificações, uso do solo e indicadores mais '
                               'recentes de cada categoria dentro do território.')
    @action(detail=True)
    def summary(self, request, pk=None, **kwargs):
        t = get_object_or_404(Territory.objects.select_related('parent'), pk=pk)
        inside = Q(territory=t)
        if t.geometry is not None:
            inside |= Q(geometry__intersects=t.geometry)
        parcels = geo.base_queryset('parcel', request.user).filter(inside)
        buildings = geo.base_queryset('building', request.user).filter(inside)
        p_agg = parcels.aggregate(n=Count('id'), area=Sum('area_m2'))
        b_agg = buildings.aggregate(n=Count('id'), h=Avg('height_m'))
        land_use = dict(parcels.exclude(land_use='').values_list('land_use')
                        .annotate(n=Count('id')).order_by('land_use'))
        area_km2 = None
        if t.geometry is not None:
            # área em metros calculada sobre o esferoide (não assume grau = metro)
            area_m2 = Territory.objects.filter(pk=t.pk).annotate(a=RawSQL(
                'ST_Area("api_territory"."geometry"::geography)', [], output_field=FloatField())
            ).values_list('a', flat=True)[0]
            area_km2 = round(area_m2 / 1e6, 3)
        latest = {}
        for ind in geo.visible_indicators(request.user, t.indicators.all()) \
                .select_related('territory', 'source', 'parcel').order_by('-period'):
            latest.setdefault((ind.category, ind.name), ind)
        return Response({
            'territory': TerritorySerializer(territories_with_envelope(Territory.objects.filter(pk=t.pk))
                                             .select_related('parent').get()).data,
            'area_km2': area_km2,
            'parcels': p_agg['n'], 'parcels_area_m2': geo.to_float(p_agg['area']),
            'buildings': b_agg['n'],
            'buildings_avg_height_m': round(float(b_agg['h']), 2) if b_agg['h'] is not None else None,
            'land_use': land_use,
            'indicators': IndicatorSerializer(latest.values(), many=True).data,
        })


@extend_schema_view(list=extend_schema(parameters=[
    OpenApiParameter('territory', str, description='Código do território'),
    OpenApiParameter('parcel', str, description='Código cadastral do lote'),
    OpenApiParameter('category', str, description='Categoria do indicador'),
    OpenApiParameter('period', str, description='Data do período, formato AAAA-MM-DD'),
    OpenApiParameter('period_from', str, description='Série temporal: período inicial (AAAA-MM-DD)'),
    OpenApiParameter('period_to', str, description='Série temporal: período final (AAAA-MM-DD)'),
]))
class IndicatorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Indicator.objects.select_related('territory', 'source', 'parcel').order_by('-period')
    serializer_class = IndicatorSerializer

    def get_queryset(self):
        qs = geo.visible_indicators(self.request.user, super().get_queryset())
        p = self.request.query_params
        if p.get('territory'):
            qs = qs.filter(territory__code=p['territory'])
        if p.get('parcel'):
            qs = qs.filter(parcel__code=p['parcel'])
        if p.get('category'):
            qs = qs.filter(category=p['category'])
        if p.get('period'):
            qs = qs.filter(period=p['period'])
        if p.get('period_from'):
            qs = qs.filter(period__gte=p['period_from'])
        if p.get('period_to'):
            qs = qs.filter(period__lte=p['period_to'])
        return qs


class SearchView(APIView):
    MAX_RESULTS = 20

    @extend_schema(
        parameters=[OpenApiParameter('q', str, required=True,
                                     description='Nome, código, endereço, código de lote ou coordenada "lon,lat" '
                                                 '(mínimo 2 caracteres)')],
        responses={200: SearchResponseSerializer, 400: ErrorSerializer},
    )
    def get(self, request, **kwargs):
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response(
                {'detail': 'Informe "q" com pelo menos 2 caracteres (nome ou código de território, ou nome de camada).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        n = self.MAX_RESULTS
        territories = territories_with_envelope(Territory.objects.select_related('parent'))
        parcels = geo.base_queryset('parcel', request.user)
        buildings = geo.base_queryset('building', request.user)
        point = self._as_point(q)

        if point is not None:
            # busca por coordenada: o que existe naquele ponto do mapa
            territories = territories.filter(geometry__contains=point).order_by('type')
            parcels = parcels.filter(geometry__contains=point)
            buildings = buildings.filter(geometry__contains=point)
            layers = Layer.objects.none()
        else:
            territories = territories.filter(Q(name__icontains=q) | Q(code__icontains=q)).order_by('name')
            parcels = parcels.filter(Q(code__icontains=q) | Q(address__icontains=q)).order_by('code')
            buildings = buildings.filter(name__icontains=q).order_by('name')
            layers = geo.visible_layers(request.user).filter(name__icontains=q) \
                .select_related('source').order_by('name')

        data = {
            'query': q,
            'territories': TerritorySerializer(territories[:n], many=True).data,
            'layers': LayerSerializer(layers[:n], many=True).data,
            'parcels': [{'id': f'parcel.{p.pk}', **geo.properties('parcel', p)} for p in parcels.defer('geometry')[:n]],
            'buildings': [{'id': f'building.{b.pk}', **geo.properties('building', b)}
                          for b in buildings.defer('geometry')[:n]],
        }
        if not any(data[k] for k in ('territories', 'layers', 'parcels', 'buildings')):
            data['message'] = f'Nenhum dado encontrado para "{q}".'
        return Response(data)

    @staticmethod
    def _as_point(q):
        parts = q.split(',')
        if len(parts) != 2:
            return None
        try:
            return geo.parse_point(q, 'q')
        except Exception:
            return None


FEATURE_PARAMS = [
    OpenApiParameter('kind', str, description='territory, parcel ou building (obrigatório se não houver "layer")'),
    OpenApiParameter('layer', int, description='ID da camada; define o tipo de feição'),
    OpenApiParameter('bbox', str, description='Recorte pela área visível: minLon,minLat,maxLon,maxLat'),
    OpenApiParameter('territory', str, description='Código do território (feições dentro dele)'),
    OpenApiParameter('near', str, description='Proximidade: ponto lon,lat'),
    OpenApiParameter('radius', float, description='Raio em metros para "near" (padrão 500, máx. 5000)'),
    OpenApiParameter('type', str, description='Territórios: municipio, bairro ou setor'),
    OpenApiParameter('land_use', str, description='Lotes: uso do solo'),
    OpenApiParameter('zoning', str, description='Lotes: zoneamento'),
    OpenApiParameter('use', str, description='Edificações: uso'),
    OpenApiParameter('min_height', float, description='Edificações: altura mínima em metros'),
    OpenApiParameter('limit', int, description='Máximo de feições (padrão 200, máx. 1000)'),
    OpenApiParameter('simplify', float, description='Tolerância de simplificação em graus (ex.: 0.0001)'),
]


class FeatureListView(APIView):
    @extend_schema(parameters=FEATURE_PARAMS, responses={200: FeatureCollectionSerializer, 400: ErrorSerializer},
                   operation_id='features_list',
                   description='Feições em GeoJSON (EPSG:4326) filtradas por camada, área ou atributos. '
                               'Use "bbox" com a área visível do mapa e "simplify" em zoom distante.')
    def get(self, request, **kwargs):
        p = request.query_params
        kind = p.get('kind')
        if p.get('layer'):
            layer = geo.visible_layers(request.user).filter(pk=p['layer']).first() \
                if p['layer'].isdigit() else None
            if layer is None:
                return Response({'detail': 'Camada não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
            if layer.kind not in geo.MODELS:
                return Response({'detail': f'A camada é do tipo "{layer.kind}": use /tilesets/.'},
                                status=status.HTTP_400_BAD_REQUEST)
            kind = layer.kind
        if kind not in geo.MODELS:
            return Response({'detail': 'Informe "kind" (territory, parcel ou building) ou "layer".'},
                            status=status.HTTP_400_BAD_REQUEST)
        qs = geo.apply_filters(geo.base_queryset(kind, request.user), kind, p)
        return Response(geo.feature_collection(qs, kind, geo.parse_limit(p.get('limit')),
                                               geo.parse_simplify(p.get('simplify'))))


class FeatureQueryView(APIView):
    # POST só porque a geometria não cabe na URL: é uma leitura, aberta como o GET de /features/
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=FeatureQuerySerializer,
                   responses={200: FeatureCollectionSerializer, 400: ErrorSerializer},
                   operation_id='features_query',
                   description='Filtro por área desenhada no mapa: devolve as feições que intersectam o polígono.')
    def post(self, request, **kwargs):
        s = FeatureQuerySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        kind = s.validated_data['kind']
        area = geo.parse_area(s.validated_data['geometry'])
        qs = geo.base_queryset(kind, request.user).filter(geometry__intersects=area)
        return Response(geo.feature_collection(qs, kind, geo.parse_limit(s.validated_data.get('limit')),
                                               geo.parse_simplify(s.validated_data.get('simplify'))))


class FeatureDetailView(APIView):
    @extend_schema(responses={200: GeoJSONFeatureSerializer, 404: ErrorSerializer},
                   operation_id='features_detail',
                   description='Detalhe da feição clicada no mapa (geometria completa, atributos e indicadores). '
                               '"kind" e "id" vêm do id da feição no GeoJSON, ex.: parcel.12.')
    def get(self, request, kind, pk, **kwargs):
        if kind not in geo.MODELS:
            return Response({'detail': 'Feição não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        obj = geo.base_queryset(kind, request.user).filter(pk=pk).first()
        if obj is None:
            return Response({'detail': 'Feição não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        data = geo.feature(kind, obj, obj.geometry.geojson if obj.geometry else None)
        if kind == 'territory':
            indicators = geo.visible_indicators(request.user, obj.indicators.all())
        elif kind == 'parcel':
            indicators = obj.indicators.all()  # o lote já passou pelo filtro de visibilidade
            buildings = geo.base_queryset('building', request.user).filter(parcel=obj)
            data['properties']['buildings'] = [f'building.{b}' for b in buildings.values_list('pk', flat=True)]
        else:
            indicators = obj.parcel.indicators.all() if obj.parcel else Indicator.objects.none()
        data['properties']['indicators'] = IndicatorSerializer(
            indicators.select_related('territory', 'source', 'parcel').order_by('-period')[:50], many=True).data
        return Response(data)


@extend_schema_view(list=extend_schema(parameters=[
    OpenApiParameter('layer', int, description='ID da camada'),
    OpenApiParameter('territory', str, description='Código do território'),
    OpenApiParameter('format', str, description='3dtiles, xyz, wmts ou terrain'),
]))
class TilesetViewSet(viewsets.ReadOnlyModelViewSet):
    """Metadados e URLs de tiles 3D/raster. Os arquivos ficam em object storage/CDN."""
    serializer_class = TilesetSerializer

    def get_queryset(self):
        qs = Tileset.objects.filter(is_active=True, layer__in=geo.visible_layers(self.request.user)) \
            .select_related('territory').order_by('name')
        p = self.request.query_params
        if p.get('layer'):
            qs = qs.filter(layer_id=p['layer'])
        if p.get('territory'):
            qs = qs.filter(territory__code=p['territory'])
        if p.get('format'):
            qs = qs.filter(format=p['format'])
        return qs


class ImportJobViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       viewsets.GenericViewSet):
    """Importação de GeoJSON (somente administrador). Com arquivo, o processamento roda na hora
    e a resposta já traz o resultado; sem arquivo, o job fica 'pending' (carga externa)."""
    queryset = ImportJob.objects.select_related('source').order_by('-created_at')
    serializer_class = ImportJobSerializer
    permission_classes = [permissions.IsAdminUser]  # "quando autorizado", como no PDF
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        job = serializer.save(created_by=self.request.user)
        AuditLog.objects.create(user=self.request.user, action='import.create', target=f'ImportJob:{job.pk}',
                                detail={'source': job.source_id, 'target': job.target,
                                        'file': job.file.name if job.file else None})
        if job.file:
            run_import(job)


class AIQueryView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai'

    @extend_schema(
        request=AIQuerySerializer,
        responses={200: AIQueryResponseSerializer, 400: ErrorSerializer, 429: ErrorSerializer},
        description='Pergunta em linguagem natural. A resposta é montada só com dados do banco e sempre cita a fonte. '
                    'Limite: 10 requisições por minuto (429 ao exceder).',
        examples=[
            OpenApiExample('Com dados', response_only=True, status_codes=['200'], value={
                'status': 'ok',
                'parameters': {'territory': '2611606', 'category': 'zoning'},
                'answer': 'Dados encontrados para Recife:\nZona ZUR-1: 12.5000 % (2024) — fonte: Prefeitura do Recife',
                'sources': ['Prefeitura do Recife'],
                'records': [{'id': 1, 'territory': '2611606', 'parcel': None, 'category': 'zoning',
                             'name': 'Zona ZUR-1', 'value': '12.5000', 'unit': '%', 'period': '2024-01-01',
                             'source': 'Prefeitura do Recife'}],
            }),
            OpenApiExample('Pergunta sem território', response_only=True, status_codes=['200'], value={
                'status': 'needs_more_info',
                'message': 'Não identifiquei o território. Informe o município ou bairro da análise.'}),
            OpenApiExample('Sem dados', response_only=True, status_codes=['200'], value={
                'status': 'no_data',
                'message': 'Não há dados disponíveis para "Recife" na categoria "fiscal".'}),
        ],
    )
    def post(self, request, **kwargs):
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

        qs = geo.visible_indicators(request.user).filter(territory=territory)
        if category:
            qs = qs.filter(category=category)
        records = list(qs.select_related('territory', 'source', 'parcel').order_by('-period')[:20])

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
