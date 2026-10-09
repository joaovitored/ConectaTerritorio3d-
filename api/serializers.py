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