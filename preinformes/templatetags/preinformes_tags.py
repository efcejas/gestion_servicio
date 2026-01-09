from django import template
from preinformes.models import has_real_text

register = template.Library()

@register.filter(name='has_real_text')
def has_real_text_filter(html_content):
    """
    Template filter para detectar si hay texto real en contenido HTML.
    Uso: {% if preinforme.conclusion|has_real_text %}
    """
    return has_real_text(html_content)
