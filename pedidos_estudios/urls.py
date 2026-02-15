"""
URLs para la app pedidos_estudios.
"""
from django.urls import path
from . import views
from . import views_dashboard
from . import views_medicos

app_name = 'pedidos_estudios'

urlpatterns = [
    # Dashboard
    path('', views_dashboard.dashboard_pedidos, name='dashboard'),
    path('dashboard/', views_dashboard.dashboard_pedidos, name='dashboard_pedidos'),  # Alias
    
    # Médicos - Sus estudios
    path('mis-estudios/', views_medicos.mis_estudios_pendientes, name='mis_estudios'),
    path('estudios/<int:pedido_id>/marcar-realizado/', views_medicos.marcar_realizado, name='marcar_realizado'),
    
    # Médicos - Acceso con token (sin login)
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
