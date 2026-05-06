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
        hoy = timezone.now().date()
        return AsignacionEquipoConsultorio.objects.filter(
            consultorio=self
        ).filter(
            models.Q(es_permanente=True) |
            models.Q(
                fecha_inicio__lte=hoy,
                fecha_fin__gte=hoy
            )
        ).select_related('equipo').distinct()


class CategoriaProfesionalExterno(models.TextChoices):
    """Categorías operativas para profesionales externos"""
    STAFF_EXTERNO = 'STAFF_EXT', 'Staff Externo'
    CARDIOLOGO_EXTERNO = 'CARD_EXT', 'Cardiólogo Externo'
    OTRO_EXTERNO = 'OTRO_EXT', 'Otro Externo'


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

    categoria = models.CharField(
        max_length=20,
        choices=CategoriaProfesionalExterno.choices,
        default=CategoriaProfesionalExterno.STAFF_EXTERNO,
        help_text="Clasificación operativa del profesional externo"
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
        
        # Asegurar que fecha_inicio sea date, no datetime
        fecha_inicio = self.fecha_inicio
        if hasattr(fecha_inicio, 'date'):
            fecha_inicio = fecha_inicio.date()
        
        if self.fecha_fin:
            fecha_fin = self.fecha_fin
            if hasattr(fecha_fin, 'date'):
                fecha_fin = fecha_fin.date()
            return fecha_inicio <= hoy <= fecha_fin
        
        return fecha_inicio <= hoy


class TipoActividad(models.TextChoices):
    """Tipos de actividades que se realizan en los consultorios"""
    ECO_GENERAL = 'ECO_GENERAL', 'Ecografía General'
    ECO_DOPPLER = 'ECO_DOPPLER', 'Ecografía Doppler'
    ECO_OBSTETRICA = 'ECO_OBSTETRICA', 'Ecografía Obstétrica'
    ECO_PEDIATRICA = 'ECO_PEDIATRICA', 'Ecografía Pediátrica'
    ECO_MUSCULOESQUELETICA = 'ECO_MSK', 'Ecografía Musculoesquelética'
    INTERVENCIONISMO = 'INTERV', 'Intervencionismo Ecoguiado'
    OTRO = 'OTRO', 'Otro'


class TipoLista(models.TextChoices):
    """Clasificación operativa de listas de ecografía"""
    LISTA_STAFF = 'LISTA_STAFF', 'Lista Staff'
    LISTA_DOCENTE_COMO_STAFF = 'LISTA_DOCENTE', 'Lista Docente como Staff'
    LISTA_RESIDENTE_POOL = 'LISTA_POOL', 'Lista Residente Pool'
    LISTA_ESPECIALIZADA = 'LISTA_ESPEC', 'Lista Especializada'


class TipoTitularBloque(models.TextChoices):
    """Define si el bloque es nominal o un slot genérico operativo."""
    NOMINAL = 'NOMINAL', 'Nominal (profesional fijo)'
    RESIDENTE_R1 = 'R1', 'Residente R1'
    RESIDENTE_R2 = 'R2', 'Residente R2'
    RESIDENTE_R3 = 'R3', 'Residente R3'
    RESIDENTE_R4 = 'R4', 'Residente R4'
    JEFES_RESIDENTES = 'JEFES_RES', 'Jefes de residentes'


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

    tipo_titular = models.CharField(
        max_length=20,
        choices=TipoTitularBloque.choices,
        default=TipoTitularBloque.NOMINAL,
        help_text='Nominal (profesional fijo) o slot genérico (R1-R4/Jefes).'
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

    profesional_asignado_temporal = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='bloques_horarios_asignacion_temporal',
        blank=True,
        null=True,
        help_text='Nombre asignado para el slot genérico (opcional).'
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

    tipo_lista = models.CharField(
        max_length=20,
        choices=TipoLista.choices,
        default=TipoLista.LISTA_STAFF,
        help_text="Tipo de lista operativa para este bloque"
    )

    permite_cobertura_residente = models.BooleanField(
        default=False,
        help_text="Indica si este bloque admite cobertura por residentes"
    )

    prioridad_cobertura = models.PositiveSmallIntegerField(
        default=3,
        help_text="Prioridad operativa de cobertura (1=alta, 5=baja)"
    )

    competencia_requerida = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        help_text="Competencia requerida para prestaciones especializadas"
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
            models.Index(fields=['tipo_titular', 'estado']),
        ]
    
    def __str__(self):
        profesional = self.nombre_profesional()
        dia = self.get_dia_semana_display()
        return f"{profesional} - {self.consultorio.nombre} - {dia} {self.hora_inicio}-{self.hora_fin}"
    
    def clean(self):
        """Validaciones del modelo"""
        if self.tipo_titular == TipoTitularBloque.NOMINAL:
            # Validar que haya al menos un profesional asignado
            if not self.profesional_interno and not self.profesional_externo:
                raise ValidationError(
                    "Debe especificar un profesional interno O un profesional externo para un bloque nominal."
                )

            # Validar que no haya ambos profesionales asignados
            if self.profesional_interno and self.profesional_externo:
                raise ValidationError(
                    "No puede asignar un profesional interno Y un profesional externo simultáneamente. Elija uno."
                )
        else:
            # Slot genérico: no se fija profesional nominal en el bloque.
            if self.profesional_interno or self.profesional_externo:
                raise ValidationError(
                    "En bloques genéricos no se debe completar profesional interno/externo; use 'Nombre asignado (opcional)'."
                )

            if self.profesional_asignado_temporal:
                rol_asignado = getattr(self.profesional_asignado_temporal, 'rol', None)
                if self.tipo_titular in (
                    TipoTitularBloque.RESIDENTE_R1,
                    TipoTitularBloque.RESIDENTE_R2,
                    TipoTitularBloque.RESIDENTE_R3,
                    TipoTitularBloque.RESIDENTE_R4,
                ):
                    if rol_asignado != 'medico_residente':
                        raise ValidationError(
                            "Para slots R1-R4, el nombre asignado debe tener rol medico_residente."
                        )
                if self.tipo_titular == TipoTitularBloque.JEFES_RESIDENTES:
                    if rol_asignado not in {'jefe_residentes', 'instructor_residentes'}:
                        raise ValidationError(
                            "Para slots de jefes, el nombre asignado debe tener rol jefe_residentes o instructor_residentes."
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

        # Validaciones de clasificación operativa
        if self.tipo_lista == TipoLista.LISTA_RESIDENTE_POOL and not self.permite_cobertura_residente:
            raise ValidationError(
                "Una lista de residente pool debe permitir cobertura por residentes."
            )

        if self.tipo_lista == TipoLista.LISTA_ESPECIALIZADA and not self.competencia_requerida:
            raise ValidationError(
                "Las listas especializadas deben definir una competencia requerida."
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
        if self.tipo_titular != TipoTitularBloque.NOMINAL:
            base = self.get_tipo_titular_display()
            if self.profesional_asignado_temporal:
                nombre = self.profesional_asignado_temporal.get_full_name() or self.profesional_asignado_temporal.username
                return f"{base}: {nombre}"
            return base

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


class EstadoAusenciaCobertura(models.TextChoices):
    """Estados operativos de una ausencia con propuesta/cobertura."""
    REPORTADA = 'REPORTADA', 'Reportada'
    PROPUESTA = 'PROPUESTA', 'Propuesta'
    CONFIRMADA = 'CONFIRMADA', 'Confirmada'
    CANCELADA = 'CANCELADA', 'Cancelada'


class MotivoAusencia(models.TextChoices):
    """Motivo principal informado para la ausencia."""
    ENFERMEDAD = 'ENFERMEDAD', 'Enfermedad'
    LICENCIA = 'LICENCIA', 'Licencia'
    CAPACITACION = 'CAPACITACION', 'Capacitación'
    PERSONAL = 'PERSONAL', 'Motivo Personal'
    OTRO = 'OTRO', 'Otro'


class AusenciaCobertura(models.Model):
    """
    Registra una ausencia de un bloque y su circuito de cobertura.

    Flujo esperado:
      - REPORTADA: se informa la ausencia
      - PROPUESTA: el sistema sugiere un residente
      - CONFIRMADA: cobertura asignada y aceptada
      - CANCELADA: se desestima el evento
    """

    bloque = models.ForeignKey(
        BloqueHorario,
        on_delete=models.CASCADE,
        related_name='ausencias_cobertura',
        help_text='Bloque afectado por la ausencia'
    )

    fecha_ausencia = models.DateField(
        help_text='Fecha de inicio de la ausencia (o única fecha si es un día)'
    )

    fecha_fin_ausencia = models.DateField(
        blank=True,
        null=True,
        help_text=(
            'Fecha de fin de la ausencia. Vacío = ausencia de un solo día. '
            'Si se indica, se generan registros por cada ocurrencia del día de semana del bloque dentro del rango.'
        )
    )

    profesional_ausente_interno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='ausencias_como_profesional_interno',
        blank=True,
        null=True,
        help_text='Profesional interno ausente (si aplica)'
    )

    profesional_ausente_externo = models.ForeignKey(
        ProfesionalExterno,
        on_delete=models.SET_NULL,
        related_name='ausencias_como_profesional_externo',
        blank=True,
        null=True,
        help_text='Profesional externo ausente (si aplica)'
    )

    motivo = models.CharField(
        max_length=20,
        choices=MotivoAusencia.choices,
        default=MotivoAusencia.OTRO,
        help_text='Motivo principal de la ausencia'
    )

    detalle_motivo = models.TextField(
        blank=True,
        null=True,
        help_text='Detalle adicional del motivo'
    )

    residente_sugerido = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='coberturas_sugeridas_consultorios',
        blank=True,
        null=True,
        help_text='Residente sugerido automáticamente por el sistema'
    )

    residente_asignado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='coberturas_asignadas_consultorios',
        blank=True,
        null=True,
        help_text='Residente finalmente asignado para cubrir'
    )

    estado = models.CharField(
        max_length=20,
        choices=EstadoAusenciaCobertura.choices,
        default=EstadoAusenciaCobertura.REPORTADA,
        help_text='Estado del circuito de ausencia/cobertura'
    )

    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text='Notas operativas de la coordinación'
    )

    reportado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='ausencias_reportadas_consultorios',
        blank=True,
        null=True,
        help_text='Usuario que reporta la ausencia'
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ausencia y Cobertura'
        verbose_name_plural = 'Ausencias y Coberturas'
        ordering = ['-fecha_ausencia', '-fecha_creacion']
        constraints = [
            models.UniqueConstraint(
                fields=['bloque', 'fecha_ausencia'],
                name='unique_ausencia_por_bloque_y_fecha'
            )
        ]
        indexes = [
            models.Index(fields=['fecha_ausencia', 'estado']),
            models.Index(fields=['residente_asignado', 'estado']),
        ]

    def __str__(self):
        return f"{self.bloque.consultorio.nombre} - {self.fecha_ausencia} - {self.get_estado_display()}"

    def clean(self):
        """Validaciones operativas del circuito de ausencias."""
        # Validar rango de fechas cuando se indica fecha_fin.
        if self.fecha_fin_ausencia and self.fecha_ausencia:
            if self.fecha_fin_ausencia < self.fecha_ausencia:
                raise ValidationError(
                    {'fecha_fin_ausencia': 'La fecha de fin no puede ser anterior a la fecha de inicio.'}
                )

        # Debe existir un ausente interno o externo, pero no ambos.
        if not self.profesional_ausente_interno and not self.profesional_ausente_externo:
            raise ValidationError(
                'Debe indicar el profesional ausente (interno o externo).'
            )

        if self.profesional_ausente_interno and self.profesional_ausente_externo:
            raise ValidationError(
                'No puede registrar simultáneamente ausente interno y externo.'
            )

        # Debe respetar el tipo de profesional del bloque.
        if self.bloque.profesional_interno_id and not self.profesional_ausente_interno_id:
            raise ValidationError(
                'Este bloque corresponde a un profesional interno; debe registrarlo como ausente interno.'
            )

        if self.bloque.profesional_externo_id and not self.profesional_ausente_externo_id:
            raise ValidationError(
                'Este bloque corresponde a un profesional externo; debe registrarlo como ausente externo.'
            )

        # El profesional ausente debe coincidir con el profesional asignado en el bloque.
        if self.profesional_ausente_interno and self.bloque.profesional_interno_id:
            if self.profesional_ausente_interno_id != self.bloque.profesional_interno_id:
                raise ValidationError(
                    'El profesional interno ausente no coincide con el asignado en el bloque.'
                )

        if self.profesional_ausente_externo and self.bloque.profesional_externo_id:
            if self.profesional_ausente_externo_id != self.bloque.profesional_externo_id:
                raise ValidationError(
                    'El profesional externo ausente no coincide con el asignado en el bloque.'
                )

        # Si el bloque no admite cobertura, no puede registrarse residente sugerido/asignado.
        if not self.bloque.permite_cobertura_residente:
            if self.residente_sugerido_id or self.residente_asignado_id:
                raise ValidationError(
                    'Este bloque no admite cobertura por residentes.'
                )

        # El estado CONFIRMADA requiere residente asignado.
        if self.estado == EstadoAusenciaCobertura.CONFIRMADA and not self.residente_asignado_id:
            raise ValidationError(
                'Para confirmar una cobertura debe indicar residente asignado.'
            )

        # Sugerido/asignado deben tener rol de residente.
        for campo, usuario in (
            ('residente_sugerido', self.residente_sugerido),
            ('residente_asignado', self.residente_asignado),
        ):
            if usuario and getattr(usuario, 'rol', None) != 'medico_residente':
                raise ValidationError(
                    {campo: 'El usuario debe tener rol medico_residente.'}
                )

    def nombre_profesional_ausente(self):
        """Nombre del profesional ausente para UI y auditoría."""
        if self.profesional_ausente_interno:
            return self.profesional_ausente_interno.get_full_name() or self.profesional_ausente_interno.username
        if self.profesional_ausente_externo:
            return self.profesional_ausente_externo.nombre_completo()
        return 'Sin profesional'


