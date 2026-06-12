from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.conf import settings
from decimal import Decimal


class GrupoTarifario(models.Model):
    """Grupo de facturación para desacoplar catálogo clínico de reglas de precio."""

    MODALIDAD_CHOICES = (
        ('ECO', 'Ecografía'),
        ('RAD', 'Radiografía'),
        ('TOM', 'Tomografía'),
        ('RES', 'Resonancia Magnética'),
        ('DOP', 'Doppler'),
        ('ECOCAR', 'Ecocardiograma'),
    )

    codigo = models.CharField(
        max_length=40,
        unique=True,
        verbose_name='Código',
        help_text='Ej: TC_SIMPLE, TC_CONTRASTE, DOPPLER_CARDIACO_LECHO',
    )
    nombre = models.CharField(max_length=150, verbose_name='Nombre')
    modalidad = models.CharField(
        max_length=6,
        choices=MODALIDAD_CHOICES,
        verbose_name='Modalidad',
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Grupo Tarifario'
        verbose_name_plural = 'Grupos Tarifarios'
        ordering = ['modalidad', 'codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def get_tarifa_vigente(self, fecha=None):
        """Retorna la tarifa vigente para la fecha indicada (hoy por defecto)."""
        fecha_ref = fecha or timezone.now().date()
        return self.tarifas.filter(
            vigencia_desde__lte=fecha_ref,
        ).filter(
            models.Q(vigencia_hasta__isnull=True) | models.Q(vigencia_hasta__gte=fecha_ref)
        ).order_by('-vigencia_desde').first()

class Estudios(models.Model):
    """
    Catálogo de estudios/prácticas médicas con sus precios
    Actualizado v2.0 - Febrero 2026
    """
    # Identificación
    codigo = models.CharField(
        max_length=10,
        unique=True,
        verbose_name='Código',
        help_text='Ej: 902225, 901244',
        blank=True,
        null=True
    )
    nombre = models.CharField(
        max_length=150,
        unique=True,
        verbose_name='Nombre del estudio'
    )
    
    TIPO_ESTUDIO_CHOICES = (
        ('ECO', 'Ecografía'),
        ('RAD', 'Radiografía'),
        ('TOM', 'Tomografía'),
        ('RES', 'Resonancia Magnética'),
        ('DOP', 'Doppler'),
        ('MAM', 'Mamografía'),
        ('ECOCAR', 'Ecocardiograma'),
    )
    tipo = models.CharField(
        max_length=6,
        choices=TIPO_ESTUDIO_CHOICES,
        default='ECO',
        verbose_name='Tipo de estudio'
    )
    grupo_tarifario = models.ForeignKey(
        'GrupoTarifario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='estudios',
        verbose_name='Grupo tarifario',
        help_text='Grupo de facturación para cálculo por tarifas vigentes',
    )
    
    conteo_regiones = models.IntegerField(
        verbose_name='Cantidad de regiones',
        help_text='Cantidad de regiones estándar para este estudio'
    )
    conteo_regiones_default = models.PositiveIntegerField(
        default=1,
        verbose_name='Regiones (default en formulario)',
        help_text='Valor por defecto que aparece en el formulario'
    )
    
    # NUEVO v2.0: Sistema de precios
    precio_unico = models.BooleanField(
        default=False,
        verbose_name='Precio Único',
        help_text='Si True, precio_cober = precio_otras_os. Ej: TAC, RMN, RX'
    )
    precio_cober = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Precio COBER',
        help_text='Precio para obra social COBER'
    )
    precio_otras_os = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name='Precio OTRAS OS',
        help_text='Precio para otras obras sociales'
    )
    
    # Auditoría de precios
    activo = models.BooleanField(
        default=True,
        verbose_name='Estudio Activo',
        help_text='Desmarcar para ocultar en formularios'
    )
    tiene_contexto_ubicacion = models.BooleanField(
        default=False,
        verbose_name='Requiere contexto de ubicación',
        help_text='Si True, el médico puede indicar si el estudio fue en Servicio, Lecho o Quirófano (ej: Doppler, ETE)',
    )
    fecha_actualizacion_precios = models.DateField(
        auto_now=True,
        verbose_name='Última actualización de precios'
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='estudios_actualizados',
        verbose_name='Actualizado por'
    )

    class Meta:
        verbose_name = 'Estudio'
        verbose_name_plural = 'Estudios'
        ordering = ['tipo', 'nombre']

    def __str__(self):
        if self.codigo:
            return f'{self.codigo} - {self.nombre}'
        return f'{self.nombre}'
    
    def _precio_legado_para_os(self, tipo_os):
        """Retorna el precio histórico almacenado en el propio estudio."""
        if self.precio_unico:
            return self.precio_cober
        return self.precio_cober if tipo_os == 'COBER' else self.precio_otras_os

    def precio_para_os(self, tipo_os, fecha=None, contexto='SERVICIO'):
        """Retorna el precio vigente por OS priorizando la tarifa del grupo.

        Si el estudio tiene contexto de ubicación (lecho/quirófano), intenta
        resolver contra un grupo variante ({codigo}_LECHO o {codigo}_QUIROFANO)
        antes de caer al grupo base.
        """
        tipo_os_normalizado = (tipo_os or '').upper()
        fecha_ref = fecha or timezone.now().date()
        contexto_norm = (contexto or 'SERVICIO').upper()

        if self.grupo_tarifario_id:
            # Intentar grupo contextual si el estudio lo soporta y el contexto no es el default
            if self.tiene_contexto_ubicacion and contexto_norm != 'SERVICIO':
                codigo_variante = f"{self.grupo_tarifario.codigo}_{contexto_norm}"
                grupo_variante = GrupoTarifario.objects.filter(codigo=codigo_variante).first()
                if grupo_variante:
                    tarifa_variante = grupo_variante.get_tarifa_vigente(fecha=fecha_ref)
                    if tarifa_variante:
                        return tarifa_variante.precio_cober if tipo_os_normalizado == 'COBER' else tarifa_variante.precio_otras_os

            # Grupo base (contexto SERVICIO o fallback)
            tarifa_vigente = self.grupo_tarifario.get_tarifa_vigente(fecha=fecha_ref)
            if tarifa_vigente:
                return tarifa_vigente.precio_cober if tipo_os_normalizado == 'COBER' else tarifa_vigente.precio_otras_os

        return self._precio_legado_para_os(tipo_os_normalizado)
    
    def actualizar_precios(self, nuevo_precio_cober, nuevo_precio_otras_os, usuario, motivo=''):
        """
        Actualiza los precios y guarda en historial
        """
        from .models import HistorialPrecioEstudio  # Import local para evitar circular
        
        # Guardar en historial antes de actualizar
        HistorialPrecioEstudio.objects.create(
            estudio=self,
            precio_cober_anterior=self.precio_cober,
            precio_otras_os_anterior=self.precio_otras_os,
            precio_cober_nuevo=nuevo_precio_cober,
            precio_otras_os_nuevo=nuevo_precio_otras_os,
            actualizado_por=usuario,
            motivo_actualizacion=motivo or 'Actualización de precios'
        )
        
        # Actualizar precios
        self.precio_cober = nuevo_precio_cober
        self.precio_otras_os = nuevo_precio_otras_os
        self.actualizado_por = usuario
        self.save()


