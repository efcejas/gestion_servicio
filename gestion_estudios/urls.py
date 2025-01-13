"""
Configuración de URL para el proyecto gestion_estudios.

La lista `urlpatterns` dirige las URL a las vistas. Para obtener más información, consulte:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Ejemplos:
Vistas de funciones
    1. Agregue una importación: desde las vistas de importación de my_app
    2. Agregue una URL a urlpatterns: ruta('', views.home, nombre='home')
Vistas basadas en clases
    1. Agregue una importación: desde other_app.views import Inicio
    2. Agregue una URL a urlpatterns: ruta('', Home.as_view(), nombre='home')
Incluyendo otra URLconf
    1. Importe la función include(): desde django.urls importe include, ruta
    2. Agregue una URL a urlpatterns: ruta('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from .views import CustomLoginView, HomeView
from tasks.views import TareasImportantesView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TareasImportantesView.as_view(), name='home'),  # Configura la vista para la página principal
    path('accounts/login/', CustomLoginView.as_view(), name='login'),  # Vista personalizada para login
    path('accounts/', include('accounts.urls')),  # Incluye las rutas de la aplicación accounts
    path('accounts/', include('django.contrib.auth.urls')),  # Incluye todas las rutas predeterminadas de autenticación
    path('tareas/', include('tasks.urls')),  # Incluye las rutas de la aplicación tasks
    path('control_guardias/', include('control_guardias.urls')),  # Incluye las rutas de la aplicación control_guardias
    path('liquidacion/', include('liquidacion.urls')),  # Incluye las rutas de la aplicación liquidacion
]