# ---------------------------------------------------------------------------
# Módulo operativo EGES
# ---------------------------------------------------------------------------

class AccionEGES(models.TextChoices):
    """Acción que debe realizar la administrativa en EGES."""
    HABILITAR = 'HABILITAR', 'Habilitar agenda'
    DESHABILITAR = 'DESHABILITAR', 'Deshabilitar agenda'
    REASIGNAR = 'REASIGNAR', 'Reasignar agenda a otro profesional'


class OrigenTareaEGES(models.TextChoices):
    """Evento del sistema que generó la tarea."""
    BLOQUE_NUEVO = 'BLOQUE_NUEVO', 'Bloque nuevo creado'
    BLOQUE_DESACTIVADO = 'BLOQUE_DESAC', 'Bloque desactivado/pausado'
    BLOQUE_MODIFICADO = 'BLOQUE_MOD', 'Bloque modificado (horario/profesional)'
    AUSENCIA_SIN_COBERTURA = 'AUSENCIA_SC', 'Ausencia sin cobertura'
    AUSENCIA_CON_COBERTURA = 'AUSENCIA_CC', 'Ausencia con cobertura (reasignación)'
    COBERTURA_CANCELADA = 'COB_CANCEL', 'Cobertura cancelada'
    SOLICITUD_EXTRA = 'SOLIC_EXTRA', 'Solicitud de agenda extra aprobada'
    MANUAL = 'MANUAL', 'Creada manualmente'


