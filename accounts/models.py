from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class CustomUser(AbstractUser):
    """
    Usuario extendido con sistema de perfiles por rol.
    Flujo: Registro básico -> Completar perfil -> Acceso completo
    """
    
    # Roles principales (simplificados y agrupados)
    ROL_CHOICES = [
        ('medico_staff', 'Médico de Staff'),
        ('medico_residente', 'Médico Residente'),
        ('jefe_servicio', 'Jefe de Servicio'),
        ('tecnico', 'Técnico Radiólogo'),
        ('administrativo', 'Administrativo'),
        ('enfermeria', 'Enfermería'),
        ('otro', 'Otro'),
    ]
    
    # Campos de perfil
    rol = models.CharField(
        max_length=30, 
        choices=ROL_CHOICES, 
        blank=True, 
        null=True,
        help_text='Rol principal del usuario en el servicio'
    )
    cargo = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text='Cargo o especialización específica (opcional)'
    )
    telefono = models.CharField(max_length=50, blank=True, null=True)
    
    # Control de perfil
    perfil_completo = models.BooleanField(
        default=False,
        help_text='Indica si el usuario completó su perfil post-registro'
    )
    fecha_perfil_completado = models.DateTimeField(
        blank=True, 
        null=True,
        help_text='Fecha en que se completó el perfil por primera vez'
    )
    
    # Preferencias de usuario
    recibir_notificaciones = models.BooleanField(
        default=True,
        help_text='Recibir notificaciones por email'
    )
    
    def __str__(self):
        return f"{self.username} - {self.get_rol_display() if self.rol else 'Sin rol'}"
    
    def marcar_perfil_completo(self):
        """Marca el perfil como completo y registra la fecha."""
        if not self.perfil_completo:
            self.perfil_completo = True
            self.fecha_perfil_completado = timezone.now()
            self.save(update_fields=['perfil_completo', 'fecha_perfil_completado'])
    
    def puede_acceder_protocolos(self):
        """Verifica si el usuario puede acceder a protocolos radiológicos."""
        roles_permitidos = ['medico_staff', 'medico_residente', 'jefe_servicio', 'tecnico']
        return self.rol in roles_permitidos or self.is_superuser
    
    def es_medico(self):
        """Verifica si el usuario es médico (staff o residente)."""
        return self.rol in ['medico_staff', 'medico_residente', 'jefe_servicio']
    
    def es_residente(self):
        """Verifica si el usuario es residente."""
        return self.rol == 'medico_residente'


