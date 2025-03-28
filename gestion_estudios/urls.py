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
from django.contrib.auth import views as auth_views
from django.urls import path, include
from .views import CustomLoginView, HomeView, send_test_email

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HomeView.as_view(), name='home'),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),  # Primero incluimos las de Django
    path('accounts/', include('accounts.urls')),  # Luego las personalizadas
    path('tareas/', include('tasks.urls')),
    path('control_guardias/', include('control_guardias.urls')),
    path('liquidacion/', include('liquidacion.urls')),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('send-test-email/', send_test_email, name='send_test_email'),
]