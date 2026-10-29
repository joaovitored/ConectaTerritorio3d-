import io
import json
import os
import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from .models import (AuditLog, Building, ImportJob, Indicator, Layer, Parcel, Source, Territory,
                     Tileset)


def box(min_lon, min_lat, max_lon, max_lat):
    return MultiPolygon(Polygon.from_bbox((min_lon, min_lat, max_lon, max_lat)), srid=4326)


class BaseTest(TestCase):
    def setUp(self):
        cache.clear()  # zera o contador de throttling entre testes
        self.client = APIClient()
        self.source = Source.objects.create(name='Fonte teste')
        self.recife = Territory.objects.create(type='municipio', code='2611606', name='Recife',
                                               geometry=box(-34.96, -8.15, -34.87, -8.00))
        self.boa_vista = Territory.objects.create(
            type='bairro', code='B1', name='Boa Vista', parent=self.recife,
            geometry=box(-34.90, -8.07, -34.88, -8.05))
        Layer.objects.create(name='Zoneamento', category='zoning', source=self.source)
        Layer.objects.create(name='Camada inativa', category='zoning',
                             source=self.source, is_active=False)
        Indicator.objects.create(
            territory=self.recife, source=self.source, category='zoning',
            name='Zona ZUR-1', value=Decimal('12.5'), unit='%', period=date(2024, 1, 1))


class LayerTests(BaseTest):
    def test_lista_paginada(self):
        data = self.client.get('/api/layers/').json()
        for k in ('count', 'next', 'previous', 'results'):
            self.assertIn(k, data)

    def test_oculta_camada_inativa(self):
        self.assertEqual(self.client.get('/api/layers/').json()['count'], 1)

    def test_filtro_categoria(self):
        self.assertEqual(self.client.get('/api/layers/?category=zoning').json()['count'], 1)
        self.assertEqual(self.client.get('/api/layers/?category=fiscal').json()['count'], 0)

    def test_campos_da_resposta(self):
        item = self.client.get('/api/layers/').json()['results'][0]
        self.assertEqual(set(item), {'id', 'name', 'category', 'kind', 'description', 'source', 'owner',
                                     'scale', 'style', 'is_public', 'updated_at'})
        self.assertEqual(item['source'], 'Fonte teste')

    def test_camada_privada_so_com_login(self):
        Layer.objects.create(name='Privada', category='fiscal', source=self.source, is_public=False)
        self.assertEqual(self.client.get('/api/layers/').json()['count'], 1)
        self.client.force_authenticate(get_user_model().objects.create_user('u', password='x12345678'))
        self.assertEqual(self.client.get('/api/layers/').json()['count'], 2)

    def test_detalhe_inexistente_404(self):
        self.assertEqual(self.client.get('/api/layers/9999/').status_code, 404)


