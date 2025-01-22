from django import template

register = template.Library()

@register.filter
def unique(queryset):
    """
    Filtra valores únicos basados en un atributo.
    En este caso, para obtener tipos de estudios únicos.
    """
    seen = set()
    unique_items = []
    for item in queryset:
        if item.get_tipo_display() not in seen:
            unique_items.append(item.get_tipo_display())
            seen.add(item.get_tipo_display())
    return unique_items