class HistorialPrecioEstudio(models.Model):
    """
    Historial de cambios de precios de estudios
    Permite auditar cuándo y quién cambió los precios
    """
    estudio = models.ForeignKey(
        'Estudios',
        on_delete=models.CASCADE,
        related_name='historial_precios',
        verbose_name='Estudio'
    )
    
    # Precios anteriores
    precio_cober_anterior = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Precio COBER Anterior'
    )
    precio_otras_os_anterior = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Precio OTRAS OS Anterior'
    )
    
    # Precios nuevos
    precio_cober_nuevo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Precio COBER Nuevo'
    )
    precio_otras_os_nuevo = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Precio OTRAS OS Nuevo'
    )
    
    # Auditoría
    fecha_actualizacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Actualización'
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Actualizado por'
    )
    motivo_actualizacion = models.TextField(
        blank=True,
        verbose_name='Motivo',
        help_text='Ej: Negociación anual, Ajuste por inflación, etc.'
    )
    
    class Meta:
        verbose_name = 'Historial de Precio'
        verbose_name_plural = 'Historial de Precios'
        ordering = ['-fecha_actualizacion']
        indexes = [
            models.Index(fields=['estudio', '-fecha_actualizacion']),
        ]
    
    def __str__(self):
        return f"{self.estudio.nombre} - {self.fecha_actualizacion.strftime('%d/%m/%Y')}"
    
    def get_variacion_cober(self):
        """Calcula porcentaje de variación COBER"""
        if self.precio_cober_anterior is None or self.precio_cober_nuevo is None:
            return 0
        if self.precio_cober_anterior == 0:
            return 0
        variacion = ((self.precio_cober_nuevo - self.precio_cober_anterior) / self.precio_cober_anterior) * 100
        return round(variacion, 2)
    
    def get_variacion_otras_os(self):
        """Calcula porcentaje de variación OTRAS OS"""
        if self.precio_otras_os_anterior is None or self.precio_otras_os_nuevo is None:
            return 0
        if self.precio_otras_os_anterior == 0:
            return 0
        variacion = ((self.precio_otras_os_nuevo - self.precio_otras_os_anterior) / self.precio_otras_os_anterior) * 100
        return round(variacion, 2)


class TarifaGrupoTarifario(models.Model):
    """Tarifa versionada por grupo con vigencia temporal."""

    grupo_tarifario = models.ForeignKey(
        'GrupoTarifario',
        on_delete=models.CASCADE,
        related_name='tarifas',
        verbose_name='Grupo tarifario',
    )
    vigencia_desde = models.DateField(verbose_name='Vigencia desde')
    vigencia_hasta = models.DateField(null=True, blank=True, verbose_name='Vigencia hasta')
    precio_cober = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio COBER')
    precio_otras_os = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio OTRAS OS')
    motivo_actualizacion = models.TextField(blank=True, verbose_name='Motivo de actualización')
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tarifas_grupo_actualizadas',
        verbose_name='Actualizado por',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tarifa de Grupo Tarifario'
        verbose_name_plural = 'Tarifas de Grupos Tarifarios'
        ordering = ['grupo_tarifario', '-vigencia_desde']
        constraints = [
            models.UniqueConstraint(
                fields=['grupo_tarifario', 'vigencia_desde'],
                name='uq_tarifa_grupo_vigencia_desde',
            ),
        ]
        indexes = [
            models.Index(fields=['grupo_tarifario', 'vigencia_desde']),
            models.Index(fields=['vigencia_desde', 'vigencia_hasta']),
        ]

    def __str__(self):
        return f"{self.grupo_tarifario.codigo} desde {self.vigencia_desde}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.vigencia_hasta and self.vigencia_hasta < self.vigencia_desde:
            raise ValidationError('La vigencia hasta no puede ser anterior a vigencia desde.')


