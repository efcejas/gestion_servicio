from django.contrib import admin
from .models import ConfiguracionMeta, Cotizacion, Snapshot, CapitalItem, Conversion


class CapitalItemInline(admin.TabularInline):
    model = CapitalItem
    extra = 0
    fields = ('nombre', 'tipo', 'moneda', 'monto_original', 'cotizacion_tipo', 'cotizacion_manual', 'monto_usd', 'orden')
    readonly_fields = ('monto_usd',)


@admin.register(ConfiguracionMeta)
class ConfiguracionMetaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'meta_usd', 'fecha_objetivo', 'actualizado')


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'blue_compra', 'blue_venta', 'oficial_compra', 'oficial_venta', 'mep', 'eur_usd', 'fuente')
    list_filter = ('fuente',)
    date_hierarchy = 'fecha'
    ordering = ('-fecha',)


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'total_usd_calculado', 'creado_por', 'creado')
    inlines = [CapitalItemInline]
    readonly_fields = ('total_usd_calculado', 'creado', 'actualizado')
    date_hierarchy = 'fecha'


@admin.register(CapitalItem)
class CapitalItemAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'snapshot', 'moneda', 'monto_original', 'cotizacion_tipo', 'monto_usd')
    list_filter = ('moneda', 'tipo')


@admin.register(Conversion)
class ConversionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'descripcion', 'moneda_origen', 'monto_origen', 'moneda_destino', 'monto_destino', 'cotizacion_efectiva', 'registrado_por')
    list_filter = ('moneda_origen', 'moneda_destino')
    date_hierarchy = 'fecha'
