# api/etl.py — importação de GeoJSON (territórios, lotes, edificações)
import json
import logging
from decimal import Decimal, InvalidOperation

from django.contrib.gis.gdal import CoordTransform, SpatialReference
from django.contrib.gis.geos import GEOSException, GEOSGeometry, MultiPolygon, Polygon
from django.db import transaction
from django.utils import timezone

from .models import SRID, AuditLog, Building, ImportJob, Parcel, Territory

log = logging.getLogger(__name__)

MAX_ERRORS_LOGGED = 50

# nomes de atributo aceitos em cada campo (o primeiro que existir na feição é usado)
ALIASES = {
    'code': ['code', 'codigo', 'cod_munici', 'CD_MUN', 'cd_mun', 'inscricao', 'id_cadastral'],
    'name': ['name', 'nome', 'nom_munici', 'NM_MUN', 'nm_mun'],
    'type': ['type', 'tipo', 'tipo_territorio'],
    'parent': ['parent', 'pai', 'codigo_pai', 'cod_municipio'],
    'address': ['address', 'endereco', 'logradouro'],
    'area_m2': ['area_m2', 'area'],
    'land_use': ['land_use', 'uso_solo', 'uso'],
    'zoning': ['zoning', 'zoneamento', 'zona'],
    'parcel': ['parcel', 'lote', 'codigo_lote'],
    'use': ['use', 'uso', 'tipo_edificacao'],
    'floors': ['floors', 'pavimentos'],
    'height_m': ['height_m', 'altura_m', 'altura'],
}


class InvalidFileError(Exception):
    """Erro que invalida o arquivo inteiro (formato, CRS...)."""


def _get(props, field):
    for key in ALIASES[field]:
        v = props.get(key)
        if v not in (None, ''):
            return v
    return None


def _decimal(v):
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        raise ValueError(f'valor numérico inválido: {v!r}')


def _source_srid(collection):
    """Lê o CRS declarado no GeoJSON. Sem CRS, o padrão da especificação é WGS84."""
    name = (collection.get('crs') or {}).get('properties', {}).get('name', '')
    if not name or name.endswith('CRS84'):
        return SRID
    try:
        return int(name.rsplit(':', 1)[-1])
    except ValueError:
        raise InvalidFileError(f'CRS não reconhecido: {name}')


def to_multipolygon(geom_json, transform=None):
    """GeoJSON → MultiPolygon válido em SRID 4326."""
    g = GEOSGeometry(json.dumps(geom_json))
    if transform is not None:
        g.srid = transform[0]
        g.transform(transform[1])
    g.srid = SRID
    if not g.valid:
        g = g.make_valid()
    if isinstance(g, Polygon):
        g = MultiPolygon(g, srid=SRID)
    elif not isinstance(g, MultiPolygon):
        # make_valid pode devolver GeometryCollection: fica só com as partes de área
        parts = []
        for p in (g if g.geom_type == 'GeometryCollection' else []):
            if isinstance(p, Polygon):
                parts.append(p)
            elif isinstance(p, MultiPolygon):
                parts.extend(p)
        if not parts:
            raise ValueError(f'geometria {g.geom_type} não é polígono')
        g = MultiPolygon(*parts, srid=SRID)
    if g.empty:
        raise ValueError('geometria vazia')
    return g


def _save_territory(props, geom, job, default_type):
    code, name = _get(props, 'code'), _get(props, 'name')
    if not code or not name:
        raise ValueError('território sem código ou nome')
    parent = None
    if _get(props, 'parent'):
        parent = Territory.objects.filter(code=str(_get(props, 'parent'))).first()
    Territory.objects.update_or_create(code=str(code), defaults={
        'name': str(name), 'type': _get(props, 'type') or default_type,
        'parent': parent, 'source': job.source, 'geometry': geom,
    })


def _territory_for(geom):
    """Território mais específico que contém o centro da geometria (contenção espacial)."""
    point = geom.point_on_surface
    order = {'setor': 0, 'bairro': 1, 'municipio': 2}
    found = list(Territory.objects.filter(geometry__contains=point).only('id', 'type'))
    return min(found, key=lambda t: order.get(t.type, 9), default=None)


def _save_parcel(props, geom, job, default_type):
    code = _get(props, 'code')
    if not code:
        raise ValueError('lote sem identificador cadastral')
    Parcel.objects.update_or_create(code=str(code), defaults={
        'address': str(_get(props, 'address') or ''),
        'area_m2': _decimal(_get(props, 'area_m2')),
        'land_use': str(_get(props, 'land_use') or ''),
        'zoning': str(_get(props, 'zoning') or ''),
        'territory': _territory_for(geom), 'layer': job.layer,
        'source': job.source, 'geometry': geom,
    })


def _save_building(props, geom, job, default_type):
    parcel = None
    if _get(props, 'parcel'):
        parcel = Parcel.objects.filter(code=str(_get(props, 'parcel'))).first()
    floors = _get(props, 'floors')
    Building.objects.create(
        parcel=parcel, territory=parcel.territory if parcel else _territory_for(geom),
        layer=job.layer, source=job.source,
        name=str(_get(props, 'name') or ''), use=str(_get(props, 'use') or ''),
        floors=int(floors) if floors is not None else None,
        height_m=_decimal(_get(props, 'height_m')), area_m2=_decimal(_get(props, 'area_m2')),
        geometry=geom,
    )


SAVERS = {'territory': _save_territory, 'parcel': _save_parcel, 'building': _save_building}


def run_import(job, data=None, default_type='municipio'):
    """Processa o arquivo do job. Cada feição é independente: erros vão para o error_log
    e não interrompem as demais. Erros de arquivo (JSON, CRS) marcam o job como 'failed'."""
    job.status, job.started_at = 'running', timezone.now()
    job.records_processed = job.records_failed = 0
    job.save(update_fields=['status', 'started_at', 'records_processed', 'records_failed'])
    errors = []
    try:
        if data is None:
            with job.file.open('rb') as f:
                data = f.read()
        if isinstance(data, bytes):
            data = data.decode('utf-8-sig')
        collection = json.loads(data)
        if collection.get('type') != 'FeatureCollection':
            raise InvalidFileError('o arquivo deve ser um GeoJSON FeatureCollection')

        srid_in = _source_srid(collection)
        transform = None
        if srid_in != SRID:
            transform = (srid_in, CoordTransform(SpatialReference(srid_in), SpatialReference(SRID)))

        save = SAVERS[job.target]
        for i, feat in enumerate(collection.get('features') or []):
            try:
                with transaction.atomic():
                    geom = to_multipolygon(feat['geometry'], transform)
                    save(feat.get('properties') or {}, geom, job, default_type)
                job.records_processed += 1
            except (ValueError, KeyError, TypeError, GEOSException) as e:
                job.records_failed += 1
                if len(errors) < MAX_ERRORS_LOGGED:
                    errors.append(f'feição {i}: {e}')
        job.status = 'done'
    except (InvalidFileError, json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        job.status = 'failed'
        errors.insert(0, f'arquivo inválido: {e}')

    job.error_log = '\n'.join(errors)
    job.finished_at = timezone.now()
    job.save()
    AuditLog.objects.create(user=job.created_by, action=f'import.{job.status}',
                            target=f'ImportJob:{job.pk}',
                            detail={'processed': job.records_processed, 'failed': job.records_failed})
    log.info('import job=%s status=%s processed=%s failed=%s',
             job.pk, job.status, job.records_processed, job.records_failed)
    return job