class SesionContable(models.Model):
    """
    Período de facturación mensual
    Agrupa todas las prácticas registradas en un mes
    """
    mes = models.PositiveIntegerField(
        verbose_name='Mes',
        help_text='1-12'
    )
    año = models.PositiveIntegerField(
        verbose_name='Año',
        help_text='2020-2050'
    )
    
    ESTADO_CHOICES = [
        ('ABIERTA', 'Abierta - Médicos pueden registrar'),
        ('REVISION', 'En Revisión - Cierre preliminar'),
        ('CERRADA', 'Cerrada - Solo Admin puede cargar faltantes'),
        ('FACTURADA', 'Facturada - Montos calculados y definitivos'),
        ('PAGADA', 'Pagada - Profesionales cobraron'),
    ]
    estado = models.CharField(
        max_length=10,
        choices=ESTADO_CHOICES,
        default='ABIERTA'
    )
    
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    fecha_facturacion = models.DateTimeField(null=True, blank=True)
    fecha_pago = models.DateTimeField(null=True, blank=True)
    
    cerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sesiones_cerradas',
        verbose_name='Cerrada por'
    )
    
    observaciones = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('mes', 'año')
        verbose_name = 'Sesión Contable'
        verbose_name_plural = 'Sesiones Contables'
        ordering = ['-año', '-mes']
    
    def __str__(self):
        meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        mes_nombre = meses[self.mes] if 1 <= self.mes <= 12 else str(self.mes)
        return f"{mes_nombre} {self.año} ({self.get_estado_display()})"
    
    def puede_registrar_practicas(self, usuario):
        """Verifica si se pueden registrar prácticas en esta sesión"""
        # Medicos solo en ABIERTA o REVISION
        if usuario.rol in ['jefe_residentes', 'instructor_residentes', 'medico_residente', 'medico_staff', 'cardiologo', 'jefe_servicio']:
            return self.estado in ['ABIERTA', 'REVISION']
        
        # Admin puede cargar incluso en CERRADA
        if usuario.is_superuser or usuario.rol == 'administrativo':
            return self.estado != 'PAGADA'  # Solo bloquear después de pagar
        
        return False


class HistorialSesionContable(models.Model):
    """Historial de transiciones de estado de una sesión contable."""

    ORIGEN_WEB = 'WEB'
    ORIGEN_ADMIN = 'ADMIN'
    ORIGEN_CHOICES = [
        (ORIGEN_WEB, 'Portal Web'),
        (ORIGEN_ADMIN, 'Django Admin'),
    ]

    sesion_contable = models.ForeignKey(
        'SesionContable',
        on_delete=models.CASCADE,
        related_name='historial_transiciones',
        verbose_name='Sesión Contable',
    )
    estado_anterior = models.CharField(
        max_length=10,
        choices=SesionContable.ESTADO_CHOICES,
        verbose_name='Estado anterior',
    )
    estado_nuevo = models.CharField(
        max_length=10,
        choices=SesionContable.ESTADO_CHOICES,
        verbose_name='Estado nuevo',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_sesiones_contables',
        verbose_name='Usuario',
    )
    fecha = models.DateTimeField(auto_now_add=True, verbose_name='Fecha')
    motivo = models.TextField(blank=True, verbose_name='Motivo')
    origen = models.CharField(
        max_length=10,
        choices=ORIGEN_CHOICES,
        default=ORIGEN_WEB,
        verbose_name='Origen',
    )
    observacion_sistema = models.TextField(blank=True, verbose_name='Observación sistema')

    class Meta:
        verbose_name = 'Historial de Sesión Contable'
        verbose_name_plural = 'Historiales de Sesión Contable'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['sesion_contable', '-fecha']),
            models.Index(fields=['origen', '-fecha']),
        ]

    def __str__(self):
        return (
            f"{self.sesion_contable} | {self.estado_anterior} -> {self.estado_nuevo} "
            f"({self.origen})"
        )


class ConfiguracionGuardiaPasiva(models.Model):
    """Configuración vigente del valor de la guardia pasiva."""

    monto_vigente = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Monto vigente',
        help_text='Valor actual definido por administración para nuevas guardias.',
    )
    vigente_desde = models.DateField(
        verbose_name='Vigente desde',
        help_text='Fecha desde la cual rige este valor.',
    )
    motivo_actualizacion = models.TextField(
        blank=True,
        verbose_name='Motivo de actualización',
        help_text='Detalle del cambio para trazabilidad.',
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='configuraciones_guardia_pasiva_actualizadas',
        verbose_name='Actualizado por',
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de Guardia Pasiva'
        verbose_name_plural = 'Configuración de Guardia Pasiva'
        ordering = ['-fecha_actualizacion']

    def __str__(self):
        return f'Guardia pasiva: {self.monto_vigente} desde {self.vigente_desde}'

    def clean(self):
        if self.monto_vigente is not None and self.monto_vigente < 0:
            raise ValidationError('El monto vigente no puede ser negativo.')

    def save(self, *args, **kwargs):
        if self.pk:
            anterior = ConfiguracionGuardiaPasiva.objects.filter(pk=self.pk).first()
            if anterior and (
                anterior.monto_vigente != self.monto_vigente
                or anterior.vigente_desde != self.vigente_desde
                or anterior.motivo_actualizacion != self.motivo_actualizacion
            ):
                HistorialConfiguracionGuardiaPasiva.objects.create(
                    configuracion=self,
                    monto_anterior=anterior.monto_vigente,
                    monto_nuevo=self.monto_vigente,
                    vigente_desde_anterior=anterior.vigente_desde,
                    vigente_desde_nueva=self.vigente_desde,
                    motivo_actualizacion=self.motivo_actualizacion,
                    actualizado_por=self.actualizado_por,
                )
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        """Retorna la configuración vigente, creando una por defecto si no existe."""
        config = cls.objects.first()
        if config:
            return config

        return cls.objects.create(
            monto_vigente=Decimal('36500.00'),
            vigente_desde=timezone.now().date(),
            motivo_actualizacion='Valor inicial por defecto',
        )


class HistorialConfiguracionGuardiaPasiva(models.Model):
    """Historial de cambios del valor de guardia pasiva."""

    configuracion = models.ForeignKey(
        ConfiguracionGuardiaPasiva,
        on_delete=models.CASCADE,
        related_name='historial_cambios',
        verbose_name='Configuración',
    )
    monto_anterior = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto anterior')
    monto_nuevo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monto nuevo')
    vigente_desde_anterior = models.DateField(verbose_name='Vigente desde anterior')
    vigente_desde_nueva = models.DateField(verbose_name='Vigente desde nueva')
    motivo_actualizacion = models.TextField(blank=True, verbose_name='Motivo de actualización')
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_configuraciones_guardia_pasiva',
        verbose_name='Actualizado por',
    )
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Historial de configuración de Guardia Pasiva'
        verbose_name_plural = 'Historial de configuración de Guardia Pasiva'
        ordering = ['-fecha_cambio']

    def __str__(self):
        return f'{self.configuracion_id} - {self.monto_anterior} -> {self.monto_nuevo}'


