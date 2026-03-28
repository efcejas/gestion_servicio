from django.contrib import admin
from .models import AreaServicio, Producto, StockPorArea, MovimientoStock


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


class StockPorAreaInline(admin.TabularInline):
    model = StockPorArea
    extra = 0
    readonly_fields = ('cantidad',)


@admin.register(StockPorArea)
class StockPorAreaAdmin(admin.ModelAdmin):
    list_display = ('producto', 'area', 'cantidad', 'bajo_minimo')
    list_filter = ('area',)
    search_fields = ('producto__nombre', 'area__nombre')

    @admin.display(boolean=True, description='Bajo mínimo')
    def bajo_minimo(self, obj):
        return obj.bajo_minimo


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'producto', 'area', 'cantidad', 'usuario', 'fecha', 'numero_lote', 'fecha_vencimiento')
    list_filter = ('tipo', 'area', 'fecha')
    search_fields = ('producto__nombre', 'numero_lote')
    readonly_fields = ('fecha',)
    date_hierarchy = 'fecha'
