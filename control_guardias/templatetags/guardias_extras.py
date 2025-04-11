from django import template

register = template.Library()

@register.filter
def get_guardia_for_franja(guardias, franja):
    return next((g for g in guardias if g.franja_horaria == franja), None)

@register.filter
def dict_get(d, key):
    return d.get(key, '')