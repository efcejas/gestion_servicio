"""
URLs para la app pedidos_estudios.
"""
from django.urls import path
from . import views

app_name = 'pedidos_estudios'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
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
