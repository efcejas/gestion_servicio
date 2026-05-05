"""
URLs para la app consultorios.
"""

from django.urls import path
from . import views

app_name = 'consultorios'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard_consultorios, name='dashboard'),

    # Grilla semanal (todos los consultorios × 7 días)
    path('grilla/', views.grilla_semanal, name='grilla_semanal'),

    # Gestión de bloques
    path('bloques/nuevo/', views.BloqueHorarioCreateView.as_view(), name='bloque_crear'),
    path('bloques/<int:pk>/editar/', views.BloqueHorarioUpdateView.as_view(), name='bloque_editar'),

    # Lista de consultorios
    path('lista/', views.ConsultoriosListView.as_view(), name='lista'),

    # Detalle de consultorio
    path('<int:pk>/', views.ConsultorioDetailView.as_view(), name='detalle'),

    # Disponibilidad por día
    path('<int:pk>/dia/<int:dia_semana>/', views.disponibilidad_consultorio_dia, name='disponibilidad_dia'),

    # Circuito de ausencias y coberturas
    path('bloques/<int:pk>/reportar-ausencia/', views.reportar_ausencia, name='reportar_ausencia'),
    path('ausencias/<int:ausencia_pk>/confirmar/<int:residente_pk>/', views.confirmar_cobertura, name='confirmar_cobertura'),
    path('ausencias/pendientes/', views.ausencias_pendientes, name='ausencias_pendientes'),
    path('ausencias/historial/', views.ausencias_historial, name='ausencias_historial'),

    # CRUD Consultorios (salas)
    path('nuevo/', views.ConsultorioCreateView.as_view(), name='consultorio_nuevo'),
    path('<int:pk>/editar/', views.ConsultorioUpdateView.as_view(), name='consultorio_editar'),

    # CRUD Profesionales Externos
    path('profesionales/', views.profesionales_lista, name='profesionales_lista'),
    path('profesionales/nuevo/', views.ProfesionalExternoCreateView.as_view(), name='profesional_nuevo'),
    path('profesionales/<int:pk>/editar/', views.ProfesionalExternoUpdateView.as_view(), name='profesional_editar'),
]
