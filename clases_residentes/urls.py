from django.urls import path
from . import views

app_name = 'clases_residentes'

urlpatterns = [
    # Lista y búsqueda
    path('', views.ClaseListView.as_view(), name='lista'),
    
    # CRUD de clases
    path('crear/', views.ClaseCreateView.as_view(), name='crear'),
    path('<int:pk>/', views.ClaseDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.ClaseUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.ClaseDeleteView.as_view(), name='eliminar'),
    
    # Interacciones
    path('<int:pk>/comentario/', views.agregar_comentario, name='agregar_comentario'),
    path('<int:pk>/favorito/', views.toggle_favorito, name='toggle_favorito'),
    
    # Vistas personales
    path('mis-clases/', views.mis_clases, name='mis_clases'),
    path('favoritos/', views.favoritos, name='favoritos'),
    
    # Gestión (solo jefes/instructores)
    path('gestionar/', views.gestionar_clases, name='gestionar'),
    path('<int:pk>/cambiar-estado/', views.cambiar_estado_clase, name='cambiar_estado'),
]
