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
    path('mis-preinformes/', views.mis_preinformes, name='mis_preinformes'),
    path('ver/<int:pk>/', views.ver_preinforme, name='ver_preinforme'),
    
    # Revisión - Staff
    path('revision/', views.lista_revision, name='lista_revision'),
    path('revisar/<int:pk>/', views.revisar_preinforme, name='revisar_preinforme'),
    path('revision/<int:pk>/autosave/', views.autosave_revision, name='autosave_revision'),
    path('comparacion/<int:pk>/', views.ver_comparacion_revision, name='comparacion_revision'),
    
    # AJAX
    path('cargar-plantillas/', views.cargar_plantillas, name='cargar_plantillas'),
    path('plantillas/<int:pk>/json/', views.plantilla_json, name='plantilla_json'),
    path('plantillas/crear/', views.crear_plantilla_residente, name='crear_plantilla_residente'),
    path('<int:pk>/autosave/', views.autosave_preinforme, name='autosave_preinforme'),
    path('<int:pk>/generar-informe/', views.generar_informe_final, name='generar_informe_final'),
    path('copiar-informe/<int:pk>/', views.copiar_informe_final, name='copiar_informe_final'),
    
    # Estadísticas
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    
]