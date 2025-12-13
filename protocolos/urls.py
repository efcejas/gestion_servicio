from django.urls import path
from .views import ProtocoloListView, ProtocoloDetailView, elegir_protocolo

app_name = 'protocolos'

urlpatterns = [
    path('', ProtocoloListView.as_view(), name='lista'),
    path('elegir/', elegir_protocolo, name='elegir'),
    path('<int:pk>/', ProtocoloDetailView.as_view(), name='detalle'),
]
