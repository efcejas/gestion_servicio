from django.urls import path

from . import views


app_name = 'portafolio'

urlpatterns = [
    path('', views.mi_portafolio, name='mi_portafolio'),
    path('actividades/', views.actividades_propias, name='actividades_propias'),
    path('actividades/nueva/', views.actividad_crear, name='actividad_crear'),
    path(
        'actividades/revision/',
        views.actividades_revision,
        name='actividades_revision',
    ),
    path(
        'actividades/<int:pk>/',
        views.actividad_detalle,
        name='actividad_detalle',
    ),
    path(
        'actividades/<int:pk>/editar/',
        views.actividad_editar,
        name='actividad_editar',
    ),
    path(
        'actividades/<int:pk>/enviar/',
        views.actividad_enviar,
        name='actividad_enviar',
    ),
    path(
        'actividades/<int:pk>/revisar/',
        views.actividad_revisar,
        name='actividad_revisar',
    ),
    path(
        'documentos/<int:pk>/descargar/',
        views.documento_actividad_descargar,
        name='documento_actividad_descargar',
    ),
    path(
        'documentos/<int:pk>/eliminar/',
        views.documento_actividad_eliminar,
        name='documento_actividad_eliminar',
    ),
    path('residentes/', views.seguimiento_residentes, name='seguimiento'),
    path(
        'residentes/<int:pk>/trayectoria/',
        views.trayectoria_residente,
        name='trayectoria_residente',
    ),
    path('residentes/<int:pk>/', views.detalle_residente, name='detalle_residente'),
]
