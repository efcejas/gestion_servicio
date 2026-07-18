from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, NotificacionCicloResidencia
from .forms import CustomUserCreationForm, CustomUserChangeForm


class CustomUserAdminChangeForm(CustomUserChangeForm):
    class Meta(CustomUserChangeForm.Meta):
        fields = CustomUserChangeForm.Meta.fields + [
            'estado_residencia', 'repite_anio_residencia',
            'fecha_egreso_residencia', 'ultimo_cierre_residencia',
        ]

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserAdminChangeForm
    model = CustomUser
    list_display = [
        'username', 'first_name', 'last_name', 'email', 'rol', 'anio_residencia',
        'estado_residencia', 'repite_anio_residencia', 'trabaja_remoto', 'perfil_completo', 'is_staff',
    ]
    list_filter = [
        'rol', 'estado_residencia', 'repite_anio_residencia', 'trabaja_remoto',
        'perfil_completo', 'date_joined', 'is_staff',
    ]
    
    # Campos de solo lectura (calculados automáticamente)
    readonly_fields = [
        'anio_residencia', 'fecha_egreso_residencia', 'ultimo_cierre_residencia',
        'fecha_perfil_completado', 'last_login', 'date_joined',
    ]

    # Configuración de los campos en la vista de cambio de usuario
    fieldsets = (
        (None, {'fields': ('username',)}),
        ('Información personal', {'fields': ('first_name', 'last_name', 'email', 'cargo', 'telefono')}),
        ('Perfil y rol', {'fields': ('rol', 'trabaja_remoto', 'perfil_completo', 'recibir_notificaciones')}),
        ('Residencia', {'fields': (
            'fecha_ingreso_residencia', 'anio_residencia', 'estado_residencia',
            'repite_anio_residencia', 'fecha_egreso_residencia', 'ultimo_cierre_residencia',
        )}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas importantes', {'fields': ('last_login', 'date_joined', 'fecha_perfil_completado')}),
    )

    # Configuración de los campos en la vista de agregar usuario
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'first_name', 'last_name', 'email', 'rol', 'trabaja_remoto', 'cargo', 'telefono'),
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(NotificacionCicloResidencia)
class NotificacionCicloResidenciaAdmin(admin.ModelAdmin):
    list_display = [
        'usuario', 'tipo', 'anio_anterior', 'anio_nuevo',
        'cierre_anio', 'creada_en', 'vista_en',
    ]
    list_filter = ['tipo', 'cierre_anio', 'vista_en']
    search_fields = [
        'usuario__username', 'usuario__first_name', 'usuario__last_name',
    ]
    readonly_fields = [
        'usuario', 'tipo', 'anio_anterior', 'anio_nuevo',
        'cierre_anio', 'creada_en', 'vista_en',
    ]

    def has_add_permission(self, request):
        return False
