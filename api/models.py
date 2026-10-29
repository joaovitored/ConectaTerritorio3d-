# api/models.py
from django.conf import settings
from django.contrib.gis.db import models

# SRID oficial de armazenamento (WGS84). Toda importação é reprojetada para ele.
SRID = 4326


class Source(models.Model):
    QUALITY = [
        ('validated', 'Validado'),
        ('pending', 'Em validação'),
        ('test', 'Dados de teste'),
    ]
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    license = models.CharField(max_length=100, blank=True)
    collected_at = models.DateField(null=True, blank=True)
    import_method = models.CharField(max_length=100, blank=True)  # ex.: "GeoJSON via /api/v1/imports/"
    version = models.CharField(max_length=50, blank=True)
    quality = models.CharField(max_length=20, choices=QUALITY, default='pending')

    def __str__(self):
        return self.name


class Layer(models.Model):
    CATEGORIES = [
        ('cadastral', 'Cadastral e imobiliário'),
        ('fiscal', 'Fiscal'),
        ('zoning', 'Zoneamento e legislação'),
        ('infra', 'Infraestrutura'),
        ('land_use', 'Uso e ocupação do solo'),
        ('terrain', 'Terreno'),
        ('socio_env', 'Socioeconômico e ambiental'),
    ]
    # tipo de dado que a camada entrega ao front (define o endpoint usado pelo Cesium)
    KINDS = [
        ('territory', 'Territórios (GeoJSON)'),
        ('parcel', 'Lotes (GeoJSON)'),
        ('building', 'Edificações (GeoJSON)'),
        ('tiles3d', '3D Tiles'),
        ('raster', 'Raster / XYZ / WMTS'),
    ]
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    kind = models.CharField(max_length=20, choices=KINDS, default='parcel')
    description = models.TextField(blank=True)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='layers')
    owner = models.CharField(max_length=150, blank=True)  # responsável pela camada
    scale = models.CharField(max_length=100, blank=True)
    style = models.JSONField(default=dict, blank=True)    # simbologia/legenda para o Cesium
    is_public = models.BooleanField(default=True)          # privada: só usuários logados
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['category', 'is_active'])]

    def __str__(self):
        return self.name


# api/models.py (adicione abaixo de Layer)
class Territory(models.Model):
    TYPES = [
        ('municipio', 'Município'),
        ('bairro', 'Bairro'),
        ('setor', 'Setor'),
    ]
    type = models.CharField(max_length=20, choices=TYPES)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.PROTECT, related_name='children',
    )
    source = models.ForeignKey(Source, null=True, blank=True, on_delete=models.PROTECT,
                               related_name='territories')
    geometry = models.MultiPolygonField(srid=SRID, null=True, blank=True)  # índice GiST automático
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['type', 'name'])]

    def __str__(self):
        return f'{self.name} ({self.type})'


class Parcel(models.Model):
    """Lote / imóvel."""
    territory = models.ForeignKey(Territory, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='parcels')
    layer = models.ForeignKey(Layer, null=True, blank=True, on_delete=models.PROTECT,
                              related_name='parcels')
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='parcels')
    code = models.CharField(max_length=100, unique=True)  # identificador cadastral
    address = models.CharField(max_length=300, blank=True)
    area_m2 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    land_use = models.CharField(max_length=100, blank=True)
    zoning = models.CharField(max_length=100, blank=True)
    geometry = models.MultiPolygonField(srid=SRID)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['land_use']), models.Index(fields=['zoning'])]

    def __str__(self):
        return self.code


class Building(models.Model):
    """Edificação."""
    parcel = models.ForeignKey(Parcel, null=True, blank=True, on_delete=models.PROTECT,
                               related_name='buildings')
    territory = models.ForeignKey(Territory, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='buildings')
    layer = models.ForeignKey(Layer, null=True, blank=True, on_delete=models.PROTECT,
                              related_name='buildings')
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='buildings')
    name = models.CharField(max_length=150, blank=True)
    use = models.CharField(max_length=100, blank=True)
    floors = models.PositiveIntegerField(null=True, blank=True)
    height_m = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area_m2 = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    geometry = models.MultiPolygonField(srid=SRID)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['use'])]

    def __str__(self):
        return self.name or f'Edificação {self.pk}'


class Indicator(models.Model):
    territory = models.ForeignKey(Territory, on_delete=models.CASCADE, related_name='indicators')
    parcel = models.ForeignKey(Parcel, null=True, blank=True, on_delete=models.CASCADE,
                               related_name='indicators')
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='indicators')
    category = models.CharField(max_length=20, choices=Layer.CATEGORIES)
    name = models.CharField(max_length=200)
    value = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=30, blank=True)
    period = models.DateField()

    class Meta:
        indexes = [models.Index(fields=['category', 'period'])]

    def __str__(self):
        return f'{self.name} - {self.territory.name}'


class Tileset(models.Model):
    """Referência a um tileset publicado em object storage/CDN (o banco não serve o arquivo)."""
    FORMATS = [
        ('3dtiles', '3D Tiles'),
        ('xyz', 'XYZ'),
        ('wmts', 'WMTS'),
        ('terrain', 'Terreno (quantized-mesh)'),
    ]
    layer = models.ForeignKey(Layer, on_delete=models.CASCADE, related_name='tilesets')
    name = models.CharField(max_length=200)
    format = models.CharField(max_length=20, choices=FORMATS)
    url = models.URLField(max_length=500)
    territory = models.ForeignKey(Territory, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name='tilesets')
    version = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ImportJob(models.Model):
    STATUS = [
        ('pending', 'Pendente'),
        ('running', 'Em execução'),
        ('done', 'Concluída'),
        ('failed', 'Falhou'),
    ]
    TARGETS = [
        ('territory', 'Territórios'),
        ('parcel', 'Lotes'),
        ('building', 'Edificações'),
    ]
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='imports')
    layer = models.ForeignKey(Layer, null=True, blank=True, on_delete=models.PROTECT,
                              related_name='imports')
    target = models.CharField(max_length=20, choices=TARGETS, blank=True)
    file = models.FileField(upload_to='imports/%Y/%m/', blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    version = models.CharField(max_length=50, blank=True)
    records_processed = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='imports')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['status'])]


class AuditLog(models.Model):
    """Registro de operações críticas (importações, logins administrativos, alterações)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='audit_logs')
    action = models.CharField(max_length=50)            # ex.: import.create, import.done
    target = models.CharField(max_length=100, blank=True)  # ex.: ImportJob:12
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['action', 'created_at'])]

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.target}'