class GuardiaPasiva(models.Model):
    """
    Registro de guardias pasivas
    Se registra por DÍA completo, no por práctica individual
    El monto se fija al crear el registro desde la configuración vigente.
    """
    sesion_contable = models.ForeignKey(
        'SesionContable',
        on_delete=models.PROTECT,
        related_name='guardias_pasivas',
        verbose_name='Sesión Contable'
    )
    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Médico'
    )
    fecha_guardia = models.DateField(
        verbose_name='Fecha de Guardia',
        help_text='Día que el médico estuvo de guardia pasiva'
    )
    
    TIPO_GUARDIA_CHOICES = [
        ('COBER', 'COBER'),
        ('OTRAS_OS', 'Otras Obras Sociales'),
    ]
    tipo_guardia = models.CharField(
        max_length=10,
        choices=TIPO_GUARDIA_CHOICES,
        default='COBER',
        verbose_name='Tipo de Guardia'
    )
    
    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('36500.00'),
        verbose_name='Monto por Día',
        help_text='Valor histórico guardado por guardia; se fija desde la configuración vigente.'
    )
    
    observaciones = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('medico', 'fecha_guardia')
        ordering = ['-fecha_guardia']
        verbose_name = 'Guardia Pasiva'
        verbose_name_plural = 'Guardias Pasivas'
        indexes = [
            models.Index(fields=['sesion_contable', 'medico']),
        ]
    
    def __str__(self):
        return f"{self.medico.get_full_name()} - Guardia {self.fecha_guardia.strftime('%d/%m/%Y')}"
    
    def save(self, *args, **kwargs):
        # Auto-asignar sesión contable
        if not self.sesion_contable_id:
            mes = self.fecha_guardia.month
            año = self.fecha_guardia.year
            sesion, created = SesionContable.objects.get_or_create(
                mes=mes, año=año,
                defaults={'estado': 'ABIERTA'}
            )
            self.sesion_contable = sesion

        if not self.pk:
            self.monto = ConfiguracionGuardiaPasiva.get_config().monto_vigente
        
        super().save(*args, **kwargs)


class RegistroEstudio(models.Model):
    """
    Tabla intermedia para la relación M2M entre Registro y Estudios.
    Permite almacenar la CANTIDAD de cada estudio realizado.
    
    Ejemplo:
    - RM RODILLA × 2 (bilateral)
    - ECO ABDOMINAL × 1
    
    v3.1 - Marzo 2026: Migración de M2M simple a M2M through
    """
    registro = models.ForeignKey(
        'RegistroEstudiosPorMedico',
        on_delete=models.CASCADE,
        verbose_name='Registro'
    )
    estudio = models.ForeignKey(
        'Estudios',
        on_delete=models.PROTECT,
        verbose_name='Estudio'
    )
    cantidad = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Cantidad',
        help_text='Número de veces que se realizó este estudio (ej: 2 para bilateral)'
    )
    
    CONTEXTO_CHOICES = [
        ('SERVICIO', 'Consultorio / Servicio'),
        ('LECHO',    'En Lecho'),
        ('QUIROFANO', 'Quirófano'),
    ]
    contexto = models.CharField(
        max_length=10,
        choices=CONTEXTO_CHOICES,
        default='SERVICIO',
        verbose_name='Contexto de ubicación',
        help_text='Indica si el estudio fue en Servicio (consultorio), en Lecho (cama del paciente) o en Quirófano',
    )

    # Metadata
    fecha_agregado = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de agregado'
    )
    
    class Meta:
        db_table = 'liquidacion_registro_estudio'
        verbose_name = 'Estudio por Registro'
        verbose_name_plural = 'Estudios por Registro'
        unique_together = [['registro', 'estudio']]  # Un estudio no se puede repetir en el mismo registro
        ordering = ['fecha_agregado']
    
    def __str__(self):
        return f"{self.estudio.nombre} (×{self.cantidad})"