class TerritoryTests(BaseTest):
    def test_filtro_tipo(self):
        self.assertEqual(self.client.get('/api/territories/?type=bairro').json()['count'], 1)

    def test_filtro_pai(self):
        r = self.client.get('/api/territories/?parent=2611606').json()
        self.assertEqual(r['count'], 1)
        self.assertEqual(r['results'][0]['name'], 'Boa Vista')

    def test_parent_na_resposta_e_o_codigo(self):
        r = self.client.get('/api/territories/?type=bairro').json()['results'][0]
        self.assertEqual(r['parent'], '2611606')   # mesmo valor aceito em ?parent=
        r = self.client.get('/api/territories/?type=municipio').json()['results'][0]
        self.assertIsNone(r['parent'])

    def test_filtro_nome_parcial(self):
        self.assertEqual(self.client.get('/api/territories/?name=boa').json()['count'], 1)

    def test_codigo_unico(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            Territory.objects.create(type='bairro', code='B1', name='Outro')

    def test_bbox_na_resposta(self):
        r = self.client.get('/api/territories/?code=B1').json()['results'][0]
        self.assertEqual(r['bbox'], [-34.90, -8.07, -34.88, -8.05])

    def test_filtro_extensao_espacial(self):
        self.assertEqual(self.client.get('/api/territories/?bbox=-34.895,-8.06,-34.885,-8.055').json()['count'], 2)
        self.assertEqual(self.client.get('/api/territories/?bbox=-34.95,-8.14,-34.94,-8.13').json()['count'], 1)

    def test_contencao_de_ponto(self):
        r = self.client.get('/api/territories/?contains=-34.89,-8.06').json()
        self.assertEqual({t['code'] for t in r['results']}, {'2611606', 'B1'})

    def test_bbox_invalido_400(self):
        for bbox in ('1,2,3', 'a,b,c,d', '-34,-8,-35,-7', '-50,-30,-30,-10'):
            self.assertEqual(self.client.get(f'/api/territories/?bbox={bbox}').status_code, 400, bbox)


class IndicatorTests(BaseTest):
    def test_filtros(self):
        self.assertEqual(self.client.get('/api/indicators/?territory=2611606').json()['count'], 1)
        self.assertEqual(self.client.get('/api/indicators/?territory=B1').json()['count'], 0)
        self.assertEqual(self.client.get('/api/indicators/?category=fiscal').json()['count'], 0)
        self.assertEqual(self.client.get('/api/indicators/?period=2024-01-01').json()['count'], 1)

    def test_campos(self):
        item = self.client.get('/api/indicators/').json()['results'][0]
        self.assertEqual(item['territory'], '2611606')
        self.assertEqual(item['source'], 'Fonte teste')


class SearchTests(BaseTest):
    def test_exige_q(self):
        self.assertEqual(self.client.get('/api/search/').status_code, 400)
        self.assertEqual(self.client.get('/api/search/?q=a').status_code, 400)

    def test_acha_territorio_e_camada(self):
        r = self.client.get('/api/search/?q=rec').json()
        self.assertEqual(len(r['territories']), 1)
        r = self.client.get('/api/search/?q=zone').json()
        self.assertEqual(len(r['layers']), 1)

    def test_busca_por_codigo(self):
        self.assertEqual(len(self.client.get('/api/search/?q=2611606').json()['territories']), 1)

    def test_sem_dados(self):
        r = self.client.get('/api/search/?q=zzzz')
        self.assertEqual(r.status_code, 200)
        self.assertIn('message', r.json())

    def test_limite_de_resultados(self):
        for i in range(30):
            Territory.objects.create(type='setor', code=f'S{i}', name=f'Setor {i}')
        self.assertEqual(len(self.client.get('/api/search/?q=Setor').json()['territories']), 20)


class GeoDataTest(BaseTest):
    """Lotes e edificações dentro da Boa Vista, um deles numa camada privada."""
    def setUp(self):
        super().setUp()
        self.layer = Layer.objects.create(name='Lotes', category='cadastral', kind='parcel', source=self.source)
        self.private = Layer.objects.create(name='Lotes privados', category='cadastral', kind='parcel',
                                            source=self.source, is_public=False)
        self.p1 = Parcel.objects.create(code='L-1', address='Rua A, 1', area_m2=300, land_use='residencial',
                                        territory=self.boa_vista, layer=self.layer, source=self.source,
                                        geometry=box(-34.895, -8.060, -34.894, -8.059))
        self.p2 = Parcel.objects.create(code='L-2', address='Rua B, 2', area_m2=500, land_use='comercial',
                                        territory=self.boa_vista, layer=self.layer, source=self.source,
                                        geometry=box(-34.893, -8.060, -34.892, -8.059))
        self.secret = Parcel.objects.create(code='L-SECRETO', territory=self.boa_vista, layer=self.private,
                                            source=self.source, geometry=box(-34.891, -8.060, -34.890, -8.059))
        self.b1 = Building.objects.create(parcel=self.p1, territory=self.boa_vista, source=self.source,
                                          name='Edifício A', use='residencial', floors=4, height_m=12,
                                          geometry=box(-34.8948, -8.0598, -34.8942, -8.0592))
        Indicator.objects.create(territory=self.boa_vista, parcel=self.p1, source=self.source,
                                 category='fiscal', name='IPTU', value=Decimal('900'), unit='R$',
                                 period=date(2024, 1, 1))

    def features(self, query):
        return self.client.get(f'/api/v1/features/?{query}')


class FeatureTests(GeoDataTest):
    def test_geojson_valido(self):
        r = self.features('kind=parcel').json()
        self.assertEqual(r['type'], 'FeatureCollection')
        f = r['features'][0]
        self.assertEqual(f['type'], 'Feature')
        self.assertEqual(f['geometry']['type'], 'MultiPolygon')
        self.assertTrue(f['id'].startswith('parcel.'))
        self.assertEqual(f['properties']['territory'], 'B1')

    def test_exige_kind_ou_camada(self):
        self.assertEqual(self.features('').status_code, 400)
        self.assertEqual(self.features('kind=xyz').status_code, 400)

    def test_camada_privada_oculta_para_anonimo(self):
        codes = {f['properties']['code'] for f in self.features('kind=parcel').json()['features']}
        self.assertEqual(codes, {'L-1', 'L-2'})
        self.assertEqual(self.features(f'layer={self.private.pk}').status_code, 404)

    def test_camada_privada_visivel_com_login(self):
        self.client.force_authenticate(get_user_model().objects.create_user('u', password='x12345678'))
        self.assertEqual(self.features(f'layer={self.private.pk}').json()['numberMatched'], 1)

    def test_filtro_por_camada(self):
        self.assertEqual(self.features(f'layer={self.layer.pk}').json()['numberMatched'], 2)

    def test_filtro_bbox(self):
        r = self.features('kind=parcel&bbox=-34.8955,-8.0605,-34.8935,-8.0585').json()
        self.assertEqual([f['properties']['code'] for f in r['features']], ['L-1'])

    def test_filtro_territorio(self):
        self.assertEqual(self.features('kind=parcel&territory=B1').json()['numberMatched'], 2)
        self.assertEqual(self.features('kind=parcel&territory=nao-existe').json()['numberMatched'], 0)

    def test_proximidade(self):
        # L-1 fica a ~0 m do ponto; L-2 a ~110 m
        self.assertEqual(self.features('kind=parcel&near=-34.8945,-8.0595&radius=50').json()['numberMatched'], 1)
        self.assertEqual(self.features('kind=parcel&near=-34.8945,-8.0595&radius=300').json()['numberMatched'], 2)
        self.assertEqual(self.features('kind=parcel&near=-34.8945,-8.0595&radius=99999').status_code, 400)

    def test_filtros_de_atributo(self):
        self.assertEqual(self.features('kind=parcel&land_use=comercial').json()['numberMatched'], 1)
        self.assertEqual(self.features('kind=building&min_height=10').json()['numberMatched'], 1)
        self.assertEqual(self.features('kind=building&min_height=20').json()['numberMatched'], 0)

    def test_limite_e_truncamento(self):
        r = self.features('kind=parcel&limit=1').json()
        self.assertEqual((r['numberMatched'], r['numberReturned'], r['truncated']), (2, 1, True))

    def test_simplificacao_nao_quebra(self):
        self.assertEqual(self.features('kind=territory&simplify=0.001').status_code, 200)

    def test_detalhe_com_indicadores(self):
        r = self.client.get(f'/api/v1/features/parcel/{self.p1.pk}/').json()
        self.assertEqual(r['properties']['code'], 'L-1')
        self.assertEqual(r['properties']['buildings'], [f'building.{self.b1.pk}'])
        self.assertEqual(r['properties']['indicators'][0]['name'], 'IPTU')

    def test_detalhe_edificacao_traz_altura(self):
        r = self.client.get(f'/api/v1/features/building/{self.b1.pk}/').json()
        self.assertEqual(r['properties']['height_m'], 12.0)
        self.assertEqual(r['properties']['parcel'], 'L-1')

    def test_detalhe_privado_e_inexistente_404(self):
        self.assertEqual(self.client.get(f'/api/v1/features/parcel/{self.secret.pk}/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/features/parcel/99999/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/features/xyz/1/').status_code, 404)

    def test_query_por_area_desenhada(self):
        area = {'type': 'Polygon', 'coordinates': [[[-34.8955, -8.0605], [-34.8915, -8.0605],
                                                    [-34.8915, -8.0585], [-34.8955, -8.0585],
                                                    [-34.8955, -8.0605]]]}
        r = self.client.post('/api/v1/features/query/', {'kind': 'parcel', 'geometry': area}, format='json')
        self.assertEqual(r.json()['numberMatched'], 2)  # o lote privado fica de fora

    def test_query_geometria_invalida(self):
        r = self.client.post('/api/v1/features/query/',
                             {'kind': 'parcel', 'geometry': {'type': 'Point', 'coordinates': [0, 0]}},
                             format='json')
        self.assertEqual(r.status_code, 400)


class PrivateParcelLeakTests(GeoDataTest):
    """Indicadores e edificações de um lote privado não podem vazar por outras rotas."""
    def setUp(self):
        super().setUp()
        Indicator.objects.create(territory=self.boa_vista, parcel=self.secret, source=self.source,
                                 category='fiscal', name='IPTU secreto', value=Decimal('1'),
                                 period=date(2024, 1, 1))
        self.secret_building = Building.objects.create(
            parcel=self.secret, territory=self.boa_vista, source=self.source, name='Prédio secreto',
            geometry=box(-34.8908, -8.0598, -34.8902, -8.0592))

    def names(self, url):
        return {i['name'] for i in self.client.get(url).json()['results']}

    def test_lista_de_indicadores(self):
        self.assertNotIn('IPTU secreto', self.names('/api/v1/indicators/'))
        self.assertEqual(self.client.get('/api/v1/indicators/?parcel=L-SECRETO').json()['count'], 0)
        self.client.force_authenticate(get_user_model().objects.create_user('u', password='x12345678'))
        self.assertIn('IPTU secreto', self.names('/api/v1/indicators/'))

    def test_summary(self):
        r = self.client.get(f'/api/v1/territories/{self.boa_vista.pk}/summary/').json()
        self.assertNotIn('IPTU secreto', {i['name'] for i in r['indicators']})
        self.assertEqual(r['buildings'], 1)

    def test_ia(self):
        r = self.client.post('/api/ai/query/', {'question': 'dados fiscais de Boa Vista'}, format='json').json()
        self.assertNotIn('IPTU secreto', r.get('answer', ''))

    def test_edificacao_de_lote_privado(self):
        self.assertEqual(self.client.get(f'/api/v1/features/building/{self.secret_building.pk}/').status_code, 404)
        self.assertEqual(self.features('kind=building').json()['numberMatched'], 1)


class SummaryTests(GeoDataTest):
    def test_agregacao_do_territorio(self):
        r = self.client.get(f'/api/v1/territories/{self.boa_vista.pk}/summary/').json()
        self.assertEqual(r['parcels'], 2)            # sem o lote privado
        self.assertEqual(r['parcels_area_m2'], 800.0)
        self.assertEqual(r['buildings'], 1)
        self.assertEqual(r['land_use'], {'comercial': 1, 'residencial': 1})
        self.assertGreater(r['area_km2'], 4)          # ~2,2 km x 2,2 km, calculado em metros


class GeoSearchTests(GeoDataTest):
    def test_busca_por_lote_e_endereco(self):
        self.assertEqual(len(self.client.get('/api/search/?q=L-1').json()['parcels']), 1)
        self.assertEqual(len(self.client.get('/api/search/?q=Rua B').json()['parcels']), 1)

    def test_busca_por_coordenada(self):
        r = self.client.get('/api/search/?q=-34.8945,-8.0595').json()
        self.assertEqual([p['code'] for p in r['parcels']], ['L-1'])
        self.assertEqual(len(r['buildings']), 1)
        self.assertEqual({t['code'] for t in r['territories']}, {'B1', '2611606'})

    def test_busca_nao_mostra_privado(self):
        self.assertEqual(self.client.get('/api/search/?q=SECRETO').json()['parcels'], [])


class TilesetTests(BaseTest):
    def test_lista_so_camadas_visiveis(self):
        pub = Layer.objects.create(name='Prédios 3D', category='cadastral', kind='tiles3d', source=self.source)
        priv = Layer.objects.create(name='3D privado', category='cadastral', kind='tiles3d',
                                    source=self.source, is_public=False)
        Tileset.objects.create(layer=pub, name='Recife 3D', format='3dtiles',
                               url='https://cdn.example.com/recife/tileset.json', territory=self.recife)
        Tileset.objects.create(layer=priv, name='Privado', format='3dtiles',
                               url='https://cdn.example.com/priv/tileset.json')
        r = self.client.get('/api/v1/tilesets/').json()
        self.assertEqual(r['count'], 1)
        self.assertEqual(r['results'][0]['territory'], '2611606')


GEOJSON = {
    'type': 'FeatureCollection',
    'features': [
        {'type': 'Feature', 'properties': {'cod_munici': '2609600', 'nom_munici': 'Olinda'},
         'geometry': {'type': 'Polygon', 'coordinates': [[[-34.88, -8.04], [-34.83, -8.04], [-34.83, -7.96],
                                                          [-34.88, -7.96], [-34.88, -8.04]]]}},
        # gravata (auto-interseção): o ETL corrige com make_valid
        {'type': 'Feature', 'properties': {'codigo': 'X1', 'nome': 'Gravata'},
         'geometry': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}},
        {'type': 'Feature', 'properties': {'nome': 'Sem código'},
         'geometry': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 0]]]}},
        {'type': 'Feature', 'properties': {'codigo': 'P1', 'nome': 'Ponto'},
         'geometry': {'type': 'Point', 'coordinates': [0, 0]}},
    ],
}


class ETLTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.admin = get_user_model().objects.create_superuser('adm', password='x12345678')
        self.client.force_authenticate(self.admin)

    def upload(self, content, target='territory', name='malha.geojson'):
        f = SimpleUploadedFile(name, content if isinstance(content, bytes) else json.dumps(content).encode())
        return self.client.post('/api/v1/imports/', {'source': self.source.id, 'target': target, 'file': f},
                                format='multipart')

    def test_importa_valida_e_registra_erros(self):
        r = self.upload(GEOJSON)
        self.assertEqual(r.status_code, 201, r.content)
        job = r.json()
        self.assertEqual(job['status'], 'done')
        self.assertEqual((job['records_processed'], job['records_failed']), (2, 2))
        self.assertIn('feição 2', job['error_log'])
        olinda = Territory.objects.get(code='2609600')
        self.assertEqual((olinda.name, olinda.geometry.geom_type, olinda.source), ('Olinda', 'MultiPolygon', self.source))
        self.assertTrue(Territory.objects.get(code='X1').geometry.valid)

    def test_reimportar_atualiza_sem_duplicar(self):
        self.upload(GEOJSON)
        self.upload(GEOJSON)
        self.assertEqual(Territory.objects.filter(code='2609600').count(), 1)

    def test_reprojeta_para_4326(self):
        # Olinda em SIRGAS 2000 / UTM 25S (EPSG:31985)
        data = {'type': 'FeatureCollection',
                'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:EPSG::31985'}},
                'features': [{'type': 'Feature', 'properties': {'codigo': 'UTM1', 'nome': 'UTM'},
                              'geometry': {'type': 'Polygon', 'coordinates': [[
                                  [292000, 9113000], [293000, 9113000], [293000, 9114000],
                                  [292000, 9114000], [292000, 9113000]]]}}]}
        self.assertEqual(self.upload(data).json()['status'], 'done')
        lon, lat = Territory.objects.get(code='UTM1').geometry.centroid.coords
        self.assertAlmostEqual(lon, -34.87, places=1)
        self.assertAlmostEqual(lat, -8.01, places=1)

    def test_lote_ganha_territorio_por_contencao(self):
        data = {'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'properties': {'inscricao': 'LT-9', 'endereco': 'Rua X'},
             'geometry': {'type': 'Polygon', 'coordinates': [[[-34.895, -8.06], [-34.894, -8.06], [-34.894, -8.059],
                                                              [-34.895, -8.059], [-34.895, -8.06]]]}}]}
        self.upload(data, target='parcel')
        self.assertEqual(Parcel.objects.get(code='LT-9').territory, self.boa_vista)  # o mais específico

    def test_arquivo_invalido_falha(self):
        self.assertEqual(self.upload(b'nao e json').json()['status'], 'failed')
        self.assertEqual(self.upload({'type': 'Feature'}).json()['status'], 'failed')

    def test_extensao_bloqueada(self):
        self.assertEqual(self.upload(GEOJSON, name='virus.exe').status_code, 400)

    def test_arquivo_exige_destino(self):
        f = SimpleUploadedFile('a.geojson', json.dumps(GEOJSON).encode())
        r = self.client.post('/api/v1/imports/', {'source': self.source.id, 'file': f}, format='multipart')
        self.assertEqual(r.status_code, 400)

    def test_auditoria(self):
        self.upload(GEOJSON)
        self.assertEqual(set(AuditLog.objects.values_list('action', flat=True)), {'import.create', 'import.done'})
        self.assertEqual(AuditLog.objects.first().user, self.admin)

    def test_comando_importar_geojson(self):
        with tempfile.NamedTemporaryFile('w', suffix='.geojson', delete=False, encoding='utf-8-sig') as f:
            json.dump(GEOJSON, f)  # com BOM, como o municipios.geojson do repositório
        try:
            call_command('importar_geojson', f.name, '--target', 'territory', stdout=io.StringIO())
        finally:
            os.unlink(f.name)
        self.assertTrue(Territory.objects.filter(code='2609600').exists())

    def test_comando_carregar_demo_idempotente(self):
        for _ in range(2):
            call_command('carregar_demo', stdout=io.StringIO())
        self.assertEqual(Parcel.objects.count(), 5)
        self.assertEqual(Building.objects.count(), 4)


