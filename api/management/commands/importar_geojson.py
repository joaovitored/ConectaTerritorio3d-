from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.etl import run_import
from api.models import ImportJob, Layer, Source


class Command(BaseCommand):
    help = 'Importa um GeoJSON (territórios, lotes ou edificações) registrando a proveniência.'

    def add_arguments(self, parser):
        parser.add_argument('arquivo')
        parser.add_argument('--target', required=True, choices=['territory', 'parcel', 'building'])
        parser.add_argument('--fonte', default='IBGE - Malha Municipal',
                            help='Nome da fonte (criada se não existir)')
        parser.add_argument('--licenca', default='')
        parser.add_argument('--versao', default='')
        parser.add_argument('--tipo', default='municipio', help='Tipo padrão dos territórios importados')
        parser.add_argument('--camada', type=int, help='ID da camada (lotes/edificações)')

    def handle(self, *args, **opts):
        path = Path(opts['arquivo'])
        if not path.is_file():
            raise CommandError(f'Arquivo não encontrado: {path}')
        source, _ = Source.objects.get_or_create(name=opts['fonte'], defaults={
            'license': opts['licenca'], 'version': opts['versao'], 'collected_at': date.today(),
            'import_method': f'manage.py importar_geojson ({path.name})',
        })
        layer = Layer.objects.filter(pk=opts['camada']).first() if opts['camada'] else None
        job = ImportJob.objects.create(source=source, layer=layer, target=opts['target'],
                                       version=opts['versao'])
        run_import(job, data=path.read_bytes(), default_type=opts['tipo'])

        self.stdout.write(f'Job {job.pk}: {job.status} — {job.records_processed} importadas, '
                          f'{job.records_failed} com erro')
        if job.error_log:
            self.stdout.write(job.error_log)
        if job.status == 'failed':
            raise CommandError('Importação falhou.')