class RegistroEstudiosPorMedico(models.Model):
    """
    Registro individual de una práctica médica realizada
    ACTUALIZADO v3.1 - Marzo 2026
    Usa tabla intermedia RegistroEstudio para guardar cantidades de cada estudio
    """
    # Relaciones
    sesion_contable = models.ForeignKey(
        'SesionContable',
        on_delete=models.PROTECT,
        related_name='practicas',
        verbose_name='Sesión Contable',
        null=True,  # Permitir null temporalmente para migración
        blank=True
    )
    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Médico'
    )
    
    # Datos del paciente
    nombre_paciente = models.CharField(max_length=50, verbose_name='Nombre del paciente')
    apellido_paciente = models.CharField(max_length=50, verbose_name='Apellido del paciente')
    dni_paciente = models.CharField(max_length=20, verbose_name='DNI del paciente')
    
    # Fechas
    fecha_registro = models.DateTimeField(default=timezone.now, verbose_name='Fecha de registro')
    fecha_del_informe = models.DateField(verbose_name='Fecha del informe')
    
    # Estudios realizados (puede ser más de uno por paciente)
    # v3.1 - Marzo 2026: Usa tabla intermedia RegistroEstudio para persistir cantidades
    estudio = models.ManyToManyField(
        Estudios,
        through='RegistroEstudio',
        verbose_name='Estudios',
        related_name='registros',
        help_text='Selecciona todos los estudios realizados a este paciente'
    )
    
    # NUEVOS CAMPOS v2.0
    # Dimensiones de facturación
    cantidad_regiones = models.PositiveIntegerField(
        default=1,
        verbose_name='Cantidad de Regiones',
        help_text='Se calcula automáticamente sumando las regiones de todos los estudios seleccionados'
    )
    
    TIPO_OS_CHOICES = [
        ('COBER', 'COBER'),
        ('OTRAS_OS', 'Otras Obras Sociales'),
    ]
    tipo_obra_social = models.CharField(
        max_length=10,
        choices=TIPO_OS_CHOICES,
        default='OTRAS_OS',
        verbose_name='Tipo de Obra Social',
        blank=True
    )
    
    HORARIO_CHOICES = [
        ('INTRA', 'Intra Residencia (50%)'),
        ('EXTRA', 'Extra Residencia (100%)'),
        ('NA', 'No Aplica (Staff)'),
    ]
    horario = models.CharField(
        max_length=6,
        choices=HORARIO_CHOICES,
        default='NA',
        verbose_name='Horario',
        blank=True
    )
    
    # Monto calculado (INMUTABLE - se guarda al crear/editar)
    monto_calculado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Monto Calculado',
        help_text='Se calcula automáticamente al guardar'
    )
    
    # Para bonus urgencia (RM a distancia con pacientes internados)
    paciente_internado = models.BooleanField(
        default=False,
        verbose_name='Paciente Internado',
        help_text='Marca si el paciente estaba internado al momento del estudio'
    )
    fecha_hora_solicitud = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha/Hora Solicitud',
        help_text='Cuándo se solicitó el estudio (para calcular urgencia)'
    )
    fecha_hora_informe = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha/Hora Informe',
        help_text='Cuándo se entregó el informe (para calcular urgencia)'
    )
    
    # Auditoría
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='practicas_modificadas',
        verbose_name='Modificado por'
    )
    fecha_modificacion = models.DateTimeField(null=True, blank=True)
    motivo_modificacion = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Registro de estudio por médico'
        verbose_name_plural = 'Registros de estudios por médico'
        ordering = ['-fecha_del_informe', '-fecha_registro']
        indexes = [
            models.Index(fields=['sesion_contable', 'medico']),
            models.Index(fields=['fecha_del_informe']),
        ]

    def __str__(self):
        return f'{self.medico} - {self.fecha_registro}'
    
    def calcular_monto(self):
        """
        Calcula el monto a facturar por esta práctica.
        v3.2 - Mayo 2026: Factor INTRA diferenciado por rol y tipo de estudio.
        v3.3 - Mayo 2026: INTRA aplica solo a ECO general real.

        Reglas de factor horario INTRA (50%):
          - medico_residente / jefe_residentes / instructor_residentes:
            aplica SOLO a ECO general real.
            Doppler (DOP), ECOCAR y otros siempre al 100%.
          - staff / otros roles: sin descuento horario, siempre 100%.
        """
        from .grupo_tarifario_mapping import es_eco_general_real_estudio

        # Si no hay estudios asignados, retornar 0
        relaciones = self.registroestudio_set.select_related('estudio__grupo_tarifario').all()
        if not relaciones.exists():
            return Decimal('0.00')

        fecha_referencia = self.fecha_del_informe or timezone.now().date()
        
        # 1. Sumar (precio × cantidad) separando ECO general real del resto.
        precio_total = Decimal('0.00')
        precio_total_eco_general = Decimal('0.00')
        precio_total_resto = Decimal('0.00')
        
        for rel in relaciones:
            estudio = rel.estudio
            cantidad = rel.cantidad

            precio_estudio = estudio.precio_para_os(
                self.tipo_obra_social,
                fecha=fecha_referencia,
                contexto=rel.contexto,
            )
            precio_rel = precio_estudio * Decimal(str(cantidad))
            precio_total += precio_rel
            if es_eco_general_real_estudio(estudio):
                precio_total_eco_general += precio_rel
            else:
                precio_total_resto += precio_rel
        
        if precio_total == Decimal('0.00'):
            return Decimal('0.00')
        
        # 2. Aplicar factor horario según rol
        subtotal = precio_total
        if self.horario == 'INTRA':
            if self.medico.rol in ['medico_residente', 'jefe_residentes', 'instructor_residentes']:
                # Residencia: INTRA solo aplica a ECO general real.
                subtotal = (precio_total_eco_general * Decimal('0.5')) + precio_total_resto
            # EXTRA para cualquier rol: sin cambio (100%)
        # Staff / otros roles: sin factor horario (100%)
        
        # 3. Bonus urgencia para RM con pacientes internados (solo remotos)
        bonus_urgencia = self.calcular_bonus_urgencia()
        monto_final = subtotal * (Decimal('1.0') + bonus_urgencia)
        
        return monto_final
    
    def calcular_bonus_urgencia(self):
        """
        Calcula el bonus de urgencia para RM a distancia
        +20% si paciente internado e informe en < 24 horas
        SOLO para médicos que trabajan remoto
        """
        # Solo si el médico trabaja remoto
        if not self.medico.trabaja_remoto:
            return Decimal('0.0')
        
        # Solo aplica si hay al menos un estudio de Resonancia Magnética
        estudios_lista = self.estudio.all()
        hay_resonancia = any(est.tipo == 'RES' for est in estudios_lista)
        if not hay_resonancia:
            return Decimal('0.0')
        
        # Solo si paciente estaba internado
        if not self.paciente_internado:
            return Decimal('0.0')
        
        # Solo si tenemos ambas fechas
        if not self.fecha_hora_solicitud or not self.fecha_hora_informe:
            return Decimal('0.0')
        
        # Calcular diferencia en horas
        delta = self.fecha_hora_informe - self.fecha_hora_solicitud
        horas = delta.total_seconds() / 3600
        
        # Si informó en menos de 24 horas → +20%
        if horas < 24:
            return Decimal('0.20')  # 20%
        
        return Decimal('0.0')
    
    def get_desglose_monto(self):
        """
        Retorna un diccionario con el desglose del cálculo
        v3.1 - Marzo 2026: Incluye cantidades desde tabla intermedia
        """
        relaciones = self.registroestudio_set.select_related('estudio').all()
        if not relaciones.exists():
            return {}
        
        # Calcular precio total de todos los estudios con cantidades
        precio_total = Decimal('0.00')
        estudios_nombres = []
        for rel in relaciones:
            estudio = rel.estudio
            cantidad = rel.cantidad

            precio_estudio = estudio.precio_para_os(
                self.tipo_obra_social,
                fecha=self.fecha_del_informe or timezone.now().date(),
                contexto=rel.contexto,
            )
            precio_total += (precio_estudio * Decimal(str(cantidad)))

            # Agregar nombre con cantidad y contexto si aplica
            label = estudio.nombre
            if rel.contexto and rel.contexto != 'SERVICIO':
                label += f' [{rel.get_contexto_display()}]'
            if cantidad > 1:
                label += f' ×{cantidad}'
            estudios_nombres.append(label)
        
        # Porcentaje según horario
        porcentaje = 0.5 if self.horario == 'INTRA' else 1.0
        subtotal = precio_total * Decimal(str(porcentaje))
        bonus_urgencia = self.calcular_bonus_urgencia()
        
        desglose = {
            'estudios': ", ".join(estudios_nombres),
            'cantidad_estudios': relaciones.count(),
            'precio_total': precio_total,
            'regiones': self.cantidad_regiones,
            'tipo_os': self.get_tipo_obra_social_display(),
            'horario': self.get_horario_display(),
            'porcentaje': f"{int(porcentaje * 100)}%",
            'monto_final': self.monto_calculado,
        }

        # Exponer ecuacion base desde backend para UI (ej: 6500 x 2 = 13000)
        regiones = self.cantidad_regiones or 0
        if regiones > 0:
            valor_base_unitario = precio_total / Decimal(str(regiones))
            desglose['valor_base_unitario'] = valor_base_unitario
            desglose['mostrar_formula_base'] = regiones > 1
        
        # Agregar info de urgencia si aplica
        if bonus_urgencia > 0:
            desglose['bonus_urgencia'] = f"+{int(bonus_urgencia * 100)}%"
            desglose['paciente_internado'] = True
            if self.fecha_hora_solicitud and self.fecha_hora_informe:
                delta = self.fecha_hora_informe - self.fecha_hora_solicitud
                horas = delta.total_seconds() / 3600
                desglose['tiempo_respuesta'] = f"{horas:.1f} horas"
        
        return desglose
    
    def get_desglose_monto_simple(self):
        """
        Desglose simplificado para usuarios médicos/residentes (v3.2 - Mayo 2026).
        
        Solo retorna información operacional sin detalles administrativos:
        - Estudios realizados
        - Cantidad de regiones
        - Monto final guardado
        
        Sin mostrar: grupo tarifario, tarifa vigente, vigencia, precio base.
        
        Returns:
            dict: Información básica del cálculo
        """
        relaciones = self.registroestudio_set.select_related('estudio').all()
        if not relaciones.exists():
            return {}
        
        # Listar estudios con cantidad y contexto
        estudios_nombres = []
        for rel in relaciones:
            estudio = rel.estudio
            cantidad = rel.cantidad
            label = estudio.nombre
            if rel.contexto and rel.contexto != 'SERVICIO':
                label += f' [{rel.get_contexto_display()}]'
            if cantidad > 1:
                label += f' ×{cantidad}'
            estudios_nombres.append(label)
        
        return {
            'estudios': ", ".join(estudios_nombres),
            'regiones': self.cantidad_regiones,
            'monto_final': self.monto_calculado,
            'tipo_os': self.get_tipo_obra_social_display(),
        }
    
    def get_desglose_monto_administrativo(self):
        """
        Desglose completo para roles administrativos/contables (v3.2 - Mayo 2026).
        
        Retorna información operacional + administrativa:
        - Estudios, regiones, monto (igual a `get_desglose_monto_simple()`)
        - Grupo tarifario y tarifa vigente aplicados
        - Vigencia de la tarifa (desde/hasta)
        - Precios de la tarifa (COBER, OTRAS_OS)
        - Alertas: si fecha_del_informe cae fuera de vigencia
        
        Este método extiende `get_desglose_monto()` con información administrativa.
        
        Returns:
            dict: Información completa incluyendo tarifas y vigencia
        """
        # Obtener desglose base (operacional)
        desglose = self.get_desglose_monto()
        
        # Agregar información administrativa de tarifas
        relaciones = self.registroestudio_set.select_related(
            'estudio',
            'estudio__grupo_tarifario'
        ).all()
        
        if relaciones.exists():
            # Usar el primer estudio para obtener grupo (asumiendo todos del mismo grupo para el registro)
            # En futuro, si hay registros multi-grupo, se puede expandir este lógica
            primer_estudio = relaciones.first().estudio
            
            if primer_estudio.grupo_tarifario:
                grupo = primer_estudio.grupo_tarifario
                tarifa_vigente = grupo.get_tarifa_vigente(
                    fecha=self.fecha_del_informe or timezone.now().date()
                )
                
                # Información del grupo
                desglose['grupo_tarifario_codigo'] = grupo.codigo
                desglose['grupo_tarifario_nombre'] = grupo.nombre
                
                # Información de la tarifa vigente
                if tarifa_vigente:
                    desglose['tarifa_vigencia_desde'] = tarifa_vigente.vigencia_desde
                    desglose['tarifa_vigencia_hasta'] = tarifa_vigente.vigencia_hasta
                    desglose['tarifa_precio_cober'] = tarifa_vigente.precio_cober
                    desglose['tarifa_precio_otras_os'] = tarifa_vigente.precio_otras_os
                    
                    # Alerta si la fecha del informe es anterior a la tarifa vigente más reciente
                    if self.fecha_del_informe and self.fecha_del_informe < tarifa_vigente.vigencia_desde:
                        desglose['alerta_fecha_anterior_tarifa'] = True
                        desglose['alerta_mensaje'] = (
                            f"⚠️ Fecha del informe ({self.fecha_del_informe.strftime('%d/%m/%Y')}) "
                            f"es anterior a la vigencia de la tarifa ({tarifa_vigente.vigencia_desde.strftime('%d/%m/%Y')}). "
                            f"Monto calculado con tarifa vigente en esa fecha."
                        )
        
        return desglose
    
    def puede_editar(self, usuario):
        """
        Verifica si el usuario puede editar esta práctica
        """
        # Admin siempre puede
        if usuario.is_superuser or usuario.rol == 'administrativo':
            return True
        
        # Médico solo puede editar sus propias prácticas
        if self.medico == usuario:
            # Solo si la sesión está abierta o en revisión
            if self.sesion_contable:
                return self.sesion_contable.puede_registrar_practicas(usuario)
            return True  # Si no tiene sesión asignada aún, puede editar
        
        return False
    
    def save(self, *args, **kwargs):
        # Validación: Asignar sesión contable automáticamente
        if not self.sesion_contable_id:
            mes = self.fecha_del_informe.month
            año = self.fecha_del_informe.year
            sesion, created = SesionContable.objects.get_or_create(
                mes=mes, año=año,
                defaults={'estado': 'ABIERTA'}
            )
            self.sesion_contable = sesion
        
        # Fallback conservador legacy: solo aplica si no hay horario definido.
        # La fuente canónica para residencia+ECO vive en flujo post-M2M (services.py).
        if not self.horario or self.horario == '':
            if self.medico.rol in ['medico_staff', 'jefe_servicio', 'cardiologo']:
                # Staff no tiene horario INTRA/EXTRA
                self.horario = 'NA'
            else:
                # Sin M2M aún no inferimos ECO/no ECO; usamos proxy por fecha_registro.
                from django.utils import timezone
                referencia = self.fecha_registro or timezone.now()
                hora_actual = timezone.localtime(referencia).hour
                
                # 8:00 a 16:59 → INTRA (17:00 ya es EXTRA)
                if 8 <= hora_actual < 17:
                    self.horario = 'INTRA'
                else:
                    self.horario = 'EXTRA'
        
        # NOTA v3.1: No se puede calcular monto aquí porque usa tabla intermedia RegistroEstudio
        # Los RegistroEstudio se crean DESPUÉS del save() principal (necesita ID)
        # El cálculo de monto se hace en form_valid() de las vistas después de crear RegistroEstudio
        # Secuencia: save() → crear RegistroEstudio → calcular_monto() → save(update_fields)
        
        super().save(*args, **kwargs)


