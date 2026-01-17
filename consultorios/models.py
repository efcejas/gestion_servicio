"""
Modelos para gestión de consultorios, equipos y disponibilidad horaria.

Diseño:
- Consultorio: Sala física donde se realizan estudios
- ProfesionalExterno: Profesionales que no son usuarios del sistema
- AsignacionEquipoConsultorio: Relación entre equipos y consultorios
- BloqueHorario: Franjas horarias asignadas a profesionales (internos o externos)
"""

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from equipos.models import EquipoImagen
from .managers import ConsultorioManager, ProfesionalExternoManager, BloqueHorarioManager


class Consultorio(models.Model):
    """
    Representa un consultorio o sala donde se realizan estudios.
    Típicamente: Consultorio Eco 1, Consultorio Eco 2, etc.
    """
    nombre = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nombre identificativo del consultorio (ej: 'Eco 1', 'Eco 2')"
    )
    
    ubicacion = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Ubicación física (ej: 'Piso 2, Ala Norte')"
    )
    
    esta_activo = models.BooleanField(
        default=True,
        help_text="¿El consultorio está actualmente operativo?"
    )
    
    capacidad_pacientes_hora = models.PositiveIntegerField(
        default=4,
        help_text="Capacidad estimada de pacientes por hora"
    )
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text="Notas adicionales sobre el consultorio"
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    # Manager personalizado
    objects = ConsultorioManager()
    
    class Meta:
        verbose_name = "Consultorio"
        verbose_name_plural = "Consultorios"
        ordering = ['nombre']
    
    def __str__(self):
        estado = "✓" if self.esta_activo else "✗"
        return f"{estado} {self.nombre}"
    
    def equipos_asignados(self):
        """Retorna los equipos actualmente asignados al consultorio"""
        return AsignacionEquipoConsultorio.objects.filter(
            consultorio=self,
            es_permanente=True
        ).select_related('equipo') | AsignacionEquipoConsultorio.objects.filter(
            consultorio=self,
            fecha_inicio__lte=timezone.now().date(),
            fecha_fin__gte=timezone.now().date()
        ).select_related('equipo')


class ProfesionalExterno(models.Model):
    """
    Representa un profesional que trabaja en los consultorios
    pero NO es usuario del sistema (profesional externo/invitado).
    """
    nombre = models.CharField(
        max_length=100,
        help_text="Nombre completo del profesional"
    )
    
    apellido = models.CharField(
        max_length=100,
        help_text="Apellido del profesional"
    )
    
    matricula = models.CharField(
        max_length=50,
        unique=True,
        help_text="Matrícula profesional (nacional o provincial)"
    )
    
    especialidad = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Especialidad médica (ej: 'Ecografía', 'Radiología')"
    )
    
    telefono = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Teléfono de contacto"
    )
    
    email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email de contacto"
    )
    
    esta_activo = models.BooleanField(
        default=True,
        help_text="¿El profesional está actualmente activo?"
    )
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text="Notas adicionales sobre el profesional"
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    # Manager personalizado
    objects = ProfesionalExternoManager()
    
    class Meta:
        verbose_name = "Profesional Externo"
        verbose_name_plural = "Profesionales Externos"
        ordering = ['apellido', 'nombre']
    
    def __str__(self):
        estado = "✓" if self.esta_activo else "✗"
        return f"{estado} Dr./Dra. {self.apellido}, {self.nombre}"
    
    def nombre_completo(self):
        """Retorna el nombre completo del profesional"""
        return f"{self.nombre} {self.apellido}"


