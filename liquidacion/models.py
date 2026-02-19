from django.db import models
from django.utils import timezone
from django.conf import settings
from decimal import Decimal

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
    
    def precio_para_os(self, tipo_os):
        """Retorna el precio según el tipo de OS"""
        if self.precio_unico:
            return self.precio_cober  # Si es único, ambos son iguales
        return self.precio_cober if tipo_os == 'COBER' else self.precio_otras_os
    
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
        if usuario.rol in ['jefe_residentes', 'instructor_residentes', 'medico_residente', 'medico_staff', 'cardiologo']:
            return self.estado in ['ABIERTA', 'REVISION']
        
        # Admin puede cargar incluso en CERRADA
        if usuario.is_superuser or usuario.rol == 'administrativo':
            return self.estado != 'PAGADA'  # Solo bloquear después de pagar
        
        return False


class GuardiaPasiva(models.Model):
    """
    Registro de guardias pasivas
    Se registra por DÍA completo, no por práctica individual
    Valor fijo por día (ej: $36.500)
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
        help_text='Valor fijo de la guardia pasiva'
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
        
        super().save(*args, **kwargs)


class RegistroEstudiosPorMedico(models.Model):
    """
    Registro individual de una práctica médica realizada
    ACTUALIZADO v2.0 - Febrero 2026
    TODO: Renombrar a 'Practica' en migración futura
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
    
    # MANTENER M2M por ahora para compatibilidad con código existente
    # En migración futura se convertirá a FK
    estudio = models.ManyToManyField(Estudios, verbose_name='Estudios')
    cantidad_estudio = models.PositiveIntegerField(
        default=1,
        blank=True,
        null=True,
        verbose_name='Cantidad por estudio'
    )
    
    # NUEVOS CAMPOS v2.0
    # Dimensiones de facturación
    cantidad_regiones = models.PositiveIntegerField(
        default=1,
        verbose_name='Cantidad de Regiones',
        help_text='Solo números enteros, no se fraccionan'
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

    def total_regiones(self):
        """LEGACY - mantener para compatibilidad"""
        total = 0
        for estudio in self.estudio.all():
            cantidad = self.cantidad_estudio or 1
            total += estudio.conteo_regiones * cantidad
        return total
    
    def calcular_monto(self):
        """
        Calcula el monto a facturar por esta práctica
        Aplica toda la lógica de: OS + Regiones + Horario + Urgencia
        """
        # Si no hay estudios asignados, retornar 0
        if not self.estudio.exists():
            return Decimal('0.00')
        
        # Calcular precio base sumando TODOS los estudios seleccionados
        precio_base_total = Decimal('0.00')
        
        for estudio_obj in self.estudio.all():
            # Precio según OS para cada estudio
            if self.tipo_obra_social == 'COBER':
                precio_base_total += estudio_obj.precio_cober
            else:
                precio_base_total += estudio_obj.precio_otras_os
        
        if precio_base_total == Decimal('0.00'):
            return Decimal('0.00')
        
        # 2. Multiplicar por regiones (precio total de todos los estudios * regiones)
        subtotal = precio_base_total * self.cantidad_regiones
        
        # 3. Aplicar porcentaje según horario
        if self.medico.rol in ['jefe_residentes', 'instructor_residentes', 'medico_residente']:
            if self.horario == 'INTRA':
                subtotal = subtotal * Decimal('0.5')  # 50%
            elif self.horario == 'EXTRA':
                subtotal = subtotal  # 100%
        else:
            # Staff (incluye cardiólogos) siempre cobra 100%
            pass
        
        # 4. Bonus urgencia para RM con pacientes internados (solo remotos)
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
        
        # Solo aplica a estudios de Resonancia Magnética
        if not self.estudio.exists():
            return Decimal('0.0')
        
        estudio_obj = self.estudio.first()
        if estudio_obj.tipo != 'RES':
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
        Útil para mostrar al médico cómo se calculó su pago
        """
        if not self.estudio.exists():
            return {}
        
        # Calcular precio base sumando TODOS los estudios
        precio_base_total = Decimal('0.00')
        estudios_nombres = []
        codigos = []
        
        for estudio_obj in self.estudio.all():
            estudios_nombres.append(estudio_obj.nombre)
            if estudio_obj.codigo:
                codigos.append(estudio_obj.codigo)
            
            if self.tipo_obra_social == 'COBER':
                precio_base_total += estudio_obj.precio_cober
            else:
                precio_base_total += estudio_obj.precio_otras_os
        
        subtotal = precio_base_total * self.cantidad_regiones
        porcentaje = 0.5 if self.horario == 'INTRA' else 1.0
        bonus_urgencia = self.calcular_bonus_urgencia()
        
        desglose = {
            'estudio': ', '.join(estudios_nombres),  # Concatenar todos los nombres
            'codigo': ', '.join(codigos) if codigos else 'N/A',
            'precio_base': precio_base_total,
            'regiones': self.cantidad_regiones,
            'subtotal': subtotal,
            'tipo_os': self.get_tipo_obra_social_display(),
            'horario': self.get_horario_display(),
            'porcentaje': f"{int(porcentaje * 100)}%",
            'monto_final': self.monto_calculado,
        }
        
        # Agregar info de urgencia si aplica
        if bonus_urgencia > 0:
            desglose['bonus_urgencia'] = f"+{int(bonus_urgencia * 100)}%"
            desglose['paciente_internado'] = True
            if self.fecha_hora_solicitud and self.fecha_hora_informe:
                delta = self.fecha_hora_informe - self.fecha_hora_solicitud
                horas = delta.total_seconds() / 3600
                desglose['tiempo_respuesta'] = f"{horas:.1f} horas"
        
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
        
        # Validación: Asignar horario automáticamente según rol y hora
        # SOLO si no está ya especificado o está vacío
        if not self.horario or self.horario == '':
            if self.medico.rol in ['medico_staff', 'jefe_servicio', 'cardiologo']:
                # Staff no tiene horario INTRA/EXTRA
                self.horario = 'NA'
            else:
                # Residentes, jefe residentes, instructores: auto-asignar según hora
                from django.utils import timezone
                hora_actual = timezone.localtime(timezone.now()).hour
                
                # 8:00 a 16:59 → INTRA (17:00 ya es EXTRA)
                if 8 <= hora_actual < 17:
                    self.horario = 'INTRA'
                else:
                    self.horario = 'EXTRA'
        
        # Calcular monto ANTES de guardar (INMUTABLE)
        # IMPORTANTE: Solo si ya tiene ID (no es nuevo) o si ya tiene estudios asignados
        # Esto evita el error de ManyToMany cuando se crea desde formulario
        if self.pk or (hasattr(self, '_estudios_temp') and self._estudios_temp):
            self.monto_calculado = self.calcular_monto()
        
        super().save(*args, **kwargs)
    
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