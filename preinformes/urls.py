from django.urls import path
from . import views

app_name = 'preinformes'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_residente, name='dashboard_residente'),
    path('staff/', views.dashboard_staff, name='dashboard_staff'),
    
    # Preinformes - Residentes
    path('nuevo/', views.crear_preinforme, name='crear_preinforme'),
    path('editar/<int:pk>/', views.editar_preinforme, name='editar_preinforme'),
    path('eliminar/<int:pk>/', views.eliminar_preinforme, name='eliminar_preinforme'),
    path('mis-preinformes/', views.mis_preinformes, name='mis_preinformes'),
    path('ver/<int:pk>/', views.ver_preinforme, name='ver_preinforme'),
    path('ver/<int:pk>/marcar-correccion-vista/', views.marcar_correccion_vista, name='marcar_correccion_vista'),
    
    # Banco de Informes (pool compartido de finalizados)
    path('banco/', views.lista_banco_informes, name='lista_banco_informes'),
    path('banco/<int:pk>/', views.ver_banco_preinforme, name='ver_banco_preinforme'),
    
    # Revisión - Staff
    path('revision/', views.lista_revision, name='lista_revision'),
    path('revisar/<int:pk>/', views.revisar_preinforme, name='revisar_preinforme'),
    path('asignar/<int:pk>/', views.asignar_revisor, name='asignar_revisor'),
    path('tomar/<int:pk>/', views.tomar_estudio, name='tomar_estudio'),
    path('revision/<int:pk>/autosave/', views.autosave_revision, name='autosave_revision'),
    path('comparacion/<int:pk>/', views.ver_comparacion_revision, name='comparacion_revision'),
    
    # AJAX
    path('cargar-plantillas/', views.cargar_plantillas, name='cargar_plantillas'),
    path('plantillas/<int:pk>/json/', views.plantilla_json, name='plantilla_json'),
    path('plantillas/propuestas/<int:pk>/json/', views.propuesta_plantilla_json, name='propuesta_plantilla_json'),
    path('plantillas/validacion/', views.lista_validacion_plantillas, name='lista_validacion_plantillas'),
    path('plantillas/validacion/<int:pk>/', views.validar_plantilla, name='validar_plantilla'),
    path('plantillas/crear/', views.crear_plantilla_residente, name='crear_plantilla_residente'),
    path('plantillas/ia/generar/', views.generar_plantilla_ia, name='generar_plantilla_ia'),
    path('plantillas/ia/aceptar/', views.aceptar_borrador_plantilla_ia, name='aceptar_borrador_plantilla_ia'),
    path('plantillas/ia/<int:pk>/aceptar/', views.aceptar_plantilla_ia, name='aceptar_plantilla_ia'),
    path('plantillas/ia/<int:pk>/aplicar/', views.aplicar_plantilla_ia, name='aplicar_plantilla_ia'),
    path('<int:pk>/autosave/', views.autosave_preinforme, name='autosave_preinforme'),
    path('<int:pk>/generar-informe/', views.generar_informe_final, name='generar_informe_final'),
    path('copiar-informe/<int:pk>/', views.copiar_informe_final, name='copiar_informe_final'),
    
    # Etiquetas
    path('<int:pk>/etiquetas/', views.agregar_etiquetas, name='agregar_etiquetas'),
    path('etiquetas/buscar/', views.buscar_etiquetas, name='buscar_etiquetas'),
    
    # Verificación de duplicados
    path('verificar-duplicado/', views.verificar_duplicado_preinforme, name='verificar_duplicado'),
    
    # Estadísticas
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    path('panel-docencia/', views.panel_docencia, name='panel_docencia'),

    # Asistente IA Radiólogo Mentor
    path('asistente/chat/', views.asistente_preinforme_chat, name='asistente_chat'),
    path('asistente/feedback/', views.asistente_preinforme_feedback, name='asistente_feedback'),
    path('asistente/evaluar/', views.asistente_preinforme_evaluar, name='asistente_evaluar'),
    path('asistente/analizar/', views.asistente_analizar_borrador, name='asistente_analizar'),
    path('perfil-residente/<int:pk>/', views.perfil_residente_docente, name='perfil_residente_docente'),

    # Encuesta CADI 2026
    path('encuesta/', views.encuesta_uso, name='encuesta_uso'),
    path('encuesta/resultados/', views.resultados_encuesta, name='resultados_encuesta'),
]
