# api/models.py
from django.db import models

class Source(models.Model):
    name = models.CharField(max_length=200)
    license = models.CharField(max_length=100, blank=True)
    collected_at = models.DateField(null=True, blank=True)

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
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='layers')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    class Meta:
        indexes = [models.Index(fields=['type', 'name'])]

    def __str__(self):
        return f'{self.name} ({self.type})'


class Indicator(models.Model):
    territory = models.ForeignKey(Territory, on_delete=models.CASCADE, related_name='indicators')
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


class ImportJob(models.Model):
    STATUS = [
        ('pending', 'Pendente'),
        ('running', 'Em execução'),
        ('done', 'Concluída'),
        ('failed', 'Falhou'),
    ]
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name='imports')
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    version = models.CharField(max_length=50, blank=True)
    error_log = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)