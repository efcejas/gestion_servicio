from django.urls import path
from .views import RegistroEstudioCreateView

urlpatterns = [
    path('nuevo/', RegistroEstudioCreateView.as_view(), name='registro_estudio'),  # Ruta para registrar un estudio
]
