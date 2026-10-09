from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Source, Layer, Territory, Indicator, ImportJob


class BaseTest(TestCase):
    def setUp(self):
        cache.clear()  # zera o contador de throttling entre testes
        self.client = APIClient()
        self.source = Source.objects.create(name='Fonte teste')
        self.recife = Territory.objects.create(type='municipio', code='2611606', name='Recife')
        self.boa_vista = Territory.objects.create(
            type='bairro', code='B1', name='Boa Vista', parent=self.recife)
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
        self.assertEqual(set(item), {'id', 'name', 'category', 'source', 'updated_at'})
        self.assertEqual(item['source'], 'Fonte teste')

    def test_detalhe_inexistente_404(self):
        self.assertEqual(self.client.get('/api/layers/9999/').status_code, 404)


class TerritoryTests(BaseTest):
    def test_filtro_tipo(self):
        self.assertEqual(self.client.get('/api/territories/?type=bairro').json()['count'], 1)

    def test_filtro_pai(self):
        r = self.client.get('/api/territories/?parent=2611606').json()
        self.assertEqual(r['count'], 1)
        self.assertEqual(r['results'][0]['name'], 'Boa Vista')

    def test_filtro_nome_parcial(self):
        self.assertEqual(self.client.get('/api/territories/?name=boa').json()['count'], 1)

    def test_codigo_unico(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            Territory.objects.create(type='bairro', code='B1', name='Outro')


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


class StubTests(BaseTest):
    def test_features(self):
        self.assertEqual(self.client.get('/api/features/').status_code, 200)
        self.assertEqual(self.client.get('/api/features/1/').status_code, 404)

    def test_tilesets(self):
        self.assertEqual(self.client.get('/api/tilesets/').status_code, 200)


class DocsTests(BaseTest):
    def test_schema_e_swagger(self):
        self.assertEqual(self.client.get('/api/schema/').status_code, 200)
        self.assertEqual(self.client.get('/api/docs/').status_code, 200)

    def test_schema_lista_endpoints(self):
        body = self.client.get('/api/schema/').content.decode()
        for p in ('/api/layers/', '/api/territories/', '/api/indicators/',
                  '/api/search/', '/api/imports/', '/api/features/', '/api/tilesets/'):
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