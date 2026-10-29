# api/geo.py — consultas espaciais e montagem de GeoJSON para o Cesium
import json

from django.conf import settings
from django.contrib.gis.db.models.functions import AsGeoJSON, GeomOutputGeoFunc
from django.contrib.gis.geos import GEOSException, GEOSGeometry, MultiPolygon, Point, Polygon
from django.contrib.gis.measure import D
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from .models import SRID, Building, Indicator, Layer, Parcel, Territory

MODELS = {'territory': Territory, 'parcel': Parcel, 'building': Building}
MAX_RADIUS_M = 5000
MAX_SIMPLIFY_DEG = 0.01


class SimplifyPreserveTopology(GeomOutputGeoFunc):
    function = 'ST_SimplifyPreserveTopology'
    arity = 2


def to_float(v):
    return float(v) if v is not None else None


def visible_layers(user):
    qs = Layer.objects.filter(is_active=True)
    return qs if user.is_authenticated else qs.filter(is_public=True)


def visible_parcel_q(user, prefix=''):
    """Lote visível: sem camada ou de camada visível. `prefix` permite filtrar por relação (ex.: 'parcel__')."""
    return (Q(**{f'{prefix}isnull': True}) if prefix else Q()) | Q(**{f'{prefix}layer__isnull': True}) \
        | Q(**{f'{prefix}layer__in': visible_layers(user)})


def visible_indicators(user, qs=None):
    """Indicadores de lotes privados só aparecem para quem pode ver o lote."""
    qs = Indicator.objects.all() if qs is None else qs
    return qs.filter(visible_parcel_q(user, 'parcel__'))


def base_queryset(kind, user):
    """Feições que o usuário pode ver: lotes/edificações de camadas privadas só com login."""
    # as geometrias dos objetos relacionados nunca são usadas: não trazê-las do banco
    if kind == 'territory':
        return Territory.objects.filter(geometry__isnull=False).select_related('parent') \
            .defer('parent__geometry')
    qs = MODELS[kind].objects.select_related('territory', 'layer', 'source').defer('territory__geometry')
    if kind == 'building':
        # a edificação herda a privacidade do lote (senão vazaria o código e os indicadores dele)
        qs = qs.select_related('parcel').defer('parcel__geometry').filter(visible_parcel_q(user, 'parcel__'))
    return qs.filter(Q(layer__isnull=True) | Q(layer__in=visible_layers(user)))


# ---------- validação de parâmetros espaciais ----------

def parse_floats(value, n, name):
    try:
        nums = [float(v) for v in value.split(',')]
    except (AttributeError, ValueError):
        nums = []
    if len(nums) != n:
        raise ValidationError({name: f'Use {n} números separados por vírgula.'})
    return nums


def parse_point(value, name='point'):
    lon, lat = parse_floats(value, 2, name)
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValidationError({name: 'Coordenada fora do intervalo (lon -180..180, lat -90..90).'})
    return Point(lon, lat, srid=SRID)


def parse_bbox(value):
    min_lon, min_lat, max_lon, max_lat = parse_floats(value, 4, 'bbox')
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValidationError({'bbox': 'Use minLon,minLat,maxLon,maxLat com mínimos menores que máximos.'})
    if (max_lon - min_lon) * (max_lat - min_lat) > settings.FEATURES_MAX_BBOX_DEG2:
        raise ValidationError({'bbox': 'Área muito grande: aproxime o mapa ou filtre por território.'})
    return Polygon.from_bbox((min_lon, min_lat, max_lon, max_lat))


def parse_area(geojson):
    """Polígono desenhado pelo usuário (GeoJSON) → geometria validada."""
    try:
        g = GEOSGeometry(json.dumps(geojson) if isinstance(geojson, dict) else str(geojson), srid=SRID)
    except (GEOSException, ValueError, TypeError):
        raise ValidationError({'geometry': 'GeoJSON inválido.'})
    if not isinstance(g, (Polygon, MultiPolygon)):
        raise ValidationError({'geometry': 'Use Polygon ou MultiPolygon.'})
    if not g.valid:
        raise ValidationError({'geometry': f'Geometria inválida: {g.valid_reason}'})
    if g.envelope.area > settings.FEATURES_MAX_BBOX_DEG2:
        raise ValidationError({'geometry': 'Área muito grande.'})
    return g


