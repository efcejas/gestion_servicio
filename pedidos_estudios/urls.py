
from django.urls import path
from .views import PedidoEstudioCreateView, PedidoEstudioDetailView, PedidoEstudioListView

app_name = 'pedidos_estudios'

urlpatterns = [
    path('', PedidoEstudioListView.as_view(), name='lista_pedidos'),
    path('crear/', PedidoEstudioCreateView.as_view(), name='crear_pedido'),
    path('<int:pk>/', PedidoEstudioDetailView.as_view(), name='detalle_pedido'),
]
