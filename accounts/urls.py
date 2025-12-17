from django.urls import path
from .views import UserRegisterView, completar_perfil, editar_perfil

app_name = 'accounts'

urlpatterns = [
    path('register/', UserRegisterView.as_view(), name='register'),
    path('completar-perfil/', completar_perfil, name='completar_perfil'),
    path('editar-perfil/', editar_perfil, name='editar_perfil'),
]