class SolicitudRevisionHorarioRegistro(models.Model):
    """Solicitud médica de revisión de horario para un registro ya cargado.

    Fase A: solo crea solicitud pendiente. No modifica horario ni monto.
    """

    ESTADO_PENDIENTE = 'PENDIENTE'
    ESTADO_APROBADA = 'APROBADA'
    ESTADO_RECHAZADA = 'RECHAZADA'
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_APROBADA, 'Aprobada'),
        (ESTADO_RECHAZADA, 'Rechazada'),
    ]

    registro = models.ForeignKey(
        'RegistroEstudiosPorMedico',
        on_delete=models.CASCADE,
        related_name='solicitudes_revision_horario',
        verbose_name='Registro',
    )
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='solicitudes_revision_horario_realizadas',
        verbose_name='Solicitado por',
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de solicitud')

    HORARIO_CHOICES = [
        ('INTRA', 'Intra Residencia (50%)'),
        ('EXTRA', 'Extra Residencia (100%)'),
        ('NA', 'No Aplica (Staff)'),
    ]
    horario_solicitado = models.CharField(
        max_length=6,
        choices=HORARIO_CHOICES,
        verbose_name='Horario solicitado',
    )
    fecha_hora_real_declarada = models.DateTimeField(verbose_name='Fecha/Hora real declarada')
    motivo_solicitud = models.TextField(verbose_name='Motivo de solicitud')

    estado = models.CharField(
        max_length=10,
        choices=ESTADO_CHOICES,
        default=ESTADO_PENDIENTE,
        verbose_name='Estado',
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='solicitudes_revision_horario_revisadas',
        null=True,
        blank=True,
        verbose_name='Revisado por',
    )
    fecha_revision = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de revision',
    )
    observacion_revision = models.TextField(
        blank=True,
        default='',
        verbose_name='Observacion de revision',
    )
    aplicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='solicitudes_revision_horario_aplicadas',
        null=True,
        blank=True,
        verbose_name='Aplicado por',
    )
    fecha_aplicacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de aplicacion',
    )
    horario_anterior = models.CharField(
        max_length=6,
        null=True,
        blank=True,
        verbose_name='Horario anterior',
    )
    horario_aplicado = models.CharField(
        max_length=6,
        null=True,
        blank=True,
        verbose_name='Horario aplicado',
    )
    monto_anterior = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Monto anterior',
    )
    monto_aplicado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Monto aplicado',
    )
    observacion_aplicacion = models.TextField(
        blank=True,
        default='',
        verbose_name='Observacion de aplicacion',
    )

    class Meta:
        verbose_name = 'Solicitud de revisión de horario'
        verbose_name_plural = 'Solicitudes de revisión de horario'
        ordering = ['-fecha_solicitud']
        indexes = [
            models.Index(fields=['estado', '-fecha_solicitud']),
            models.Index(fields=['registro', 'estado']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['registro'],
                condition=models.Q(estado='PENDIENTE'),
                name='uniq_revision_horario_pendiente_por_registro',
            ),
        ]

    def __str__(self):
        return f"Solicitud #{self.pk} - Registro #{self.registro_id} - {self.estado}"
    
