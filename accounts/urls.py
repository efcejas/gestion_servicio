from django.urls import path
from .views import (
    UserRegisterView,
    completar_perfil,
    confirmar_notificacion_ciclo,
    editar_perfil,
    eliminar_avatar,
    username_recovery,
    username_recovery_done,
)

app_name = 'accounts'

urlpatterns = [
    path('register/', UserRegisterView.as_view(), name='register'),
    path('completar-perfil/', completar_perfil, name='completar_perfil'),
    path('editar-perfil/', editar_perfil, name='editar_perfil'),
    path('eliminar-avatar/', eliminar_avatar, name='eliminar_avatar'),
    path(
        'notificaciones-ciclo/<int:pk>/confirmar/',
        confirmar_notificacion_ciclo,
        name='confirmar_notificacion_ciclo',
    ),
    path('recuperar-usuario/', username_recovery, name='username_recovery'),
    path('recuperar-usuario/confirmacion/', username_recovery_done, name='username_recovery_done'),
]
