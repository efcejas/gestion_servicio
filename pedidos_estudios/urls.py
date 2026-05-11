"""
URLs para la app pedidos_estudios.
"""
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import path

from . import views
from . import views_dashboard
from . import views_medicos

app_name = 'pedidos_estudios'

def _modulo_temporalmente_desactivado(request, *args, **kwargs):
    messages.info(request, 'La seccion de solicitud de estudios esta temporalmente deshabilitada.')
    return redirect('home')


if getattr(settings, 'PEDIDOS_ESTUDIOS_HABILITADO', False):
    urlpatterns = [
        # Dashboard
        path('', views_dashboard.dashboard_pedidos, name='dashboard'),
        path('dashboard/', views_dashboard.dashboard_pedidos, name='dashboard_pedidos'),  # Alias

        # Medicos - Sus estudios
        path('mis-estudios/', views_medicos.mis_estudios_pendientes, name='mis_estudios'),
        path('estudios/<int:pedido_id>/marcar-realizado/', views_medicos.marcar_realizado, name='marcar_realizado'),

        # Medicos - Acceso con token (sin login)
        path('mis-estudios/<str:token>/', views_medicos.mis_estudios_token, name='mis_estudios_token'),
        path('estudios/<str:token>/<int:pedido_id>/marcar-realizado/', views_medicos.marcar_realizado_token, name='marcar_realizado_token'),

        # Pedidos
        path('pedidos/', views.lista_pedidos, name='lista_pedidos'),
        path('pedidos/<int:pk>/', views.detalle_pedido, name='detalle_pedido'),
        path('pedidos/<int:pk>/revisar/', views.revisar_pedido, name='revisar_pedido'),
        path('pedidos/<int:pk>/cambiar-estado/', views.cambiar_estado, name='cambiar_estado'),

        # Procesamiento
        path('procesar-emails/', views.procesar_emails_manual, name='procesar_emails'),
        path('verificar-gmail/', views.verificar_gmail, name='verificar_gmail'),
        path('logs/', views.logs_procesamiento, name='logs_procesamiento'),
    ]
else:
    urlpatterns = [
        # Se mantienen los mismos nombres de URL para no romper reverse() existentes.
        path('', _modulo_temporalmente_desactivado, name='dashboard'),
        path('dashboard/', _modulo_temporalmente_desactivado, name='dashboard_pedidos'),
        path('mis-estudios/', _modulo_temporalmente_desactivado, name='mis_estudios'),
        path('estudios/<int:pedido_id>/marcar-realizado/', _modulo_temporalmente_desactivado, name='marcar_realizado'),
        path('mis-estudios/<str:token>/', _modulo_temporalmente_desactivado, name='mis_estudios_token'),
        path('estudios/<str:token>/<int:pedido_id>/marcar-realizado/', _modulo_temporalmente_desactivado, name='marcar_realizado_token'),
        path('pedidos/', _modulo_temporalmente_desactivado, name='lista_pedidos'),
        path('pedidos/<int:pk>/', _modulo_temporalmente_desactivado, name='detalle_pedido'),
        path('pedidos/<int:pk>/revisar/', _modulo_temporalmente_desactivado, name='revisar_pedido'),
        path('pedidos/<int:pk>/cambiar-estado/', _modulo_temporalmente_desactivado, name='cambiar_estado'),
        path('procesar-emails/', _modulo_temporalmente_desactivado, name='procesar_emails'),
        path('verificar-gmail/', _modulo_temporalmente_desactivado, name='verificar_gmail'),
        path('logs/', _modulo_temporalmente_desactivado, name='logs_procesamiento'),
    ]
