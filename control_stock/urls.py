from django.urls import path
from . import views
from . import views_api

app_name = 'control_stock'

urlpatterns = [
    # Vistas HTML
    path('', views.dashboard, name='dashboard'),
    path('area/<int:area_id>/', views.detalle_area, name='detalle_area'),
    path('scanner/', views.scanner, name='scanner'),
    path('scanner/<int:area_id>/', views.scanner, name='scanner_area'),
    path('historial/', views.historial, name='historial'),
    path('historial/exportar/', views.exportar_historial_csv, name='exportar_historial'),
    path('buscar/', views.buscar_producto, name='buscar'),
    path('vencimientos/', views.vencimientos, name='vencimientos'),
    path('area/<int:area_id>/producto/<int:producto_id>/historial/', views.historial_producto_area, name='historial_producto'),
    path('producto/nuevo/', views.crear_producto, name='crear_producto'),
    path('producto/<int:producto_id>/editar/', views.editar_producto, name='editar_producto'),

    # API JSON (consumidas por el JavaScript del escáner)
    path('api/buscar/', views_api.api_buscar_producto, name='api_buscar'),
    path('api/buscar-global/', views_api.api_buscar_global, name='api_buscar_global'),
    path('api/buscar-nombre/', views_api.api_buscar_por_nombre, name='api_buscar_nombre'),
    path('api/lotes/', views_api.api_lotes_producto, name='api_lotes_producto'),
    path('api/analizar-foto/', views_api.api_analizar_foto, name='api_analizar_foto'),
    path('api/movimiento/', views_api.api_registrar_movimiento, name='api_movimiento'),
    path('api/anular/<int:mov_id>/', views_api.api_anular_movimiento, name='api_anular'),
    path('api/salida-rapida/', views_api.api_salida_rapida, name='api_salida_rapida'),
    path('api/reportar-lote/', views_api.api_reportar_lote, name='api_reportar_lote'),
    path('api/descarte-masivo/', views_api.api_descarte_masivo, name='api_descarte_masivo'),
]
