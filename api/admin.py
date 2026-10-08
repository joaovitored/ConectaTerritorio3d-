from django.contrib import admin
from .models import Source, Layer, Territory, Indicator, ImportJob

admin.site.register([Source, Layer, Territory, Indicator, ImportJob])