def parse_limit(value):
    if value in (None, ''):
        return settings.FEATURES_DEFAULT_LIMIT
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError({'limit': 'Use um número inteiro.'})
    return max(1, min(n, settings.FEATURES_MAX_LIMIT))


def parse_simplify(value):
    if value in (None, ''):
        return 0
    try:
        t = float(value)
    except (TypeError, ValueError):
        raise ValidationError({'simplify': 'Use a tolerância em graus, ex.: 0.0001.'})
    return max(0.0, min(t, MAX_SIMPLIFY_DEG))


def apply_filters(qs, kind, params):
    """Filtros comuns de /features/: área, território, proximidade e atributos."""
    if params.get('bbox'):
        qs = qs.filter(geometry__intersects=parse_bbox(params['bbox']))
    if params.get('territory'):
        t = Territory.objects.filter(code=params['territory']).only('id', 'geometry').first()
        if t is None:
            return qs.none()
        if kind == 'territory':
            qs = qs.filter(Q(pk=t.pk) | Q(parent=t))
        elif t.geometry is not None:
            qs = qs.filter(Q(territory=t) | Q(geometry__intersects=t.geometry))
        else:
            qs = qs.filter(territory=t)
    if params.get('near'):
        radius = params.get('radius') or '500'
        try:
            radius = float(radius)
        except ValueError:
            raise ValidationError({'radius': 'Use o raio em metros.'})
        if not 0 < radius <= MAX_RADIUS_M:
            raise ValidationError({'radius': f'O raio deve estar entre 0 e {MAX_RADIUS_M} m.'})
        qs = qs.filter(geometry__distance_lte=(parse_point(params['near'], 'near'), D(m=radius)))
    if params.get('layer'):
        qs = qs.filter(layer_id=params['layer']) if kind != 'territory' else qs
    if kind == 'territory' and params.get('type'):
        qs = qs.filter(type=params['type'])
    if kind == 'parcel':
        if params.get('land_use'):
            qs = qs.filter(land_use=params['land_use'])
        if params.get('zoning'):
            qs = qs.filter(zoning=params['zoning'])
    if kind == 'building':
        if params.get('use'):
            qs = qs.filter(use=params['use'])
        if params.get('min_height'):
            qs = qs.filter(height_m__gte=parse_floats(params['min_height'], 1, 'min_height')[0])
    return qs


# ---------- GeoJSON ----------

def properties(kind, obj):
    if kind == 'territory':
        return {'kind': kind, 'code': obj.code, 'name': obj.name, 'type': obj.type,
                'parent': obj.parent.code if obj.parent else None}
    common = {'kind': kind, 'territory': obj.territory.code if obj.territory else None,
              'layer': obj.layer_id, 'source': obj.source.name,
              'area_m2': to_float(obj.area_m2)}
    if kind == 'parcel':
        return {**common, 'code': obj.code, 'address': obj.address,
                'land_use': obj.land_use, 'zoning': obj.zoning}
    return {**common, 'name': obj.name, 'use': obj.use, 'floors': obj.floors,
            'height_m': to_float(obj.height_m),'parcel': obj.parcel.code if obj.parcel else None}


def feature(kind, obj, geometry_json):
    return {'type': 'Feature', 'id': f'{kind}.{obj.pk}',
            'geometry': json.loads(geometry_json) if geometry_json else None,
            'properties': properties(kind, obj)}


def feature_collection(qs, kind, limit, simplify=0):
    geom = SimplifyPreserveTopology('geometry', simplify) if simplify else 'geometry'
    total = qs.count()
    rows = qs.annotate(geojson=AsGeoJSON(geom, precision=7)).defer('geometry').order_by('pk')[:limit]
    features = [feature(kind, r, r.geojson) for r in rows]
    return {'type': 'FeatureCollection', 'features': features,
            'numberMatched': total, 'numberReturned': len(features), 'truncated': total > len(features)}