class ImportTests(BaseTest):
    def test_anonimo_nao_cria(self):
        r = self.client.post('/api/imports/', {'source': self.source.id})
        self.assertIn(r.status_code, (401, 403))

    def test_usuario_comum_nao_cria(self):
        u = get_user_model().objects.create_user('comum', password='x12345678')
        self.client.force_authenticate(u)
        self.assertEqual(self.client.post('/api/imports/', {'source': self.source.id}).status_code, 403)

    def test_admin_cria_job_pendente(self):
        u = get_user_model().objects.create_superuser('adm', password='x12345678')
        self.client.force_authenticate(u)
        r = self.client.post('/api/imports/', {'source': self.source.id})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(ImportJob.objects.get().status, 'pending')

    def test_status_nao_pode_ser_forcado(self):
        u = get_user_model().objects.create_superuser('adm', password='x12345678')
        self.client.force_authenticate(u)
        self.client.post('/api/imports/', {'source': self.source.id, 'status': 'done'})
        self.assertEqual(ImportJob.objects.get().status, 'pending')


class AITests(BaseTest):
    def ask(self, q):
        return self.client.post('/api/ai/query/', {'question': q}, format='json')

    def test_ok_com_fonte(self):
        r = self.ask('qual o zoneamento de Recife?').json()
        self.assertEqual(r['status'], 'ok')
        self.assertIn('Fonte teste', r['sources'])
        self.assertIn('Fonte teste', r['answer'])

    def test_sem_territorio(self):
        self.assertEqual(self.ask('qual o zoneamento?').json()['status'], 'needs_more_info')

    def test_territorio_inexistente(self):
        self.assertEqual(self.ask('zoneamento de Olinda').json()['status'], 'needs_more_info')

    def test_sem_dados(self):
        self.assertEqual(self.ask('dados fiscais de Recife').json()['status'], 'no_data')

    def test_corpo_invalido_nao_gera_500(self):
        for body in (5, 'texto', [1, 2], None):
            r = self.client.post('/api/ai/query/', body, format='json')
            self.assertEqual(r.status_code, 400, body)

    def test_pergunta_vazia(self):
        self.assertEqual(self.ask('').status_code, 400)

    def test_nao_inventa_dado(self):
        r = self.ask('dados fiscais de Recife').json()
        self.assertNotIn('answer', r)

    def test_limite_de_requisicoes(self):
        codes = [self.ask('zoneamento de Recife').status_code for _ in range(12)]
        self.assertIn(429, codes)