# Modelo para registrar que fue a la lista pero no tubo pacientes
# ============================================================================
# [DEPRECADO - 16 de febrero 2026 - Sanatorio Colegiales]
# DiaSinPacientes NO se usa en Colegiales (era del sistema anterior)
# Se mantiene el modelo por compatibilidad con código legacy
# TODO: Eliminar completamente en refactor futuro
# ============================================================================

class DiaSinPacientes(models.Model):
    """[DEPRECADO] Modelo del sistema anterior, NO usar en Colegiales"""
    sesion_contable = models.ForeignKey(
        'SesionContable',
        on_delete=models.PROTECT,
        related_name='dias_sin_pacientes',
        verbose_name='Sesión Contable',
        null=True,
        blank=True
    )
    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Médico'
    )
    fecha = models.DateField(verbose_name='Fecha sin pacientes')
    observacion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observación (opcional)'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('medico', 'fecha')
        ordering = ['-fecha']
        verbose_name = 'Día sin pacientes'
        verbose_name_plural = 'Días sin pacientes'

    def __str__(self):
        return f"{self.medico.get_full_name()} - {self.fecha.strftime('%d/%m/%Y')}"
    
    def save(self, *args, **kwargs):
        # Auto-asignar sesión contable si no existe
        if not self.sesion_contable_id:
            mes = self.fecha.month
            año = self.fecha.year
            sesion, created = SesionContable.objects.get_or_create(
                mes=mes, año=año,
                defaults={'estado': 'ABIERTA'}
            )
            self.sesion_contable = sesion
        
        super().save(*args, **kwargs)


