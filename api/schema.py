# api/schema.py — ajustes do OpenAPI gerado pelo drf-spectacular


def only_v1(endpoints, **kwargs):
    """Documenta só /api/v1/; o alias /api/ é o mesmo código e duplicaria tudo no Swagger."""
    return [e for e in endpoints if e[0].startswith('/api/v1/')]
