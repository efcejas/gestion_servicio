from django.urls import path
from . import views

app_name = 'ahorro_vivienda'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('snapshots/', views.lista_snapshots, name='lista_snapshots'),
    path('snapshots/nuevo/', views.nuevo_snapshot, name='nuevo_snapshot'),
    path('snapshots/<int:pk>/', views.detalle_snapshot, name='detalle_snapshot'),
    path('conversiones/', views.lista_conversiones, name='lista_conversiones'),
    path('conversiones/nueva/', views.nueva_conversion, name='nueva_conversion'),
    path('configuracion/', views.configuracion, name='configuracion'),
    path('api/cotizacion-hoy/', views.api_cotizacion_hoy, name='api_cotizacion_hoy'),
    path('export/csv/', views.export_csv, name='export_csv'),
]
