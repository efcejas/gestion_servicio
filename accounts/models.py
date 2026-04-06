from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta

class CustomUser(AbstractUser):
    """
    Usuario extendido con sistema de perfiles por rol.
    Flujo: Registro básico -> Completar perfil -> Acceso completo
    """
    
    # Roles principales (simplificados y agrupados)
    ROL_CHOICES = [
        ('medico_staff', 'Médico de Staff'),
        ('medico_residente', 'Médico Residente'),
        ('jefe_residentes', 'Jefe de Residentes'),
        ('instructor_residentes', 'Instructor de Residentes'),
        ('jefe_servicio', 'Jefe de Servicio'),
        ('cardiologo', 'Cardiólogo'),  # NUEVO - Liquidación v2.0
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
    
    # NUEVO - Liquidación v2.0: Para bonus urgencia RM a distancia
    trabaja_remoto = models.BooleanField(
        default=False,
        help_text='Médico trabaja a distancia (para cálculo bonus urgencia RM)'
    )
    
    # Campos específicos para residentes
    fecha_ingreso_residencia = models.DateField(
        blank=True,
        null=True,
        help_text='Fecha de ingreso a la residencia (para cálculo automático de año)'
    )
    anio_residencia = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        help_text='Año de residencia calculado automáticamente (R1, R2, R3, R4, R5)'
    )
    
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
    
    def calcular_anio_residencia(self):
        """
        Calcula el año de residencia basado en la fecha de ingreso.
        Retorna: 'R1', 'R2', 'R3', 'R4', 'R5' o None si no aplica
        """
        if not self.fecha_ingreso_residencia or self.rol != 'medico_residente':
            return None
        
        # Calcular diferencia en meses desde el ingreso
        hoy = timezone.now().date()
        meses_transcurridos = relativedelta(hoy, self.fecha_ingreso_residencia).years * 12 + \
                             relativedelta(hoy, self.fecha_ingreso_residencia).months
        
        # Determinar año de residencia
        if meses_transcurridos < 12:
            return 'R1'
        elif meses_transcurridos < 24:
            return 'R2'
        elif meses_transcurridos < 36:
            return 'R3'
        else:
            return 'R4'
    
    def actualizar_anio_residencia(self):
        """Actualiza el año de residencia si es residente y tiene fecha de ingreso"""
        if self.rol == 'medico_residente' and self.fecha_ingreso_residencia:
            anio_calculado = self.calcular_anio_residencia()
            if anio_calculado and self.anio_residencia != anio_calculado:
                self.anio_residencia = anio_calculado
                self.save(update_fields=['anio_residencia'])
    
    def marcar_perfil_completo(self):
        """Marca el perfil como completo y registra la fecha."""
        if not self.perfil_completo:
            self.perfil_completo = True
            self.fecha_perfil_completado = timezone.now()
            # Si es residente, calcular año de residencia
            if self.rol == 'medico_residente' and self.fecha_ingreso_residencia:
                self.anio_residencia = self.calcular_anio_residencia()
            self.save(update_fields=['perfil_completo', 'fecha_perfil_completado', 'anio_residencia'])
    
    def puede_acceder_protocolos(self):
        """Verifica si el usuario puede acceder a protocolos radiológicos."""
        roles_permitidos = ['medico_staff', 'medico_residente', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio', 'tecnico']
        return self.rol in roles_permitidos or self.is_superuser
    
    def es_medico(self):
        """Verifica si el usuario es médico (staff, residente, jefe de residentes, instructor, jefe de servicio o cardiólogo)."""
        return self.rol in ['medico_staff', 'medico_residente', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio', 'cardiologo']
    
    def es_residente(self):
        """Verifica si el usuario es residente."""
        return self.rol == 'medico_residente'


