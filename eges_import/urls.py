from django.urls import path
from . import views

app_name = 'eges_import'

urlpatterns = [
    path('', views.lista_batches, name='lista_batches'),
    path('dashboard/', views.dashboard_global, name='dashboard_global'),
    path('importar/', views.importar_eges, name='importar'),
    path('batch/<int:batch_id>/', views.detalle_batch, name='detalle_batch'),
    path('batch/<int:batch_id>/grafico-data/', views.grafico_batch_data, name='grafico_batch_data'),
    path('batch/<int:batch_id>/grafico-dia-semana/', views.grafico_dia_semana_data, name='grafico_dia_semana_data'),
    path('batch/<int:batch_id>/grafico-franja-horaria/', views.grafico_franja_horaria_data, name='grafico_franja_horaria_data'),
    path('dashboard/grafico-data/', views.dashboard_global_grafico_data, name='dashboard_global_grafico_data'),
    path('dashboard/grafico-dia-semana/', views.dashboard_global_dia_semana_data, name='dashboard_global_dia_semana_data'),
    path('dashboard/grafico-franja-horaria/', views.dashboard_global_franja_horaria_data, name='dashboard_global_franja_horaria_data'),
]