# ============================================================================
# [ANULADO - 16 de febrero 2026 - Sanatorio Colegiales]
# RegistroProcedimientosIntervensionismo - NO ELIMINAR ESTE CÓDIGO
# ============================================================================
# Razón: En Colegiales no se usa. Procedimientos se registran como Estudios.
# 
# ⚠️ IMPORTANTE: Este modelo NO se elimina del código para mantener
# compatibilidad con migraciones existentes. Si eliminas este modelo,
# Django intentará crear una migración que borre la tabla y fallará
# en producción si hay datos históricos.
#
# Alternativa segura: Crear migración personalizada que renombre la tabla
# a "liquidacion_registroprocedimientosintervensionismo_archive" y luego
# eliminar este modelo del código.
#
# Si necesitas recuperar datos: liquidacion_backup_completo_2026-02-16.json
# ============================================================================

class RegistroProcedimientosIntervensionismo(models.Model):
    """
    [DESHABILITADO] Este modelo ya no se usa en Sanatorio Colegiales.
    Mantenido solo para compatibilidad con migraciones existentes.
    """
    medico = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Médico')
    nombre_paciente = models.CharField(max_length=50, verbose_name='Nombre del paciente')
    apellido_paciente = models.CharField(max_length=50, verbose_name='Apellido del paciente')
    dni_paciente = models.CharField(max_length=50, verbose_name='DNI del paciente', blank=True, null=True)
    fecha_registro = models.DateTimeField(default=timezone.now, verbose_name='Fecha de registro')
    fecha_del_procedimiento = models.DateField(verbose_name='Fecha del procedimiento', default=timezone.now)
    procedimiento = models.CharField(max_length=150, verbose_name='Procedimiento realizado')
    conteo_regiones = models.IntegerField(verbose_name='Cantidad de regiones', blank=True, null=True, default=0)
    notas = models.TextField(verbose_name='Notas', blank=True, null=True)

    class Meta:
        verbose_name = '[DESHABILITADO] Registro de procedimiento de intervencionismo'
        verbose_name_plural = '[DESHABILITADO] Registros de procedimientos de intervencionismo'
        # Marcar como "managed = False" para que Django NO intente crear/modificar esta tabla
        managed = True  # Dejamos en True temporalmente para no romper migraciones

    def __str__(self):
        return f'{self.medico} - {self.fecha_registro}'