class EstadoTareaEGES(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente'
    EJECUTADO = 'EJECUTADO', 'Ejecutado en EGES'


class TareaAgendaEGES(models.Model):
    """
    Tarea concreta para la administrativa: qué debe hacer en EGES
    como consecuencia de un evento en este sistema.

    Ciclo de vida: PENDIENTE → EJECUTADO
    """

    accion = models.CharField(
        max_length=20,
        choices=AccionEGES.choices,
        help_text='Acción a realizar en EGES'
    )

    origen = models.CharField(
        max_length=20,
        choices=OrigenTareaEGES.choices,
        default=OrigenTareaEGES.MANUAL,
        help_text='Evento que originó esta tarea'
    )

    consultorio = models.ForeignKey(
        Consultorio,
        on_delete=models.CASCADE,
        related_name='tareas_eges',
        help_text='Consultorio afectado'
    )

    # Profesional al que refiere la tarea (puede ser interno o externo)
    profesional_interno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='tareas_eges',
        blank=True,
        null=True,
    )

    profesional_externo = models.ForeignKey(
        ProfesionalExterno,
        on_delete=models.SET_NULL,
        related_name='tareas_eges',
        blank=True,
        null=True,
    )

    # Fecha/horario afectados
    fecha_afectada = models.DateField(
        blank=True,
        null=True,
        help_text='Fecha puntual afectada (ausencias, eventos únicos)'
    )

    fecha_desde = models.DateField(
        blank=True,
        null=True,
        help_text='Inicio del rango afectado (vacaciones, cambios de bloque)'
    )

    fecha_hasta = models.DateField(
        blank=True,
        null=True,
        help_text='Fin del rango afectado'
    )

    hora_inicio = models.TimeField(
        blank=True,
        null=True,
        help_text='Franja horaria de inicio'
    )

    hora_fin = models.TimeField(
        blank=True,
        null=True,
        help_text='Franja horaria de fin'
    )

    estado = models.CharField(
        max_length=20,
        choices=EstadoTareaEGES.choices,
        default=EstadoTareaEGES.PENDIENTE,
    )

    notas = models.TextField(
        blank=True,
        null=True,
        help_text='Información adicional para la administrativa'
    )

    # Trazabilidad
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='tareas_eges_creadas',
        blank=True,
        null=True,
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    ejecutado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='tareas_eges_ejecutadas',
        blank=True,
        null=True,
        help_text='Administrativa que marcó la tarea como ejecutada'
    )

    fecha_ejecucion = models.DateTimeField(
        blank=True,
        null=True,
        help_text='Momento en que se marcó como ejecutado en EGES'
    )

    notas_ejecucion = models.TextField(
        blank=True,
        null=True,
        help_text='Notas de la administrativa al ejecutar (ej: número de agenda creada)'
    )

    class Meta:
        verbose_name = 'Tarea EGES'
        verbose_name_plural = 'Tareas EGES'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['estado', 'fecha_creacion']),
            models.Index(fields=['consultorio', 'estado']),
        ]

    def __str__(self):
        profesional = self.nombre_profesional()
        fecha = self.fecha_afectada or self.fecha_desde or '—'
        return f"[{self.get_estado_display()}] {self.get_accion_display()} — {profesional} — {self.consultorio.nombre} ({fecha})"

    def nombre_profesional(self):
        if self.profesional_interno:
            return self.profesional_interno.get_full_name() or self.profesional_interno.username
        if self.profesional_externo:
            return self.profesional_externo.nombre_completo()
        return 'Sin especificar'

    def marcar_ejecutada(self, usuario, notas=''):
        """Marca la tarea como ejecutada en EGES."""
        self.estado = EstadoTareaEGES.EJECUTADO
        self.ejecutado_por = usuario
        self.fecha_ejecucion = timezone.now()
        self.notas_ejecucion = notas
        self.save(update_fields=['estado', 'ejecutado_por', 'fecha_ejecucion', 'notas_ejecucion'])