class VersioningTests(BaseTest):
    def test_v1_e_alias_respondem_igual(self):
        a = self.client.get('/api/v1/territories/').json()
        b = self.client.get('/api/territories/').json()
        self.assertEqual(a['results'], b['results'])

    def test_versao_inexistente_404(self):
        self.assertEqual(self.client.get('/api/v2/territories/').status_code, 404)


class DocsTests(BaseTest):
    def test_schema_e_swagger(self):
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
        self.assertEqual(self.client.get('/api/docs/').status_code, 200)

    def test_schema_lista_endpoints(self):
        body = self.client.get('/api/schema/').content.decode()
        for p in ('/api/v1/layers/', '/api/v1/territories/', '/api/v1/indicators/', '/api/v1/search/',
                  '/api/v1/imports/', '/api/v1/features/', '/api/v1/features/query/',
                  '/api/v1/features/{kind}/{id}/', '/api/v1/tilesets/', '/api/v1/territories/{id}/summary/'):
            self.assertIn(p, body)


class SegurancaTests(BaseTest):
    def test_escrita_bloqueada_nas_leituras(self):
        for url in ('/api/layers/', '/api/territories/', '/api/indicators/'):
            self.assertIn(self.client.post(url, {}).status_code, (401, 403, 405))

    def test_admin_exige_login(self):
        self.assertEqual(self.client.get('/admin/').status_code, 302)

    def test_cors_so_front(self):
        r = self.client.get('/api/layers/', HTTP_ORIGIN='http://localhost:5173')
        self.assertEqual(r.headers.get('Access-Control-Allow-Origin'), 'http://localhost:5173')
        r = self.client.get('/api/layers/', HTTP_ORIGIN='http://site-estranho.com')
        self.assertIsNone(r.headers.get('Access-Control-Allow-Origin'))


