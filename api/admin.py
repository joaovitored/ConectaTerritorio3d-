from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import (AuditLog, Building, ImportJob, Indicator, Layer, Parcel, Source, Territory,
                     Tileset)

admin.site.register([Source, Indicator, Tileset])


@admin.register(Layer)
class LayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'kind', 'is_public', 'is_active', 'updated_at']
    list_filter = ['category', 'kind', 'is_public', 'is_active']


@admin.register(Territory)
class TerritoryAdmin(GISModelAdmin):
    list_display = ['name', 'code', 'type', 'parent']
    list_filter = ['type']
    search_fields = ['name', 'code']


@admin.register(Parcel)
class ParcelAdmin(GISModelAdmin):
    list_display = ['code', 'address', 'land_use', 'zoning', 'territory']
    list_filter = ['land_use', 'zoning']
    search_fields = ['code', 'address']


@admin.register(Building)
class BuildingAdmin(GISModelAdmin):
    list_display = ['__str__', 'use', 'floors', 'height_m', 'parcel']
    list_filter = ['use']


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'source', 'target', 'status', 'records_processed', 'records_failed', 'created_at']
    list_filter = ['status', 'target']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'action', 'target', 'user']
    list_filter = ['action']
    readonly_fields = ['user', 'action', 'target', 'detail', 'created_at']

    def has_add_permission(self, request):
        return False  # auditoria não é editável
