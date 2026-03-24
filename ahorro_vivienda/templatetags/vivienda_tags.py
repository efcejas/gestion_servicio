from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Accede a un dict por clave en los templates: {{ dict|get_item:key }}"""
    if dictionary is None:
        return None
    return dictionary.get(key)