class AuthTests(BaseTest):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user('ana', 'ana@x.com', 'senha-forte-123')
        self.admin = User.objects.create_user('adm', 'adm@x.com', 'senha-forte-123', is_staff=True)

    def _login(self, username='ana', password='senha-forte-123'):
        return self.client.post('/api/auth/login/', {'username': username, 'password': password},
                                format='json')

    def test_login_ok_devolve_token(self):
        r = self._login()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['token'])

    def test_login_senha_errada_400(self):
        r = self._login(password='errada')
        self.assertEqual(r.status_code, 400)
        self.assertNotIn('token', r.json())

    def test_login_sem_campos_400(self):
        self.assertEqual(self.client.post('/api/auth/login/', {}, format='json').status_code, 400)

    def test_login_so_aceita_post(self):
        self.assertEqual(self.client.get('/api/auth/login/').status_code, 405)

    def test_me_sem_token_401(self):
        self.assertIn(self.client.get('/api/auth/me/').status_code, (401, 403))

    def test_me_com_token(self):
        token = self._login().json()['token']
        r = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'username': 'ana', 'email': 'ana@x.com', 'is_staff': False})

    def test_token_invalido_401(self):
        r = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION='Token lixo')
        self.assertEqual(r.status_code, 401)

    def test_token_nao_vaza_senha(self):
        self.assertNotIn('senha-forte-123', self._login().content.decode())

    def test_logout_invalida_token(self):
        token = self._login().json()['token']
        h = {'HTTP_AUTHORIZATION': f'Token {token}'}
        self.assertEqual(self.client.post('/api/auth/logout/', **h).status_code, 204)
        self.assertEqual(self.client.get('/api/auth/me/', **h).status_code, 401)

    def test_usuario_comum_nao_cria_import(self):
        token = self._login().json()['token']
        r = self.client.post('/api/imports/', {'source': self.source.id}, format='json',
                             HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(r.status_code, 403)

    def test_admin_com_token_cria_import(self):
        token = self._login('adm').json()['token']
        r = self.client.post('/api/imports/', {'source': self.source.id}, format='json',
                             HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(r.status_code, 201)

    def test_leitura_publica_continua_sem_token(self):
        self.assertEqual(self.client.get('/api/layers/').status_code, 200)

    def test_throttle_login_429(self):
        codes = [self._login(password='errada').status_code for _ in range(12)]
        self.assertIn(429, codes)