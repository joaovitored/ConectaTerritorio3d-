from datetime import date
from decimal import Decimal

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import SRID, Building, Indicator, Layer, Parcel, Source, Territory

# Coordenadas APROXIMADAS, só para desenvolvimento (antes ficavam no DB/init.sql)
MUNICIPIOS = [
    ('2609600', 'Olinda', 'POLYGON((-34.885 -8.040, -34.825 -8.040, -34.825 -7.960, -34.885 -7.960, -34.885 -8.040))'),
    ('2611606', 'Recife', 'POLYGON((-34.960 -8.150, -34.870 -8.150, -34.870 -8.000, -34.960 -8.000, -34.960 -8.150))'),
]
LOTES = [
    ('OL-001', 'Rua do Sol, 10', '300.00', 'residencial', 'ZUR-1', 'POLYGON((-34.8560 -8.0100, -34.8555 -8.0100, -34.8555 -8.0095, -34.8560 -8.0095, -34.8560 -8.0100))'),
    ('OL-002', 'Rua do Sol, 20', '320.00', 'residencial', 'ZUR-1', 'POLYGON((-34.8554 -8.0100, -34.8549 -8.0100, -34.8549 -8.0095, -34.8554 -8.0095, -34.8554 -8.0100))'),
    ('OL-003', 'Av. Principal, 100', '500.00', 'comercial', 'ZC-2', 'POLYGON((-34.8560 -8.0094, -34.8554 -8.0094, -34.8554 -8.0088, -34.8560 -8.0088, -34.8560 -8.0094))'),
    ('OL-004', 'Praça Central, 5', '450.00', 'misto', 'ZM-1', 'POLYGON((-34.8553 -8.0094, -34.8547 -8.0094, -34.8547 -8.0088, -34.8553 -8.0088, -34.8553 -8.0094))'),
    ('OL-005', 'Rua da Igreja, 40', '280.00', 'institucional', 'ZI-1', 'POLYGON((-34.8546 -8.0100, -34.8541 -8.0100, -34.8541 -8.0095, -34.8546 -8.0095, -34.8546 -8.0100))'),
]
EDIFICACOES = [
    ('OL-001', 'Casa 10', 'residencial', 1, '3.50', '120.00', 'POLYGON((-34.85590 -8.01000, -34.85565 -8.01000, -34.85565 -8.00975, -34.85590 -8.00975, -34.85590 -8.01000))'),
    ('OL-003', 'Loja Principal', 'comercial', 2, '7.00', '300.00', 'POLYGON((-34.85590 -8.00935, -34.85550 -8.00935, -34.85550 -8.00895, -34.85590 -8.00895, -34.85590 -8.00935))'),
    ('OL-004', 'Edifício Praça', 'misto', 5, '15.00', '250.00', 'POLYGON((-34.85520 -8.00935, -34.85480 -8.00935, -34.85480 -8.00895, -34.85520 -8.00895, -34.85520 -8.00935))'),
    ('OL-005', 'Paróquia', 'institucional', 1, '9.00', '200.00', 'POLYGON((-34.85450 -8.00995, -34.85420 -8.00995, -34.85420 -8.00960, -34.85450 -8.00960, -34.85450 -8.00995))'),
]


def multi(wkt):
    return MultiPolygon(GEOSGeometry(wkt, srid=SRID), srid=SRID)


class Command(BaseCommand):
    help = 'Carrega dados de teste (Olinda/Recife, lotes, edificações e indicadores). Pode rodar de novo.'

    @transaction.atomic
    def handle(self, *args, **opts):
        source, _ = Source.objects.get_or_create(name='Dados de teste', defaults={
            'description': 'Geometrias aproximadas criadas à mão para desenvolvimento',
            'license': 'uso interno', 'collected_at': date.today(), 'quality': 'test'})
        layers = {
            'parcel': Layer.objects.get_or_create(name='Lotes (teste)', defaults={
                'category': 'cadastral', 'kind': 'parcel', 'source': source,
                'description': 'Lotes de exemplo em Olinda'})[0],
            'building': Layer.objects.get_or_create(name='Edificações (teste)', defaults={
                'category': 'cadastral', 'kind': 'building', 'source': source,
                'description': 'Edificações de exemplo em Olinda',
                'style': {'extrude': 'height_m', 'color': '#4f7cac'}})[0],
            'territory': Layer.objects.get_or_create(name='Limites municipais', defaults={
                'category': 'socio_env', 'kind': 'territory', 'source': source})[0],
        }

        for code, name, wkt in MUNICIPIOS:
            t, created = Territory.objects.get_or_create(code=code, defaults={
                'type': 'municipio', 'name': name, 'source': source, 'geometry': multi(wkt)})
            if not created and t.geometry is None:  # não sobrescreve a malha real, se já importada
                t.geometry = multi(wkt)
                t.save(update_fields=['geometry'])
        olinda = Territory.objects.get(code='2609600')

        for code, address, area, use, zone, wkt in LOTES:
            Parcel.objects.update_or_create(code=code, defaults={
                'territory': olinda, 'layer': layers['parcel'], 'source': source, 'address': address,
                'area_m2': Decimal(area), 'land_use': use, 'zoning': zone, 'geometry': multi(wkt)})

        for parcel_code, name, use, floors, height, area, wkt in EDIFICACOES:
            parcel = Parcel.objects.get(code=parcel_code)
            Building.objects.update_or_create(parcel=parcel, name=name, defaults={
                'territory': olinda, 'layer': layers['building'], 'source': source, 'use': use,
                'floors': floors, 'height_m': Decimal(height), 'area_m2': Decimal(area),
                'geometry': multi(wkt)})

        Indicator.objects.get_or_create(
            territory=olinda, source=source, category='zoning', name='Zona ZUR-1',
            period=date(2024, 1, 1), defaults={'value': Decimal('12.5'), 'unit': '%'})
        Indicator.objects.get_or_create(
            territory=olinda, parcel=Parcel.objects.get(code='OL-003'), source=source,
            category='fiscal', name='IPTU', period=date(2024, 1, 1),
            defaults={'value': Decimal('1850.00'), 'unit': 'R$'})

        self.stdout.write(self.style.SUCCESS(
            f'Demo carregada: {Territory.objects.count()} territórios, {Parcel.objects.count()} lotes, '
            f'{Building.objects.count()} edificações.'))
