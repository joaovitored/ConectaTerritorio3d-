# api/serializers.py
from django.conf import settings
from rest_framework import serializers

from .models import ImportJob, Indicator, Layer, Source, Territory, Tileset


class LayerSerializer(serializers.ModelSerializer):
    source = serializers.CharField(source='source.name')

    class Meta:
        model = Layer
        fields = ['id', 'name', 'category', 'kind', 'description', 'source', 'owner',
                  'scale', 'style', 'is_public', 'updated_at']


class TerritorySerializer(serializers.ModelSerializer):
    # devolve o CÓDIGO do território pai (o mesmo valor aceito no filtro ?parent=)
    parent = serializers.SlugRelatedField(slug_field='code', read_only=True, allow_null=True)
    bbox = serializers.SerializerMethodField(help_text='[minLon, minLat, maxLon, maxLat] ou null')

    class Meta:
        model = Territory
        fields = ['id', 'type', 'code', 'name', 'parent', 'bbox']

    def get_bbox(self, obj) -> list[float] | None:
        # extensão para o Cesium enquadrar a câmera sem baixar a geometria inteira
        # (as views anotam "envelope" e adiam a geometria completa)
        geom = getattr(obj, 'envelope', None) or obj.geometry
        return [round(v, 6) for v in geom.extent] if geom else None


class IndicatorSerializer(serializers.ModelSerializer):
    territory = serializers.CharField(source='territory.code')
    parcel = serializers.CharField(source='parcel.code', allow_null=True, default=None)
    source = serializers.CharField(source='source.name')

    class Meta:
        model = Indicator
        fields = ['id', 'territory', 'parcel', 'category', 'name', 'value', 'unit', 'period', 'source']


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ['id', 'name', 'license', 'collected_at', 'import_method', 'version', 'quality']


class TilesetSerializer(serializers.ModelSerializer):
    layer = serializers.IntegerField(source='layer_id')
    territory = serializers.CharField(source='territory.code', allow_null=True, default=None)

    class Meta:
        model = Tileset
        fields = ['id', 'name', 'format', 'url', 'layer', 'territory', 'version', 'updated_at']


class ImportJobSerializer(serializers.ModelSerializer):
    ALLOWED_EXTENSIONS = ('.geojson', '.json')

    class Meta:
        model = ImportJob
        fields = ['id', 'source', 'layer', 'target', 'file', 'status', 'version',
                  'records_processed', 'records_failed', 'error_log',
                  'created_at', 'started_at', 'finished_at']
        read_only_fields = ['status', 'records_processed', 'records_failed', 'error_log',
                            'created_at', 'started_at', 'finished_at']

    def validate_file(self, f):
        if f is None:
            return f
        if not f.name.lower().endswith(self.ALLOWED_EXTENSIONS):
            raise serializers.ValidationError('Envie um arquivo .geojson ou .json.')
        max_mb = settings.IMPORT_MAX_UPLOAD_MB
        if f.size > max_mb * 1024 * 1024:
            raise serializers.ValidationError(f'Arquivo maior que {max_mb} MB.')
        return f

    def validate(self, attrs):
        if attrs.get('file') and not attrs.get('target'):
            raise serializers.ValidationError({'target': 'Informe o destino: territory, parcel ou building.'})
        layer = attrs.get('layer')
        if layer and attrs.get('target') and layer.kind != attrs['target']:
            raise serializers.ValidationError({'layer': f'A camada é do tipo "{layer.kind}".'})
        return attrs


class AIQuerySerializer(serializers.Serializer):
    question = serializers.CharField(min_length=5, max_length=500)


class FeatureQuerySerializer(serializers.Serializer):
    """Corpo do filtro por área desenhada no mapa."""
    kind = serializers.ChoiceField(choices=['territory', 'parcel', 'building'])
    geometry = serializers.JSONField(help_text='Polygon ou MultiPolygon GeoJSON em EPSG:4326')
    limit = serializers.IntegerField(required=False, min_value=1)
    simplify = serializers.FloatField(required=False, min_value=0)

# ---- Serializers usados só para documentar as respostas no Swagger/OpenAPI ----

class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class SearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    territories = TerritorySerializer(many=True)
    layers = LayerSerializer(many=True)
    parcels = serializers.ListField(child=serializers.DictField())
    buildings = serializers.ListField(child=serializers.DictField())
    message = serializers.CharField(required=False, help_text='Só aparece quando nada foi encontrado')


class AIParametersSerializer(serializers.Serializer):
    territory = serializers.CharField(help_text='Código do território identificado')
    category = serializers.CharField(allow_null=True, help_text='Categoria identificada (ou null)')


class AIQueryResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['ok', 'needs_more_info', 'no_data'])
    message = serializers.CharField(required=False, help_text='Presente em needs_more_info e no_data')
    parameters = AIParametersSerializer(required=False)
    answer = serializers.CharField(required=False, help_text='Texto montado só com dados do banco (status ok)')
    sources = serializers.ListField(child=serializers.CharField(), required=False)
    records = IndicatorSerializer(many=True, required=False)


class GeoJSONFeatureSerializer(serializers.Serializer):
    type = serializers.CharField(default='Feature')
    id = serializers.CharField(help_text='"<tipo>.<id>", ex.: parcel.12')
    geometry = serializers.DictField()
    properties = serializers.DictField()


class FeatureCollectionSerializer(serializers.Serializer):
    type = serializers.CharField(default='FeatureCollection')
    features = GeoJSONFeatureSerializer(many=True)
    numberMatched = serializers.IntegerField()
    numberReturned = serializers.IntegerField()
    truncated = serializers.BooleanField(help_text='true quando há mais feições que o limite')


class TerritorySummarySerializer(serializers.Serializer):
    territory = TerritorySerializer()
    area_km2 = serializers.FloatField(allow_null=True)
    parcels = serializers.IntegerField()
    parcels_area_m2 = serializers.FloatField(allow_null=True)
    buildings = serializers.IntegerField()
    buildings_avg_height_m = serializers.FloatField(allow_null=True)
    land_use = serializers.DictField(child=serializers.IntegerField())
    indicators = IndicatorSerializer(many=True)
