from django.urls import path
from . import views

app_name = 'eges_import'

urlpatterns = [
    # ── Vistas principales (superuser) ──────────────────────────────────────
    path('', views.lista_batches, name='lista_batches'),
    path('importar/', views.importar_eges, name='importar'),
    path('batch/<int:batch_id>/', views.detalle_batch, name='detalle_batch'),

    # ── Estadísticas globales (superuser) ───────────────────────────────────
    path('estadisticas/', views.dashboard_global, name='estadisticas'),
    path('estadisticas/grafico-data/', views.dashboard_global_grafico_data, name='dashboard_global_grafico_data'),
    path('estadisticas/grafico-dia-semana/', views.dashboard_global_dia_semana_data, name='dashboard_global_dia_semana_data'),
    path('estadisticas/grafico-franja-horaria/', views.dashboard_global_franja_horaria_data, name='dashboard_global_franja_horaria_data'),

    # ── Endpoints de análisis nuevos (superuser) ─────────────────────────────
    path('datos/kpis/', views.kpis_data, name='kpis_data'),
    path('datos/analisis-temporal/', views.analisis_temporal_data, name='analisis_temporal_data'),
    path('datos/distribucion-modalidad/', views.distribucion_modalidad_data, name='distribucion_modalidad_data'),
    path('datos/sub-modalidades-eco/', views.sub_modalidades_eco_data, name='sub_modalidades_eco_data'),
    path('datos/productividad-medico/', views.productividad_medico_data, name='productividad_medico_data'),
    path('datos/obras-sociales/', views.obras_sociales_data, name='obras_sociales_data'),
    path('datos/practicas/', views.practicas_data, name='practicas_data'),
    path('datos/obras-sociales/evolucion/', views.obras_sociales_evolucion_data, name='obras_sociales_evolucion_data'),
    path('datos/comparativa/', views.comparativa_data, name='comparativa_data'),
    path('datos/exportar-excel/', views.exportar_excel, name='exportar_excel'),
    path('datos/exportar-pdf/', views.exportar_pdf, name='exportar_pdf'),

    # ── Endpoints por batch ──────────────────────────────────────────────────
    path('batch/<int:batch_id>/grafico-data/', views.grafico_batch_data, name='grafico_batch_data'),
    path('batch/<int:batch_id>/grafico-dia-semana/', views.grafico_dia_semana_data, name='grafico_dia_semana_data'),
    path('batch/<int:batch_id>/grafico-franja-horaria/', views.grafico_franja_horaria_data, name='grafico_franja_horaria_data'),

    # ── Portal del Director (acceso por token, sin login) ────────────────────
    path('director/<str:token>/', views.portal_director, name='portal_director'),
    path('director/<str:token>/kpis/', views.portal_director_kpis, name='portal_director_kpis'),
    path('director/<str:token>/analisis-temporal/', views.portal_director_analisis_temporal, name='portal_director_analisis_temporal'),
    path('director/<str:token>/distribucion/', views.portal_director_distribucion, name='portal_director_distribucion'),
    path('director/<str:token>/eco/', views.portal_director_eco, name='portal_director_eco'),
    path('director/<str:token>/medicos/', views.portal_director_medicos, name='portal_director_medicos'),
    path('director/<str:token>/franja-horaria/', views.portal_director_franja_horaria, name='portal_director_franja_horaria'),
    path('director/<str:token>/obras-sociales/', views.portal_director_obras_sociales, name='portal_director_obras_sociales'),
    path('director/<str:token>/practicas/', views.portal_director_practicas, name='portal_director_practicas'),
    path('director/<str:token>/obras-sociales/evolucion/', views.portal_director_obras_sociales_evolucion, name='portal_director_obras_sociales_evolucion'),
    path('director/<str:token>/comparativa/', views.portal_director_comparativa, name='portal_director_comparativa'),
    path('director/<str:token>/exportar-excel/', views.portal_director_exportar_excel, name='portal_director_exportar_excel'),
    path('director/<str:token>/exportar-pdf/', views.portal_director_exportar_pdf, name='portal_director_exportar_pdf'),
]
