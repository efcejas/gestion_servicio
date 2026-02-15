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
from django.conf import settings
from django.conf.urls.static import static

from accounts import views
from .views import (
    CustomLoginView, 
    CustomPasswordResetView,
    CustomPasswordResetDoneView,
    CustomPasswordResetConfirmView,
    CustomPasswordResetCompleteView,
    CustomPasswordChangeView,
    CustomPasswordChangeDoneView,
    HomeView, 
    send_test_email, 
    AdminDashboardView, 
    eventos_modal, 
    cambiar_estado_evento
)

urlpatterns = [
    # Administración
    path('admin/', admin.site.urls, name='admin'),

    # Página principal
    path('', HomeView.as_view(), name='home'),

    # Tablero de administración
    path('admin-dashboard/', AdminDashboardView.as_view(), name='admin_dashboard'),  # Nueva URL más descriptiva

    # Autenticación y cuentas
    path('accounts/login/', CustomLoginView.as_view(), name='login'),  # Vista personalizada de inicio de sesión
    path('accounts/', include('django.contrib.auth.urls')),  # URLs predeterminadas de Django para autenticación
    path('accounts/', include('accounts.urls')),  # URLs personalizadas para cuentas

    # Aplicaciones específicas
    path('dictado_informes/', include('dictado_informes.urls')),  # URLs para dictado de informes
    path('agenda/', include('agenda.urls')),  # URLs para agenda y notas
    path('control_guardias/', include('control_guardias.urls')),  # URLs para el control de guardias
    path('liquidacion/', include('liquidacion.urls')),  # URLs para liquidación
    path('gestion_eventos/', include('gestion_eventos.urls')),  # URLs para la gestión de eventos
    path('protocolos/', include('protocolos.urls')),  # URLs para protocolos
    path('equipos/', include('equipos.urls')),  # URLs para equipos
    path('consultorios/', include('consultorios.urls')),  # URLs para gestión de consultorios
    path('clases/', include('clases_residentes.urls')),
    path('eges/', include('eges_import.urls')),  # URLs para importación EGES
    path('preinformes/', include('preinformes.urls')),  # URLs para preinformes
    path('pedidos/', include('pedidos_estudios.urls')),  # URLs para pedidos de estudios por email

    # CKEditor 5
    path("ckeditor5/", include('django_ckeditor_5.urls')),

    # Restablecimiento de contraseñas
    path('password_change/', CustomPasswordChangeView.as_view(), name='password_change'),
    path('password_change/done/', CustomPasswordChangeDoneView.as_view(), name='password_change_done'),
    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # Prueba de envío de correos
    path('send-test-email/', send_test_email, name='send_test_email'),

    # URL para el modal de eventos del dashboard
    path('dashboard/eventos/modal/', eventos_modal, name='eventos_modal'),
    path('dashboard/eventos/<int:evento_id>/cambiar-estado/', cambiar_estado_evento, name='cambiar_estado_evento'),
]

# Servir archivos subidos por usuarios (MEDIA) en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)