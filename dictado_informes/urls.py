from django.urls import path
from . import views

app_name = 'dictado_informes'

urlpatterns = [
    # Dashboard
    path('', views.DashboardDictadoView.as_view(), name='dashboard'),
    
    # Dictado Rápido (nueva funcionalidad simplificada)
    path('dictado-rapido/', views.DictadoRapidoView.as_view(), name='dictado_rapido'),
    
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
    
    # Diccionario Médico
    path('diccionario/', views.TerminoMedicoListView.as_view(), name='termino_list'),
    path('diccionario/nuevo/', views.TerminoMedicoCreateView.as_view(), name='termino_create'),
    path('diccionario/<int:pk>/editar/', views.TerminoMedicoUpdateView.as_view(), name='termino_update'),
    path('diccionario/<int:pk>/eliminar/', views.TerminoMedicoDeleteView.as_view(), name='termino_delete'),
    path('diccionario/<int:pk>/toggle/', views.toggle_termino_activo, name='termino_toggle'),
    
    # API
    path('api/plantilla/<int:pk>/', views.obtener_plantilla, name='obtener_plantilla'),
    path('api/procesar-audio/', views.procesar_audio_dictado, name='procesar_audio'),
    path('api/transcribir-whisper/', views.transcribir_audio_whisper, name='transcribir_whisper'),
    path('api/mejorar-texto/', views.mejorar_texto_ia, name='mejorar_texto'),
    path('api/guardar-aprendizaje/', views.guardar_correccion_aprendizaje, name='guardar_aprendizaje'),
    path('api/info-aprendizaje/', views.info_aprendizaje, name='info_aprendizaje'),
]
