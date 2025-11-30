from django.urls import path
from . import views

app_name = 'dictado_informes'

urlpatterns = [
    # Dashboard
    path('', views.DashboardDictadoView.as_view(), name='dashboard'),
    
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
    
    # API
    path('api/plantilla/<int:pk>/', views.obtener_plantilla, name='obtener_plantilla'),
    path('api/procesar-audio/', views.procesar_audio_dictado, name='procesar_audio'),
    path('api/mejorar-texto/', views.mejorar_texto_ia, name='mejorar_texto'),
]