class AsignacionEquipoConsultorio(models.Model):
    """
    Relaciona equipos con consultorios.
    Permite rotación temporal de equipos entre consultorios.
    """
    consultorio = models.ForeignKey(
        Consultorio,
        on_delete=models.CASCADE,
        related_name='asignaciones_equipos'
    )
    
    equipo = models.ForeignKey(
        EquipoImagen,
        on_delete=models.CASCADE,
        related_name='asignaciones_consultorios'
    )
    
    fecha_inicio = models.DateField(
        default=timezone.now,
        help_text="Fecha de inicio de la asignación"
    )
    
    fecha_fin = models.DateField(
        blank=True,
        null=True,
        help_text="Fecha de fin de la asignación (dejar vacío si es permanente)"
    )
    
    es_permanente = models.BooleanField(
        default=False,
        help_text="¿La asignación es permanente? (ignora fecha_fin)"
    )
    
    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text="Notas sobre esta asignación (ej: 'Rotación por mantenimiento')"
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Asignación Equipo-Consultorio"
        verbose_name_plural = "Asignaciones Equipo-Consultorio"
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        tipo = "Permanente" if self.es_permanente else f"Temporal ({self.fecha_inicio} - {self.fecha_fin or 'Indefinido'})"
        return f"{self.equipo.nombre} → {self.consultorio.nombre} ({tipo})"
    
    def clean(self):
        """Validaciones del modelo"""
        from django.core.exceptions import ValidationError
        
        # Si no es permanente, debe tener fecha de fin
        if not self.es_permanente:
            if not self.fecha_fin:
                raise ValidationError({
                    'fecha_fin': "Si la asignación no es permanente, debe especificar una fecha de fin."
                })
            
            # Validar que fecha_inicio < fecha_fin
            if self.fecha_inicio and self.fecha_fin and self.fecha_inicio > self.fecha_fin:
                raise ValidationError({
                    'fecha_fin': "La fecha de fin no puede ser anterior a la fecha de inicio."
                })
    
    def esta_vigente(self):
        """Verifica si la asignación está vigente en la fecha actual"""
        if self.es_permanente:
            return True
        
        hoy = timezone.now().date()
        if self.fecha_fin:
            return self.fecha_inicio <= hoy <= self.fecha_fin
        return self.fecha_inicio <= hoy


class TipoActividad(models.TextChoices):
    """Tipos de actividades que se realizan en los consultorios"""
    ECO_GENERAL = 'ECO_GENERAL', 'Ecografía General'
    ECO_DOPPLER = 'ECO_DOPPLER', 'Ecografía Doppler'
    ECO_OBSTETRICA = 'ECO_OBSTETRICA', 'Ecografía Obstétrica'
    ECO_PEDIATRICA = 'ECO_PEDIATRICA', 'Ecografía Pediátrica'
    ECO_MUSCULOESQUELETICA = 'ECO_MSK', 'Ecografía Musculoesquelética'
    INTERVENCIONISMO = 'INTERV', 'Intervencionismo Ecoguiado'
    OTRO = 'OTRO', 'Otro'


class EstadoBloque(models.TextChoices):
    """Estados posibles de un bloque horario"""
    ACTIVO = 'ACTIVO', 'Activo'
    PAUSADO = 'PAUSADO', 'Pausado'
    FINALIZADO = 'FINALIZADO', 'Finalizado'


class DiaSemana(models.IntegerChoices):
    """Días de la semana (0=Lunes, 6=Domingo)"""
    LUNES = 0, 'Lunes'
    MARTES = 1, 'Martes'
    MIERCOLES = 2, 'Miércoles'
    JUEVES = 3, 'Jueves'
    VIERNES = 4, 'Viernes'
    SABADO = 5, 'Sábado'
    DOMINGO = 6, 'Domingo'


