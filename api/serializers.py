# api/serializers.py (arquivo novo)
from rest_framework import serializers
from .models import Layer, Territory, Indicator
from .models import ImportJob

class LayerSerializer(serializers.ModelSerializer):
    source = serializers.CharField(source='source.name')

    class Meta:
        model = Layer
        fields = ['id', 'name', 'category', 'source', 'updated_at']

# api/serializers.py (acrescente)

class TerritorySerializer(serializers.ModelSerializer):
    # devolve o CÓDIGO do território pai (o mesmo valor aceito no filtro ?parent=)
    parent = serializers.SlugRelatedField(slug_field='code', read_only=True, allow_null=True)

    class Meta:
        model = Territory
        fields = ['id', 'type', 'code', 'name', 'parent']

class IndicatorSerializer(serializers.ModelSerializer):
    territory = serializers.CharField(source='territory.code')
    source = serializers.CharField(source='source.name')

    class Meta:
        model = Indicator
        fields = ['id', 'territory', 'category', 'name', 'value', 'unit', 'period', 'source']


class ImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJob
        fields = ['id', 'source', 'status', 'version', 'error_log', 'created_at', 'finished_at']
        read_only_fields = ['status', 'error_log', 'created_at', 'finished_at']

class AIQuerySerializer(serializers.Serializer):
    question = serializers.CharField(min_length=5, max_length=500)

# ---- Serializers usados só para documentar as respostas no Swagger/OpenAPI ----

class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class SearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    territories = TerritorySerializer(many=True)
    layers = LayerSerializer(many=True)
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


class StubListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True, required=False)
    previous = serializers.CharField(allow_null=True, required=False)
    results = serializers.ListField(child=serializers.DictField())
    message = serializers.CharField()