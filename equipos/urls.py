from django.urls import path
from .views import EquiposListView

app_name = 'equipos'

urlpatterns = [
    path('', EquiposListView.as_view(), name='equipos_lista'),
]
