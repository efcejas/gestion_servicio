from django.urls import path
from .views import UserRegisterView, completar_perfil, editar_perfil, username_recovery, username_recovery_done

app_name = 'accounts'

urlpatterns = [
    path('register/', UserRegisterView.as_view(), name='register'),
    path('completar-perfil/', completar_perfil, name='completar_perfil'),
    path('editar-perfil/', editar_perfil, name='editar_perfil'),
    path('recuperar-usuario/', username_recovery, name='username_recovery'),
    path('recuperar-usuario/confirmacion/', username_recovery_done, name='username_recovery_done'),
]
