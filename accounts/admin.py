from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ['username', 'first_name', 'last_name', 'email', 'rol', 'perfil_completo', 'is_staff']
    list_filter = ['rol', 'perfil_completo', 'date_joined', 'is_staff']

    # Configuración de los campos en la vista de cambio de usuario
    fieldsets = (
        (None, {'fields': ('username',)}),
        ('Información personal', {'fields': ('first_name', 'last_name', 'email', 'cargo', 'telefono')}),
        ('Perfil y rol', {'fields': ('rol', 'fecha_ingreso_residencia', 'anio_residencia', 'perfil_completo', 'recibir_notificaciones')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas importantes', {'fields': ('last_login', 'date_joined', 'fecha_perfil_completado')}),
    )

    # Configuración de los campos en la vista de agregar usuario
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'first_name', 'last_name', 'email', 'rol', 'cargo', 'telefono'),
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)
