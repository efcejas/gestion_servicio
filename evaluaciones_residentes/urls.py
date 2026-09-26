from django.urls import path

from . import views


app_name = 'evaluaciones_residentes'

urlpatterns = [
    path('', views.lista_examenes, name='lista'),
    path('<int:examen_id>/intentos/', views.lista_intentos, name='intentos'),
    path('mis-evaluaciones/', views.lista_residente, name='mis_evaluaciones'),
    path('mis-evaluaciones/<int:examen_id>/', views.detalle_residente, name='detalle_residente'),
    path('mis-evaluaciones/<int:examen_id>/resultado/', views.resultado_residente, name='resultado_residente'),
    path('mis-evaluaciones/<int:examen_id>/iniciar/', views.iniciar_residente, name='iniciar_residente'),
    path('intentos/<int:intento_id>/', views.intento_residente, name='intento_residente'),
    path('intentos/<int:intento_id>/confirmar-entrega/', views.confirmar_entrega, name='confirmar_entrega'),
    path('intentos/<int:intento_id>/revision/', views.revisar_intento, name='revisar_intento'),
    path('crear/', views.crear_examen, name='crear'),
    path('<int:examen_id>/editar/', views.editar_examen, name='editar'),
    path('<int:examen_id>/preguntas/', views.lista_preguntas, name='preguntas'),
    path('<int:examen_id>/preguntas/crear/', views.crear_pregunta, name='crear_pregunta'),
    path(
        '<int:examen_id>/preguntas/<int:pregunta_id>/editar/',
        views.editar_pregunta,
        name='editar_pregunta',
    ),
    path('<int:examen_id>/revision/', views.revisar_examen, name='revision'),
    path('<int:examen_id>/publicar/', views.publicar, name='publicar'),
    path('<int:examen_id>/iniciar-examen/', views.iniciar_examen, name='iniciar_examen'),
    path('<int:examen_id>/finalizar/', views.finalizar, name='finalizar'),
    path('<int:examen_id>/eliminar/', views.eliminar, name='eliminar'),
]
