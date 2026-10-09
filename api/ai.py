# api/ai.py (arquivo novo)
from .models import Territory
 
CATEGORY_KEYWORDS = {
    # radicais, para casar singular/plural e variações (fiscal/fiscais, zona/zonas...)
    'zoning': ['zoneamento', 'zona', 'legisla', 'lei de uso'],
    'fiscal': ['fisca', 'iptu', 'imposto', 'tribut'],
    'infra': ['infraestrutura', 'esgoto', 'água', 'agua', 'energia', 'saneamento'],
    'land_use': ['uso do solo', 'ocupa'],
    'terrain': ['terren', 'relevo', 'declividade'],
    'socio_env': ['renda', 'popula', 'ambient', 'socioecon'],
    'cadastral': ['cadastr', 'imóve', 'imove', 'lote'],
}
 
def interpret(question):
    """Transforma a pergunta em parâmetros de consulta.
    Hoje: regras simples. Depois: trocar por chamada ao LLM devolvendo o mesmo dict."""
    q = question.lower()
    category = next(
        (c for c, kws in CATEGORY_KEYWORDS.items() if any(k in q for k in kws)), None
    )
    matches = [t for t in Territory.objects.all() if t.name.lower() in q]
    territory = max(matches, key=lambda t: len(t.name), default=None)
    return {'category': category, 'territory': territory}