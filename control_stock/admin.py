from django.contrib import admin
from .models import AreaServicio, LoteEnArea, Producto, StockPorArea, MovimientoStock


@admin.register(AreaServicio)
class AreaServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'responsable', 'activa', 'creada_en')
    list_filter = ('activa',)
    search_fields = ('nombre',)
    raw_id_fields = ('responsable',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_barras', 'categoria', 'unidad_medida', 'stock_minimo', 'creado_en')
    list_filter = ('categoria', 'unidad_medida')
    search_fields = ('nombre', 'codigo_barras')
    readonly_fields = ('creado_en', 'actualizado_en')


@admin.register(StockPorArea)
class StockPorAreaAdmin(admin.ModelAdmin):
    list_display = ('producto', 'area', 'cantidad', 'bajo_minimo')
    list_filter = ('area',)
    search_fields = ('producto__nombre', 'area__nombre')
    readonly_fields = ('cantidad',)

    @admin.display(boolean=True, description='Bajo mínimo')
    def bajo_minimo(self, obj):
        return obj.bajo_minimo


@admin.register(LoteEnArea)
class LoteEnAreaAdmin(admin.ModelAdmin):
    list_display = ('stock', 'numero_lote', 'cantidad', 'fecha_vencimiento', 'activo', 'reportado_para_descarte')
    list_filter = ('activo', 'reportado_para_descarte', 'stock__area')
    search_fields = ('stock__producto__nombre', 'numero_lote')
    readonly_fields = ('creado_en',)
    date_hierarchy = 'fecha_vencimiento'


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'producto', 'area', 'cantidad', 'usuario', 'fecha', 'numero_lote', 'fecha_vencimiento', 'anulado')
    list_filter = ('tipo', 'anulado', 'area', 'fecha')
    search_fields = ('producto__nombre', 'numero_lote')
    readonly_fields = ('fecha',)
    date_hierarchy = 'fecha'
