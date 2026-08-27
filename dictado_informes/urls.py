from django.urls import path
from . import views
from . import views_dashboard  # 🚀 FASE 4: Vistas de dashboard de métricas

app_name = 'dictado_informes'

urlpatterns = [
    # Dashboard
    path('', views.DashboardDictadoView.as_view(), name='dashboard'),

    # Demo de presentacion clinica — SILENCIADA (reactivar descomentando)
    # path('demo-presentacion-ia/', views.DemoPresentacionIAView.as_view(), name='demo_presentacion_ia'),
    # path('demo-presentacion-ia/api/segmentos-reales/', views.demo_segmentos_reales_api, name='demo_segmentos_reales_api'),
    
    # Dictado Rápido (nueva funcionalidad simplificada)
    path('dictado-rapido/', views.DictadoRapidoView.as_view(), name='dictado_rapido'),
    path('mi-memoria/', views.MemoriaAprendizajeView.as_view(), name='memoria_aprendizaje'),
    path('mi-memoria/<int:pk>/estado/', views.actualizar_estado_memoria, name='actualizar_estado_memoria'),
    
    # Informes
    path('informes/', views.InformeListView.as_view(), name='informe_list'),
    path('informes/nuevo/', views.InformeCreateView.as_view(), name='informe_create'),
    path('informes/<int:pk>/', views.InformeDetailView.as_view(), name='informe_detail'),
    path('informes/<int:pk>/editar/', views.InformeUpdateView.as_view(), name='informe_update'),
    path('informes/<int:pk>/eliminar/', views.InformeDeleteView.as_view(), name='informe_delete'),
    path('informes/<int:pk>/firmar/', views.firmar_informe, name='firmar_informe'),
    
    # Plantillas
    path('plantillas/', views.PlantillaListView.as_view(), name='plantilla_list'),
    path('plantillas/nueva/', views.PlantillaCreateView.as_view(), name='plantilla_create'),
    path('plantillas/<int:pk>/editar/', views.PlantillaUpdateView.as_view(), name='plantilla_update'),
    
    # Plantillas Estructuradas (Guardrails de IA)
    path('plantillas-estructuradas/', views.PlantillaEstructuradaListView.as_view(), name='plantilla_estructurada_list'),
    path('plantillas-estructuradas/nueva/', views.PlantillaEstructuradaCreateView.as_view(), name='plantilla_estructurada_create'),
    path('plantillas-estructuradas/importar-docx/', views.importar_plantilla_docx_view, name='plantilla_estructurada_import_docx'),
    path('plantillas-estructuradas/<int:pk>/editar/', views.PlantillaEstructuradaUpdateView.as_view(), name='plantilla_estructurada_update'),
    path('plantillas-estructuradas/<int:pk>/eliminar/', views.PlantillaEstructuradaDeleteView.as_view(), name='plantilla_estructurada_delete'),
    
    # Diccionario Médico
    path('diccionario/', views.TerminoMedicoListView.as_view(), name='termino_list'),
    path('diccionario/nuevo/', views.TerminoMedicoCreateView.as_view(), name='termino_create'),
    path('diccionario/<int:pk>/editar/', views.TerminoMedicoUpdateView.as_view(), name='termino_update'),
    path('diccionario/<int:pk>/eliminar/', views.TerminoMedicoDeleteView.as_view(), name='termino_delete'),
    path('diccionario/<int:pk>/toggle/', views.toggle_termino_activo, name='termino_toggle'),
    
    # 🚀 FASE 4: Dashboard de Métricas
    path('metricas/', views_dashboard.dashboard_metricas, name='dashboard_metricas'),
    path('metricas/api/resumen/', views_dashboard.api_metricas_resumen, name='api_metricas_resumen'),
    path('metricas/api/anomalias/', views_dashboard.api_anomalias, name='api_anomalias'),
    
    # API
    path('api/plantilla/<int:pk>/', views.obtener_plantilla, name='obtener_plantilla'),
    path('api/transcribir-whisper/', views.transcribir_audio_whisper, name='transcribir_whisper'),
    path('api/mejorar-texto/', views.mejorar_texto_ia, name='mejorar_texto'),
    path('api/corregir-borrador/', views.corregir_borrador_ia, name='corregir_borrador'),
    path('api/deshacer-correccion/', views.deshacer_evento_correccion, name='deshacer_correccion'),
    path('api/guardar-aprendizaje/', views.guardar_correccion_aprendizaje, name='guardar_aprendizaje'),
    path('api/feedback-calidad/', views.registrar_feedback_calidad, name='feedback_calidad'),
    path('api/info-aprendizaje/', views.info_aprendizaje, name='info_aprendizaje'),
]
