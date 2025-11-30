from django.urls import path
from . import views

app_name = 'dictado_informes'

urlpatterns = [
    # Dashboard
    path('', views.DashboardDictadoView.as_view(), name='dashboard'),
    
    # Informes
    path('informes/', views.InformeListView.as_view(), name='lista_informes'),
    path('informes/nuevo/', views.InformeCreateView.as_view(), name='crear_informe'),
    path('informes/<int:pk>/', views.InformeDetailView.as_view(), name='detalle_informe'),
    path('informes/<int:pk>/editar/', views.InformeUpdateView.as_view(), name='editar_informe'),
    path('informes/<int:pk>/eliminar/', views.InformeDeleteView.as_view(), name='eliminar_informe'),
    path('informes/<int:pk>/firmar/', views.firmar_informe, name='firmar_informe'),
    
    # Plantillas
    path('plantillas/', views.PlantillaListView.as_view(), name='lista_plantillas'),
    path('plantillas/nueva/', views.PlantillaCreateView.as_view(), name='crear_plantilla'),
    path('plantillas/<int:pk>/editar/', views.PlantillaUpdateView.as_view(), name='editar_plantilla'),
    
    # API
    path('api/plantilla/<int:pk>/', views.obtener_plantilla, name='obtener_plantilla'),
]