class BloqueHorario(models.Model):
    """
    Representa una franja horaria asignada a un profesional en un consultorio.
    Puede ser un profesional interno (usuario del sistema) o externo.
    """
    consultorio = models.ForeignKey(
        Consultorio,
        on_delete=models.CASCADE,
        related_name='bloques_horarios'
    )
    
    # Profesional - FLEXIBLE: interno O externo
    profesional_interno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bloques_horarios',
        blank=True,
        null=True,
        help_text="Profesional registrado en el sistema"
    )
    
    profesional_externo = models.ForeignKey(
        ProfesionalExterno,
        on_delete=models.CASCADE,
        related_name='bloques_horarios',
        blank=True,
        null=True,
        help_text="Profesional externo (no usuario del sistema)"
    )
    
    # Equipo específico (opcional, puede usar cualquier equipo del consultorio)
    equipo = models.ForeignKey(
        EquipoImagen,
        on_delete=models.SET_NULL,
        related_name='bloques_horarios',
        blank=True,
        null=True,
        help_text="Equipo específico a usar (opcional)"
    )
    
    # Configuración de tiempo
    dia_semana = models.IntegerField(
        choices=DiaSemana.choices,
        help_text="Día de la semana (0=Lunes, 6=Domingo)"
    )
    
    hora_inicio = models.TimeField(
        help_text="Hora de inicio del bloque"
    )
    
    hora_fin = models.TimeField(
        help_text="Hora de fin del bloque"
    )
    
    # Vigencia
    fecha_inicio_vigencia = models.DateField(
        default=timezone.now,
        help_text="Fecha desde la cual este bloque está vigente"
    )
    
    fecha_fin_vigencia = models.DateField(
        blank=True,
        null=True,
        help_text="Fecha hasta la cual este bloque está vigente (vacío = indefinido)"
    )
    
    # Tipo de actividad y estado
    tipo_actividad = models.CharField(
        max_length=20,
        choices=TipoActividad.choices,
        default=TipoActividad.ECO_GENERAL,
        help_text="Tipo de estudios a realizar en este bloque"
    )
    
    estado = models.CharField(
        max_length=20,
        choices=EstadoBloque.choices,
        default=EstadoBloque.ACTIVO,
        help_text="Estado actual del bloque horario"
    )
    
    # Información adicional
    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text="Notas adicionales sobre este bloque"
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='bloques_creados',
        blank=True,
        null=True,
        help_text="Usuario que creó este bloque"
    )
    
    # Manager personalizado
    objects = BloqueHorarioManager()
    
    class Meta:
        verbose_name = "Bloque Horario"
        verbose_name_plural = "Bloques Horarios"
        ordering = ['dia_semana', 'hora_inicio']
        indexes = [
            models.Index(fields=['consultorio', 'dia_semana', 'estado']),
            models.Index(fields=['profesional_interno', 'estado']),
            models.Index(fields=['profesional_externo', 'estado']),
        ]
    
    def __str__(self):
        profesional = self.nombre_profesional()
        dia = self.get_dia_semana_display()
        return f"{profesional} - {self.consultorio.nombre} - {dia} {self.hora_inicio}-{self.hora_fin}"
    
    def clean(self):
        """Validaciones del modelo"""
        # Validar que haya al menos un profesional asignado
        if not self.profesional_interno and not self.profesional_externo:
            raise ValidationError(
                "Debe especificar un profesional interno O un profesional externo."
            )
        
        # Validar que no haya ambos profesionales asignados
        if self.profesional_interno and self.profesional_externo:
            raise ValidationError(
                "No puede asignar un profesional interno Y un profesional externo simultáneamente. Elija uno."
            )
        
        # Validar que hora_inicio sea antes que hora_fin
        if self.hora_inicio >= self.hora_fin:
            raise ValidationError(
                "La hora de inicio debe ser anterior a la hora de fin."
            )
        
        # Validar fechas de vigencia
        if self.fecha_fin_vigencia and self.fecha_inicio_vigencia > self.fecha_fin_vigencia:
            raise ValidationError(
                "La fecha de inicio de vigencia no puede ser posterior a la fecha de fin."
            )
        
        # Validar que el equipo (si se especifica) esté asignado al consultorio
        if self.equipo:
            asignacion_valida = AsignacionEquipoConsultorio.objects.filter(
                consultorio=self.consultorio,
                equipo=self.equipo
            ).filter(
                models.Q(es_permanente=True) |
                models.Q(
                    fecha_inicio__lte=timezone.now().date(),
                    fecha_fin__gte=timezone.now().date()
                )
            ).exists()
            
            if not asignacion_valida:
                raise ValidationError(
                    f"El equipo '{self.equipo.nombre}' no está asignado al consultorio '{self.consultorio.nombre}'."
                )
        
        # Validar conflictos de horario (solo si estado es ACTIVO)
        if self.estado == EstadoBloque.ACTIVO:
            from .utils import ConflictDetector
            ConflictDetector.validar_bloque(self)
    
    def nombre_profesional(self):
        """Retorna el nombre del profesional (interno o externo)"""
        if self.profesional_interno:
            return f"{self.profesional_interno.get_full_name() or self.profesional_interno.username}"
        elif self.profesional_externo:
            return self.profesional_externo.nombre_completo()
        return "Sin asignar"
    
    def esta_vigente(self, fecha=None):
        """Verifica si el bloque está vigente en una fecha específica"""
        if fecha is None:
            fecha = timezone.now().date()
        
        # Verificar estado
        if self.estado != EstadoBloque.ACTIVO:
            return False
        
        # Verificar vigencia
        if fecha < self.fecha_inicio_vigencia:
            return False
        
        if self.fecha_fin_vigencia and fecha > self.fecha_fin_vigencia:
            return False
        
        return True
    
    def duracion_horas(self):
        """Calcula la duración del bloque en horas"""
        if not self.hora_inicio or not self.hora_fin:
            return 0
        
        from datetime import datetime, timedelta
        inicio = datetime.combine(datetime.today(), self.hora_inicio)
        fin = datetime.combine(datetime.today(), self.hora_fin)
        duracion = fin - inicio
        return duracion.total_seconds() / 3600
