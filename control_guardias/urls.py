from django.urls import path
from .views import GuardiaListView

urlpatterns = [
    path('coberturas-semanal/', GuardiaListView.as_view(), name='coberturas_semanal'),
]