class EstadoSolicitudExtra(models.TextChoices):
    PENDIENTE = 'PENDIENTE', 'Pendiente de aprobación'
    APROBADA = 'APROBADA', 'Aprobada'
    RECHAZADA = 'RECHAZADA', 'Rechazada'


class SolicitudAgendaExtra(models.Model):
    """
    Pedido de apertura de agenda fuera del horario habitual de un bloque.
    Ejemplo: un residente que quiere trabajar un sábado.

    Flujo:
      Residente/jefe_residentes crea solicitud (PENDIENTE)
        → jefe_servicio aprueba o rechaza
          → Si APROBADA: se genera automáticamente una TareaAgendaEGES (HABILITAR)
          → Si RECHAZADA: cierra sin más acción
    """

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='solicitudes_agenda_extra',
        help_text='Usuario que realiza la solicitud'
    )

    consultorio = models.ForeignKey(
        Consultorio,
        on_delete=models.CASCADE,
        related_name='solicitudes_agenda_extra',
    )

    # Profesional que va a trabajar ese día extra
    profesional_interno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='solicitudes_extra_como_profesional',
        blank=True,
        null=True,
    )

    profesional_externo = models.ForeignKey(
        ProfesionalExterno,
        on_delete=models.SET_NULL,
        related_name='solicitudes_extra_como_profesional',
        blank=True,
        null=True,
    )

    fecha_solicitada = models.DateField(
        help_text='Fecha en que se solicita la agenda extra'
    )

    hora_inicio = models.TimeField(
        help_text='Franja horaria de inicio'
    )

    hora_fin = models.TimeField(
        help_text='Franja horaria de fin'
    )

    tipo_actividad = models.CharField(
        max_length=20,
        choices=TipoActividad.choices,
        default=TipoActividad.ECO_GENERAL,
    )

    motivo = models.TextField(
        help_text='Motivo de la solicitud de agenda extra'
    )

    estado = models.CharField(
        max_length=20,
        choices=EstadoSolicitudExtra.choices,
        default=EstadoSolicitudExtra.PENDIENTE,
    )

    # Resolución
    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='solicitudes_extra_resueltas',
        blank=True,
        null=True,
        help_text='Jefe que aprobó o rechazó la solicitud'
    )

    fecha_resolucion = models.DateTimeField(
        blank=True,
        null=True,
    )

    observaciones_resolucion = models.TextField(
        blank=True,
        null=True,
        help_text='Motivo de rechazo u observaciones del jefe'
    )

    # Tarea EGES generada al aprobar (trazabilidad)
    tarea_eges = models.OneToOneField(
        TareaAgendaEGES,
        on_delete=models.SET_NULL,
        related_name='solicitud_origen',
        blank=True,
        null=True,
        help_text='Tarea EGES generada automáticamente al aprobar'
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Solicitud de Agenda Extra'
        verbose_name_plural = 'Solicitudes de Agenda Extra'
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['estado', 'fecha_solicitada']),
        ]

    def __str__(self):
        profesional = self.nombre_profesional()
        return f"[{self.get_estado_display()}] {profesional} — {self.consultorio.nombre} {self.fecha_solicitada} {self.hora_inicio}-{self.hora_fin}"

    def clean(self):
        if self.hora_inicio and self.hora_fin and self.hora_inicio >= self.hora_fin:
            raise ValidationError('La hora de inicio debe ser anterior a la hora de fin.')
        if self.profesional_interno and self.profesional_externo:
            raise ValidationError('Especificar un profesional: interno O externo, no ambos.')

    def nombre_profesional(self):
        if self.profesional_interno:
            return self.profesional_interno.get_full_name() or self.profesional_interno.username
        if self.profesional_externo:
            return self.profesional_externo.nombre_completo()
        return 'Sin especificar'

    def aprobar(self, jefe):
        """Aprueba la solicitud y genera la TareaAgendaEGES correspondiente."""
        if self.estado != EstadoSolicitudExtra.PENDIENTE:
            raise ValidationError('Solo se pueden aprobar solicitudes en estado PENDIENTE.')

        tarea = TareaAgendaEGES.objects.create(
            accion=AccionEGES.HABILITAR,
            origen=OrigenTareaEGES.SOLICITUD_EXTRA,
            consultorio=self.consultorio,
            profesional_interno=self.profesional_interno,
            profesional_externo=self.profesional_externo,
            fecha_afectada=self.fecha_solicitada,
            hora_inicio=self.hora_inicio,
            hora_fin=self.hora_fin,
            notas=f'Agenda extra aprobada. Motivo: {self.motivo}',
            creado_por=jefe,
        )

        self.estado = EstadoSolicitudExtra.APROBADA
        self.resuelto_por = jefe
        self.fecha_resolucion = timezone.now()
        self.tarea_eges = tarea
        self.save(update_fields=['estado', 'resuelto_por', 'fecha_resolucion', 'tarea_eges'])

    def rechazar(self, jefe, observaciones=''):
        """Rechaza la solicitud."""
        if self.estado != EstadoSolicitudExtra.PENDIENTE:
            raise ValidationError('Solo se pueden rechazar solicitudes en estado PENDIENTE.')

        self.estado = EstadoSolicitudExtra.RECHAZADA
        self.resuelto_por = jefe
        self.fecha_resolucion = timezone.now()
        self.observaciones_resolucion = observaciones
        self.save(update_fields=['estado', 'resuelto_por', 'fecha_resolucion', 'observaciones_resolucion'])
