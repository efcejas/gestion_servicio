"""
URLs para la app consultorios.
"""

from django.urls import path
from . import views

app_name = 'consultorios'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard_consultorios, name='dashboard'),
    
    # Lista de consultorios
    path('lista/', views.ConsultoriosListView.as_view(), name='lista'),
    
    # Detalle de consultorio
    path('<int:pk>/', views.ConsultorioDetailView.as_view(), name='detalle'),
    
    # Disponibilidad por día
    path('<int:pk>/dia/<int:dia_semana>/', views.disponibilidad_consultorio_dia, name='disponibilidad_dia'),
]
