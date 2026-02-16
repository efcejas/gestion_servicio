# SISTEMA DE LIQUIDACIÓN - SANATORIO COLEGIALES
## Especificación Completa v2.0 - Febrero 2026

---

## 1. ANÁLISIS DEL DOMINIO

### 1.1 Actores del Sistema

| Rol | Registra Prácticas | Particularidades de Facturación |
|-----|-------------------|--------------------------------|
| **Radiólogo Staff** | ✅ Sí | • Diferencia COBER vs OTRAS OS<br>• Sin diferencia INTRA/EXTRA<br>• Precio completo siempre |
| **Jefe de Residentes** | ✅ Sí | • Diferencia COBER vs OTRAS OS<br>• **INTRA residencia: 50% del valor**<br>• **EXTRA residencia: 100% del valor** |
| **Instructor Residentes** | ✅ Sí | • Ídem Jefe de Residentes |
| **Residente** | ✅ Sí | • Ídem Jefe de Residentes |
| **Cardiólogo** | 🔜 Futuro | • Probablemente como Staff |
| **Jefe de Servicio** | ✅ Sí | • Como Staff |

### 1.2 Dimensiones de Registro

Cada práctica médica tiene **4 dimensiones** que determinan su valor:

```
PRÁCTICA = Estudio × Cantidad_Regiones × Tipo_OS × Horario
```

#### Dimensión 1: **Estudio Realizado**
- Doppler Periférico en Servicio
- Doppler Periférico en Lecho
- Doppler Cardíaco en Servicio
- TAC, TAC con contraste
- RMN, RMN con contraste
- Ecografías (múltiples variantes)
- RX
- Mamografía
- Etc.

**Cada estudio tiene:**
- Código (ej: 902225)
- Nombre descriptivo
- Precio base COBER
- Precio base OTRAS OS
- Cantidad de regiones (default)
- Modalidad (RM, TC, ECO, RX)

#### Dimensión 2: **Cantidad de Regiones**
- Base: 1 región = 1× precio
- Múltiples regiones: N regiones = N× precio
- Ejemplo: Doppler 2 regiones = 2 × $8.500 = $17.000

#### Dimensión 3: **Tipo de Obra Social**
```python
COBER:    precio específico (generalmente menor)
OTRAS OS: precio estándar (generalmente mayor)
```

**Ejemplos (Octubre 2025):**
| Estudio | COBER | OTRAS OS |
|---------|-------|----------|
| Doppler Periférico Servicio | $8.500 | $10.000 |
| Doppler Cardíaco Lecho | $12.000 | $14.000 |
| Ecostress | $25.000 | $25.000 |
| RMN Cardíaca | $66.550 | $66.550 |

#### Dimensión 4: **Horario (Solo Jefes/Instructores/Residentes)**
```python
INTRA RESIDENCIA:  50% del valor calculado
EXTRA RESIDENCIA: 100% del valor calculado
N/A (Staff):      100% siempre
```

**Ejemplo real (Dra. Arianne Gonzalez - Noviembre 2025):**
```
TOTAL REGIONES ECO:        #REF  (calculado automáticamente)
TOTAL REGIONES TC:         #REF
TOTAL PASIVAS DOPPLER:   109.500

Desglose:
- INTRA_COBER:    8500 regiones × $4.250 (50% de $8.500 COBER) 
- EXTRA_COBER:    4250 regiones × $8.500 (100%)
- INTRA_OTRAS:   12000 regiones × $5.000 (50% de $10.000 OTRAS)
- EXTRA_OTRAS:    6000 regiones × $10.000 (100%)
- GUARD_PASIVAS: 36500 (valor fijo por día de guardia)
```

### 1.3 Fórmula de Cálculo

```python
def calcular_monto_practica(estudio, cantidad_regiones, tipo_os, horario, rol_usuario, 
                           paciente_internado=False, tiempo_respuesta_horas=None):
    # 1. Determinar precio base según OS
    if tipo_os == 'COBER':
        precio_base = estudio.precio_cober
    else:  # OTRAS_OS
        precio_base = estudio.precio_otras_os
    
    # 2. Multiplicar por cantidad de regiones (siempre enteras, no fraccionarias)
    subtotal = precio_base * cantidad_regiones
    
    # 3. Aplicar porcentaje según horario (solo si corresponde)
    if rol_usuario in ['jefe_residentes', 'instructor_residentes', 'residente']:
        if horario == 'INTRA':
            subtotal = subtotal * 0.5  # 50%
        elif horario == 'EXTRA':
            subtotal = subtotal * 1.0  # 100%
    else:  # Staff
        subtotal = subtotal * 1.0  # Siempre 100%
    
    # 4. NUEVO: Bonus urgencia para RM a distancia con pacientes internados
    # Si estudio es RM + paciente internado + informe < 24hs → +20%
    bonus_urgencia = 0.0
    if estudio.modalidad == 'RES' and paciente_internado:
        if tiempo_respuesta_horas and tiempo_respuesta_horas < 24:
            bonus_urgencia = 0.20  # +20%
    
    monto_final = subtotal * (1 + bonus_urgencia)
    
    return monto_final
```

### 1.4 Ciclo de Liquidación

```
┌─────────────────────────────────────────────────────────────────┐
│                    CICLO MENSUAL                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1-31 DICIEMBRE - Estado: ABIERTA                               │
│  ┌────────────────────────────────────────────┐                 │
│  │ MÉDICOS REGISTRAN PRÁCTICAS                │                 │
│  │ - Dr. López: 45 estudios                   │                 │
│  │ - Dra. Gómez: 38 estudios                  │                 │
│  │ - Dr. Martínez: 52 estudios + 4 guardias   │                 │
│  └────────────────────────────────────────────┘                 │
│           ↓                                                      │
│  1-5 ENERO - Estado: REVISION                                    │
│  ┌────────────────────────────────────────────┐                 │
│  │ REVISION PRELIMINAR                        │                 │
│  │ - Médicos pueden seguir cargando           │                 │
│  │ - Admin revisa totales                     │                 │
│  │ - Se detectan faltantes                    │                 │
│  └────────────────────────────────────────────┘                 │
│           ↓                                                      │
│  5-10 ENERO - Estado: CERRADA                                    │
│  ┌────────────────────────────────────────────┐                 │
│  │ CIERRE Y CARGA DE FALTANTES                │                 │
│  │ ⚠️ Solo Admin puede cargar prácticas       │                 │
│  │ - Médicos no pueden registrar              │                 │
│  │ - Admin corrige errores detectados         │                 │
│  │ - Se confirman totales definitivos         │                 │
│  └────────────────────────────────────────────┘                 │
│           ↓                                                      │
│  10 ENERO - Estado: FACTURADA                                    │
│  ┌────────────────────────────────────────────┐                 │
│  │ FACTURACIÓN DEFINITIVA                     │                 │
│  │ - Sistema calcula totales finales          │                 │
│  │ - Se emite factura a c/profesional         │                 │
│  │ - Se genera Excel e informes               │                 │
│  │ ⚠️ Solo Admin puede hacer correcciones     │                 │
│  └────────────────────────────────────────────┘                 │
│           ↓                                                      │
│  20-31 ENERO - Estado: PAGADA                                    │
│  ┌────────────────────────────────────────────┐                 │
│  │ PAGO A PROFESIONALES                       │                 │
│  │ "Los pagos se efectúan a los 30 días"      │                 │
│  │ 🔒 Sesión bloqueada completamente          │                 │
│  └────────────────────────────────────────────┘                 │
│                                                                  │
│  NOTA IMPORTANTE:                                                │
│  Médicos pueden registrar TARDE (después del mes) durante       │
│  REVISION o con aprobación de Admin en CERRADA                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Regla Clave:** "Prestaciones de Diciembre-25 se facturan del 01 al 10 Enero y se cobran antes de fin de mes"

---

## 2. ESTRUCTURA DE DATOS PROPUESTA

### 2.1 Modelo: `Estudio` (Actualizado)

```python
class Estudio(models.Model):
    """
    Catálogo de estudios/prácticas médicas con sus precios
    """
    codigo = models.CharField(
        max_length=10, 
        unique=True, 
        verbose_name='Código',
        help_text='Ej: 902225, 901244'
    )
    nombre = models.CharField(
        max_length=200, 
        verbose_name='Nombre del estudio',
        help_text='Ej: ANGIOTOMOGRAFIA CARDIACA'
    )
    
    MODALIDAD_CHOICES = [
        ('ECO', 'Ecografía'),
        ('RAD', 'Radiografía'),
        ('TOM', 'Tomografía'),
        ('RES', 'Resonancia Magnética'),
        ('DOP', 'Doppler'),
        ('MAM', 'Mamografía'),
    ]
    modalidad = models.CharField(
        max_length=3, 
        choices=MODALIDAD_CHOICES,
        verbose_name='Modalidad'
    )
    
    # NUEVOS CAMPOS
    precio_unico = models.BooleanField(
        default=False,
        verbose_name='Precio Único',
        help_text='Si True, precio_cober = precio_otras_os. Ej: TAC, RMN, RX'
    )
    precio_cober = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name='Precio COBER',
        help_text='Precio para obra social COBER'
    )
    precio_otras_os = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name='Precio OTRAS OS',
        help_text='Precio para otras obras sociales'
    )
    conteo_regiones_default = models.PositiveIntegerField(
        default=1,
        verbose_name='Regiones (default)',
        help_text='Cantidad de regiones por defecto'
    )
    
    # Campos de auditoría
    activo = models.BooleanField(default=True)
    fecha_actualizacion_precios = models.DateField(
        auto_now=True,
        verbose_name='Última actualización de precios'
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='estudios_actualizados',
        verbose_name='Actualizado por'
    )
    
    class Meta:
        verbose_name = 'Estudio'
        verbose_name_plural = 'Estudios'
        ordering = ['modalidad', 'nombre']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    def precio_para_os(self, tipo_os):
        """Retorna el precio según el tipo de OS"""
        if self.precio_unico:
            return self.precio_cober  # Si es único, ambos son iguales
        return self.precio_cober if tipo_os == 'COBER' else self.precio_otras_os
    
    def actualizar_precios(self, nuevo_precio_cober, nuevo_precio_otras_os, usuario):
        """
        Actualiza los precios y guarda en historial
        """
        # Guardar en historial antes de actualizar
        HistorialPrecioEstudio.objects.create(
            estudio=self,
            precio_cober_anterior=self.precio_cober,
            precio_otras_os_anterior=self.precio_otras_os,
            precio_cober_nuevo=nuevo_precio_cober,
            precio_otras_os_nuevo=nuevo_precio_otras_os,
            actualizado_por=usuario,
            motivo_actualizacion='Actualización de precios'
        )
        
        # Actualizar precios
        self.precio_cober = nuevo_precio_cober
        self.precio_otras_os = nuevo_precio_otras_os
        self.actualizado_por = usuario
        self.save()
```

### 2.2 Modelo: `HistorialPrecioEstudio` (NUEVO)

```python
class HistorialPrecioEstudio(models.Model):
    """
    Historial de cambios de precios de estudios
    Permite auditar cuándo y quién cambió los precios
    """
    estudio = models.ForeignKey(
        'Estudio',
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
        if self.precio_cober_anterior == 0:
            return 0
        variacion = ((self.precio_cober_nuevo - self.precio_cober_anterior) / self.precio_cober_anterior) * 100
        return round(variacion, 2)
    
    def get_variacion_otras_os(self):
        """Calcula porcentaje de variación OTRAS OS"""
        if self.precio_otras_os_anterior == 0:
            return 0
        variacion = ((self.precio_otras_os_nuevo - self.precio_otras_os_anterior) / self.precio_otras_os_anterior) * 100
        return round(variacion, 2)
```

### 2.3 Modelo: `SesionContable` (NUEVO)

```python
class SesionContable(models.Model):
    """
    Período de facturación mensual
    Agrupa todas las prácticas registradas en un mes
    """
    mes = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        verbose_name='Mes'
    )
    año = models.PositiveIntegerField(
        validators=[MinValueValidator(2020), MaxValueValidator(2050)],
        verbose_name='Año'
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
        null=True, blank=True,
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
        return f"{self.get_mes_display()} {self.año} ({self.estado})"
    
    def get_mes_display(self):
        meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        return meses[self.mes]
    
    def puede_registrar_practicas(self, usuario):
        """Verifica si se pueden registrar prácticas en esta sesión"""
        # Medicos solo en ABIERTA o REVISION
        if usuario.rol in ['jefe_residentes', 'instructor_residentes', 'residente', 'radiólogo_staff']:
            return self.estado in ['ABIERTA', 'REVISION']
        
        # Admin puede cargar incluso en CERRADA
        if usuario.is_superuser or usuario.rol == 'administrativo':
            return self.estado != 'PAGADA'  # Solo bloquear después de pagar
        
        return False
    
    def calcular_totales(self):
        """Calcula totales de todas las prácticas de esta sesión"""
        practicas = self.practicas.all()
        return {
            'total_practicas': practicas.count(),
            'total_facturado': sum(p.calcular_monto() for p in practicas),
            'por_medico': self._totales_por_medico(practicas),
        }
    
    def _totales_por_medico(self, practicas):
        """Agrupa totales por médico"""
        from collections import defaultdict
        totales = defaultdict(lambda: {'practicas': 0, 'monto': 0})
        
        for p in practicas:
            totales[p.medico]['practicas'] += 1
            totales[p.medico]['monto'] += p.calcular_monto()
        
        return dict(totales)
```

### 2.4 Modelo: `Practica` (Renombrado de RegistroEstudiosPorMedico)

```python
class Practica(models.Model):
    """
    Registro individual de una práctica médica realizada
    Anteriormente: RegistroEstudiosPorMedico
    """
    # Relaciones
    sesion_contable = models.ForeignKey(
        'SesionContable',
        on_delete=models.PROTECT,
        related_name='practicas',
        verbose_name='Sesión Contable'
    )
    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Médico'
    )
    estudio = models.ForeignKey(
        'Estudio',
        on_delete=models.PROTECT,
        verbose_name='Estudio Realizado'
    )
    
    # Datos del paciente
    nombre_paciente = models.CharField(max_length=50, verbose_name='Nombre')
    apellido_paciente = models.CharField(max_length=50, verbose_name='Apellido')
    dni_paciente = models.CharField(max_length=20, verbose_name='DNI')
    
    # Dimensiones de facturación
    cantidad_regiones = models.PositiveIntegerField(
        default=1,
        verbose_name='Cantidad de Regiones',
        validators=[MinValueValidator(1)],
        help_text='Solo números enteros, no se fraccionan'
    )
    
    # NUEVO: Para bonus de urgencia (RM a distancia)
    paciente_internado = models.BooleanField(
        default=False,
        verbose_name='Paciente Internado',
        help_text='Marca si el paciente estaba internado al momento del estudio'
    )
    fecha_hora_solicitud = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Fecha/Hora Solicitud',
        help_text='Cuándo se solicitó el estudio (para calcular urgencia)'
    )
    fecha_hora_informe = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Fecha/Hora Informe',
        help_text='Cuándo se entregó el informe (para calcular urgencia)'
    )
    
    TIPO_OS_CHOICES = [
        ('COBER', 'COBER'),
        ('OTRAS_OS', 'Otras Obras Sociales'),
    ]
    tipo_obra_social = models.CharField(
        max_length=10,
        choices=TIPO_OS_CHOICES,
        default='OTRAS_OS',
        verbose_name='Tipo de Obra Social'
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
        verbose_name='Horario'
    )
    
    # Fechas
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_practica = models.DateField(verbose_name='Fecha de la Práctica')
    
    # Auditoría
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='practicas_modificadas',
        verbose_name='Modificado por'
    )
    fecha_modificacion = models.DateTimeField(null=True, blank=True)
    motivo_modificacion = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Práctica Médica'
        verbose_name_plural = 'Prácticas Médicas'
        ordering = ['-fecha_practica', '-fecha_registro']
        indexes = [
            models.Index(fields=['sesion_contable', 'medico']),
            models.Index(fields=['fecha_practica']),
        ]
    
    def __str__(self):
        return f"{self.medico} - {self.estudio.nombre} - {self.fecha_practica}"
    
    def calcular_monto(self):
        """
        Calcula el monto a facturar por esta práctica
        Aplica toda la lógica de: OS + Regiones + Horario + Urgencia
        """
        # 1. Precio base según OS
        if self.tipo_obra_social == 'COBER':
            precio_base = self.estudio.precio_cober
        else:
            precio_base = self.estudio.precio_otras_os
        
        # 2. Multiplicar por regiones
        subtotal = precio_base * self.cantidad_regiones
        
        # 3. Aplicar porcentaje según horario
        rol = self.medico.rol  # Asume que User tiene campo 'rol'
        
        if rol in ['jefe_residentes', 'instructor_residentes', 'residente']:
            if self.horario == 'INTRA':
                subtotal = subtotal * Decimal('0.5')  # 50%
            elif self.horario == 'EXTRA':
                subtotal = subtotal  # 100%
        else:
            # Staff siempre cobra 100%
            pass
        
        # 4. NUEVO: Bonus urgencia para RM con pacientes internados
        bonus_urgencia = self.calcular_bonus_urgencia()
        monto_final = subtotal * (Decimal('1.0') + bonus_urgencia)
        
        return monto_final
    
    def calcular_bonus_urgencia(self):
        """
        Calcula el bonus de urgencia para RM a distancia
        +20% si paciente internado e informe en < 24 horas
        """
        # Solo aplica a estudios de Resonancia Magnética
        if self.estudio.modalidad != 'RES':
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
        precio_base = (self.estudio.precio_cober if self.tipo_obra_social == 'COBER' 
                      else self.estudio.precio_otras_os)
        
        subtotal = precio_base * self.cantidad_regiones
        porcentaje = 0.5 if self.horario == 'INTRA' else 1.0
        bonus_urgencia = self.calcular_bonus_urgencia()
        monto_final = self.calcular_monto()
        
        desglose = {
            'estudio': self.estudio.nombre,
            'codigo': self.estudio.codigo,
            'precio_base': precio_base,
            'regiones': self.cantidad_regiones,
            'subtotal': subtotal,
            'tipo_os': self.get_tipo_obra_social_display(),
            'horario': self.get_horario_display(),
            'porcentaje': f"{int(porcentaje * 100)}%",
            'monto_final': monto_final,
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
            # Solo si la sesión está abierta
            return self.sesion_contable.puede_registrar_practicas()
        
        return False
    
    def save(self, *args, **kwargs):
        # Validación: Asignar sesión contable automáticamente
        if not self.sesion_contable_id:
            mes = self.fecha_practica.month
            año = self.fecha_practica.year
            sesion, created = SesionContable.objects.get_or_create(
                mes=mes, año=año,
                defaults={'estado': 'ABIERTA'}
            )
            self.sesion_contable = sesion
        
        # Validación: Staff no debe tener horario INTRA/EXTRA
        if self.medico.rol in ['radiólogo_staff', 'jefe_servicio', 'cardiólogo']:
            self.horario = 'NA'
        
        super().save(*args, **kwargs)
```

### 2.5 Modelo: `GuardiaPasiva` (NUEVO)

```python
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
        ('COBER', 'COBER - $36.500'),  # Precio ejemplo
        # Agregar más tipos si hay variaciones
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
        default=36500.00,
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
```

### 2.6 Modelo: `DiaSinPacientes` (Mantener)

```python
class DiaSinPacientes(models.Model):
    """
    Registro de días donde el médico no tuvo pacientes
    (mantener como está, pero agregar sesion_contable)
    """
    sesion_contable = models.ForeignKey(
        'SesionContable',
        on_delete=models.PROTECT,
        related_name='dias_sin_pacientes',
        verbose_name='Sesión Contable'
    )
    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Médico'
    )
    fecha = models.DateField(verbose_name='Fecha sin pacientes')
    observacion = models.TextField(
        blank=True,
        verbose_name='Observación'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('medico', 'fecha')
        ordering = ['-fecha']
        verbose_name = 'Día sin pacientes'
        verbose_name_plural = 'Días sin pacientes'
    
    def __str__(self):
        return f"{self.medico.get_full_name()} - {self.fecha.strftime('%d/%m/%Y')}"
```

---

## 3. INTERFACES DE USUARIO

### 3.1 Formulario de Registro de Práctica

```
┌────────────────────────────────────────────────────────────┐
│  REGISTRAR NUEVA PRÁCTICA                                   │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Fecha de la Práctica: [  /  /    ] 📅                    │
│                                                             │
│  ━━━ DATOS DEL PACIENTE ━━━                                │
│  Nombre:    [________________]                              │
│  Apellido:  [________________]                              │
│  DNI:       [________]                                      │
│                                                             │
│  ━━━ ESTUDIO REALIZADO ━━━                                 │
│  Estudio:   [▼ Buscar estudio...              ]            │
│             902225 - ANGIOTOMOGRAFIA CARDIACA               │
│                                                             │
│  Cantidad de Regiones: [1] ▲▼  (solo números enteros)      │
│                                                             │
│  ━━━ FACTURACIÓN ━━━                                       │
│  Obra Social: ⚪ COBER     ⚪ OTRAS OS                      │
│                                                             │
│  🔒 Horario:  ⚪ INTRA RESIDENCIA (50%)                     │
│              ⚪ EXTRA RESIDENCIA (100%)                     │
│              [Solo visible si eres Jefe/Instructor/Resid]  │
│                                                             │
│  ━━━ URGENCIA (Solo RM con pacientes internados) ━━━       │
│  ☑️ Paciente Internado                                     │
│  [✅ Activado - se muestran campos adicionales]            │
│                                                             │
│  Fecha/Hora Solicitud:  [  /  /     --:--] 📅🕐           │
│  Fecha/Hora Informe:    [  /  /     --:--] 📅🕐           │
│                                                             │
│  ⏱️ Tiempo de respuesta: 18.5 horas                         │
│  ✅ BONUS URGENCIA +20% (< 24 horas)                       │
│                                                             │
│  ━━━ RESUMEN ━━━                                           │
│  ┌──────────────────────────────────────────┐              │
│  │ Precio base (COBER):      $66.550,00     │              │
│  │ × Regiones:                      1        │              │
│  │ Subtotal:                 $66.550,00     │              │
│  │ Horario (INTRA 50%):       -$33.275,00   │              │
│  │ Subtotal ajustado:        $33.275,00     │              │
│  │ 🚀 Bonus Urgencia (+20%):  +$6.655,00    │              │
│  │ ═══════════════════════════════════════  │              │
│  │ TOTAL A FACTURAR:         $39.930,00     │              │
│  └──────────────────────────────────────────┘              │
│                                                             │
│  [Cancelar]                    [Registrar Práctica] ✓      │
└────────────────────────────────────────────────────────────┘
```

**Validaciones:**
- Fecha no puede ser futura
- Fecha debe estar dentro de sesión ABIERTA o REVISION
- DNI: 7-8 dígitos
- No duplicar: mismo paciente + mismo estudio + misma fecha en 5 min
- Si es Staff → Horario = N/A (ocultar select)
- Si estudio NO es RM → Ocultar checkbox "Paciente Internado"
- Si "Paciente Internado" = false → Ocultar campos de fechas/horas
- Si fechas/horas completas → Calcular tiempo respuesta automáticamente
- Si tiempo < 24hs → Mostrar badge "BONUS +20%"
- Cálculo en tiempo real con JavaScript
- Cantidad de regiones: validar que sea entero positivo (sin decimales)

### 3.2 Dashboard del Médico - "Mis Prácticas"

```
┌────────────────────────────────────────────────────────────┐
│  MIS PRÁCTICAS                                              │
│  Dr. Juan Pérez - Jefe de Residentes                       │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Período: [Diciembre ▼] [2025 ▼]    Estado: 🟢 ABIERTA    │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  RESUMEN MENSUAL                                            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                             │
│  ┌─────────────────────┬─────────────────────────────────┐ │
│  │ Total Prácticas     │              45                  │ │
│  ├─────────────────────┼─────────────────────────────────┤ │
│  │ COBER               │  12 prácticas →    $125.000,00  │ │
│  │ OTRAS OS            │  33 prácticas →    $287.500,00  │ │
│  ├─────────────────────┼─────────────────────────────────┤ │
│  │ INTRA Residencia    │  23 regiones  →    $ 95.000,00  │ │
│  │ EXTRA Residencia    │  22 regiones  →    $180.000,00  │ │
│  ├─────────────────────┼─────────────────────────────────┤ │
│  │ TOTAL A COBRAR      │                 $412.500,00     │ │
│  └─────────────────────┴─────────────────────────────────┘ │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  DETALLE DE PRÁCTICAS (últimas 10)                         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                             │
│  Fecha       Paciente            Estudio          Monto    │
│  ──────────────────────────────────────────────────────── │
│  15/12/2025  GOMEZ, Juan         Doppler Cardíaco $8.500  │
│  15/12/2025  LOPEZ, María        TAC con contraste $5.000 │
│  14/12/2025  MARTINEZ, Pedro     RMN Cardíaca     $33.275 │
│  ...                                                        │
│                                                             │
│  [Ver Todas] [Exportar PDF] [Exportar Excel]               │
│                                                             │
│  [+ Registrar Nueva Práctica]                              │
└────────────────────────────────────────────────────────────┘
```

### 3.3 Panel Administrativo - Liquidación

```
┌────────────────────────────────────────────────────────────┐
│  LIQUIDACIÓN MENSUAL                                        │
│  Panel Administrativo                                       │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Período: [Diciembre ▼] [2025 ▼]                          │
│  Estado: 🟢 ABIERTA → [Cerrar Sesión]                     │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  TOTALES GENERALES                                          │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                             │
│  Total Prácticas Registradas:     342                      │
│  Total a Facturar:           $3.245.500,00                 │
│  Profesionales Activos:           12                       │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  POR PROFESIONAL                                            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                             │
│  Profesional              Prácticas    Monto        [Acc]  │
│  ──────────────────────────────────────────────────────── │
│  Dra. Gonzalez, Arianne      45     $412.500,00    [Ver]  │
│  Dr. López, Carlos           38     $320.000,00    [Ver]  │
│  Dr. Martínez, Javier        52     $485.000,00    [Ver]  │
│  Dra. Rodríguez, Ana         29     $280.000,00    [Ver]  │
│  ...                                                        │
│                                                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  ACCIONES                                                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                             │
│  [📊 Exportar Excel General]                               │
│  [📄 Generar PDFs Individuales]                            │
│  [🔒 Cerrar Sesión Contable]                               │
│  [💰 Marcar como Facturada]                                │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

---

## 4. LÓGICA DE NEGOCIO

### 4.1 Reglas de Validación

```python
class ReglaValidacionPractica:
    """
    Centraliza todas las reglas de validación
    """
    
    @staticmethod
    def validar_fecha_practica(fecha, sesion):
        """La fecha debe estar dentro del mes de la sesión"""
        if fecha.month != sesion.mes or fecha.year != sesion.año:
            raise ValidationError(
                f"La fecha debe estar en {sesion.get_mes_display()} {sesion.año}"
            )
        
        if fecha > date.today():
            raise ValidationError("No puede registrar prácticas futuras")
    
    @staticmethod
    def validar_horario_segun_rol(medico, horario):
        """Staff no puede tener horario INTRA/EXTRA"""
        roles_staff = ['radiólogo_staff', 'jefe_servicio', 'cardiólogo']
        
        if medico.rol in roles_staff:
            if horario != 'NA':
                raise ValidationError(
                    "Los médicos de staff no tienen diferenciación de horario"
                )
        else:
            # Jefes/Instructores/Residentes
            if horario == 'NA':
                raise ValidationError(
                    "Debe especificar INTRA o EXTRA residencia"
                )
    
    @staticmethod
    def validar_sesion_abierta(sesion):
        """Solo se puede registrar en sesiones abiertas"""
        if not sesion.puede_registrar_practicas():
            raise ValidationError(
                f"La sesión {sesion} está {sesion.estado}. "
                "No se pueden registrar nuevas prácticas."
            )
    
    @staticmethod
    def validar_duplicado(medico, paciente_dni, estudio, fecha_practica):
        """
        Evitar duplicados: mismo médico + paciente + estudio + fecha
        en los últimos 5 minutos
        """
        hace_5_min = timezone.now() - timedelta(minutes=5)
        
        existe = Practica.objects.filter(
            medico=medico,
            dni_paciente=paciente_dni,
            estudio=estudio,
            fecha_practica=fecha_practica,
            fecha_registro__gte=hace_5_min
        ).exists()
        
        if existe:
            raise ValidationError(
                "Ya registraste una práctica idéntica hace menos de 5 minutos. "
                "Si es correcto, espera un momento e intenta de nuevo."
            )
```

### 4.2 Casos de Uso Principales

#### CU-01: Registrar Práctica
```
Actor: Médico
Precondiciones: 
  - Usuario autenticado
  - Sesión contable ABIERTA

Flujo Principal:
1. Médico accede a "Mis Prácticas"
2. Click en "+ Registrar Nueva Práctica"
3. Completa formulario:
   - Fecha de la práctica
   - Datos del paciente (nombre, apellido, DNI)
   - Estudio realizado (select con buscador)
   - Cantidad de regiones
   - Tipo de Obra Social (COBER/OTRAS)
   - Horario (si corresponde)
4. Sistema valida datos
5. Sistema calcula monto automáticamente
6. Médico confirma
7. Sistema guarda práctica
8. Sistema actualiza totales del dashboard

Flujos Alternativos:
4a. Fecha fuera de sesión actual → Error
4b. DNI inválido → Error
4c. Duplicado detectado → Advertencia + confirmación
4d. Sesión cerrada → Error "No puede registrar"
```

#### CU-02: Cerrar Sesión Contable
```
Actor: Administrativo
Precondiciones:
  - Usuario con rol administrativo
  - Sesión en estado ABIERTA

Flujo Principal:
1. Admin accede a "Liquidación"
2. Selecciona sesión a cerrar
3. Sistema muestra resumen:
   - Total prácticas
   - Total guardias pasivas
   - Total a facturar
   - Desglose por médico
   - Prácticas con bonus urgencia
4. Admin revisa datos
5. Admin click "Pasar a REVISION"
6. Sistema:
   - Cambia estado → REVISION
   - Médicos aún pueden cargar
   - Admin revisa faltantes
7. Admin click "Cerrar Definitivamente"
8. Sistema solicita confirmación
9. Admin confirma
10. Sistema:
    - Cambia estado → CERRADA
    - Registra fecha_cierre
    - Registra usuario que cerró
    - Bloquea registros de médicos
    - Admin puede seguir cargando faltantes
11. Admin verifica todo correcto
12. Admin click "Facturar"
13. Sistema:
    - Cambia estado → FACTURADA
    - Genera reportes finales
    - Envía notificaciones a médicos
    - Bloquea modificaciones (solo Admin con motivo)

Flujos Alternativos:
10a. Se detectan faltantes → Admin carga manualmente en CERRADA
10b. Hay prácticas con montos $0 → Advertencia
10c. Hay médicos sin prácticas en el mes → Advertencia
12a. Médico reporta error después de FACTURADA → Admin corrige con auditoría

Flujo de Reapertura (Excepcional):
- Admin puede cambiar REVISION → ABIERTA
- Admin puede cambiar CERRADA → REVISION
- FACTURADA NO se puede reabrir (solo correcciones con motivo)
```

#### CU-03: Ver Resumen Personal
```
Actor: Médico
Precondiciones:
  - Usuario autenticado

Flujo Principal:
1. Médico accede a "Mis Prácticas"
2. Sistema muestra:
   - Resumen del mes actual (ABIERTA)
   - Totales por tipo de OS
   - Totales por horario (si aplica)
   - Total a cobrar
   - Lista de prácticas registradas
3. Médico puede:
   - Exportar PDF con detalle
   - Exportar Excel
   - Filtrar por fecha/tipo de estudio
   - Editar práctica (si sesión ABIERTA)
   - Ver histórico de meses anteriores
```

---

## 5. PLAN DE IMPLEMENTACIÓN

### Fase 1: Modelos y Migraciones (4-5 horas)

**Tareas:**
1. ✅ Crear modelo `HistorialPrecioEstudio`:
   - Registra cambios de precios automáticamente
   - Campos: precio_anterior, precio_nuevo, fecha, usuario, motivo
   - Métodos: get_variacion_cober(), get_variacion_otras_os()
2. ✅ Crear modelo `SesionContable` con estados: ABIERTA → REVISION → CERRADA → FACTURADA → PAGADA
3. ✅ Actualizar modelo `Estudio`:
   - Agregar `codigo`, `precio_unico` (Boolean)
   - Agregar `precio_cober`, `precio_otras_os`
   - Agregar `conteo_regiones_default`, `activo`
   - Agregar `fecha_actualizacion_precios`, `actualizado_por`
   - Método `actualizar_precios()` que guarda en historial automáticamente
4. ✅ Renombrar `RegistroEstudiosPorMedico` → `Practica`
5. ✅ Actualizar modelo `Practica`:
   - Agregar `sesion_contable` (FK)
   - Agregar `tipo_obra_social` (COBER/OTRAS_OS)
   - Agregar `horario` (INTRA/EXTRA/NA)
   - Agregar `cantidad_regiones` (PositiveIntegerField, no decimales)
   - **NUEVO:** Agregar `paciente_internado` (Boolean)
   - **NUEVO:** Agregar `fecha_hora_solicitud` (DateTime)
   - **NUEVO:** Agregar `fecha_hora_informe` (DateTime)
   - Cambiar `estudio` de M2M a FK (un estudio por registro)
   - Agregar métodos `calcular_monto()`, `calcular_bonus_urgencia()`, `get_desglose_monto()`
   - Agregar campos auditoría (`modificado_por`, etc.)
6. ✅ **NUEVO:** Crear modelo `GuardiaPasiva`:
   - sesion_contable, medico, fecha_guardia
   - tipo_guardia (COBER por defecto)
   - monto (valor fijo por día: $36.500)
   - unique_together: (medico, fecha_guardia)
7. ✅ Actualizar `DiaSinPacientes`: agregar `sesion_contable` (mantener para compatibilidad)
8. ✅ Crear migraciones
9. ✅ Migrar datos existentes:
   - Crear sesiones contables retroactivas
   - Asignar prácticas antiguas a sus sesiones
   - Rellenar `tipo_obra_social='OTRAS_OS'` por defecto
   - Rellenar `horario='NA'` para staff
   - Rellenar `paciente_internado=False` por defecto

**Script de migración de datos:**
```python
# liquidacion/management/commands/migrar_practicas_v2.py
from django.core.management.base import BaseCommand
from liquidacion.models import SesionContable, Practica
from liquidacion.models import RegistroEstudiosPorMedico  # Modelo viejo

class Command(BaseCommand):
    def handle(self, *args, **options):
        # 1. Crear sesiones contables retroactivas
        for practica_vieja in RegistroEstudiosPorMedico.objects.all():
            mes = practica_vieja.fecha_del_informe.month
            año = practica_vieja.fecha_del_informe.year
            sesion, created = SesionContable.objects.get_or_create(
                mes=mes, año=año,
                defaults={'estado': 'CERRADA'}  # Meses pasados ya cerrados
            )
            
            # 2. Determinar horario según rol
            if practica_vieja.medico.rol in ['jefe_residentes', 'instructor_residentes', 'residente']:
                horario = 'EXTRA'  # Asumir EXTRA por defecto (más seguro)
            else:
                horario = 'NA'
            
            # 3. Migrar a nuevo modelo
            Practica.objects.create(
                sesion_contable=sesion,
                medico=practica_vieja.medico,
                estudio=practica_vieja.estudios.first(),  # M2M → FK (tomar primero)
                nombre_paciente=practica_vieja.nombre_paciente,
                apellido_paciente=practica_vieja.apellido_paciente,
                dni_paciente=practica_vieja.dni_paciente,
                cantidad_regiones=1,  # Default
                tipo_obra_social='OTRAS_OS',  # Default conservador
                horario=horario,
                fecha_practica=practica_vieja.fecha_del_informe,
                paciente_internado=False,  # Default
            )
            
            self.stdout.write(f"Migrada práctica {practica_vieja.id}")
        
        self.stdout.write(self.style.SUCCESS('Migración completada'))
```

### Fase 2: Formularios y Vistas (5-6 horas)

**Tareas:**
1. ✅ Crear `PracticaForm` con validaciones
   - Campo `estudio` con Select2
   - Campo `tipo_obra_social` (radio buttons)
   - Campo `horario` (radio buttons, condicional)
   - **NUEVO:** Campo `paciente_internado` (checkbox, solo visible si modalidad=RES)
   - **NUEVO:** Campos `fecha_hora_solicitud`, `fecha_hora_informe` (condicionales)
   - JavaScript para cálculo en tiempo real (incluye bonus urgencia)
   - Validación: cantidad_regiones debe ser entero positivo
2. ✅ **NUEVO:** Crear `GuardiaPasivaForm`
   - Campo fecha_guardia con calendario
   - Campo tipo_guardia (COBER por defecto)
   - Monto fijo editable (default $36.500)
3. ✅ Vista `RegistrarPracticaView`:
   - Validar sesión ABIERTA o REVISION (médicos)
   - Validar sesión ABIERTA, REVISION o CERRADA (admin)
   - Auto-asignar médico logueado
   - Auto-completar horario='NA' si es staff
   - Validar fechas de urgencia si paciente_internado=True
4. ✅ **NUEVO:** Vista `RegistrarGuardiaPasivaView`:
   - Similar a RegistrarPracticaView
   - Auto-asignar médico
   - Validar no duplicar mismo día
5. ✅ Vista `MisPracticasView`:
   - Dashboard con resumen mensual
   - Incluir guardias pasivas en totales
   - Lista de prácticas con indicador de bonus urgencia
   - Exportación PDF/Excel
6. ✅ Vista `LiquidacionAdminView`:
   - Resumen general
   - Totales por médico (prácticas + guardias)
   - Acciones de cambio de estado
   - Botones: Pasar a REVISION, Cerrar, Facturar, Reabrir
7. ✅ Vista `CerrarSesionView`:
   - Confirmación
   - Cálculo final
   - Cambio de estado

### Fase 3: UI y Templates (3-4 horas)

**Tareas:**
1. ✅ Template `practica_form.html` con Tailwind
2. ✅ Template `mis_practicas.html` responsive  
3. ✅ Template `liquidacion_admin.html`
4. ✅ Componente JS para cálculo en tiempo real
5. ✅ Componente JS para búsqueda de estudios

### Fase 4: Reportes y Exportación (2-3 horas)

**Tareas:**
1. ✅ Función `exportar_excel_practicas_medico()`
2. ✅ Función `generar_pdf_liquidacion_individual()`
3. ✅ Función `generar_excel_liquidacion_general()`
4. ✅ Templates de email para notificaciones

### Fase 5: Datos Iniciales (2-3 horas)

**Tareas:**
1. ✅ Fixture con estudios de Colegiales:
   - **Estudios con precio único (`precio_unico=True`):**
     * TAC ($4.000), TAC con/cte ($5.000), ANGIO TAC ($7.000)
     * RMN ($5.000), RMN con contraste ($6.000), ANGIO RMN ($8.000), RMN DIFUSION ($8.000)
     * RX ($1.500), MAMOGRAFIA REGION ($1.500)
     * 902225 - ANGIOTOMOGRAFIA CARDIACA ($66.550)
     * 902226 - ANGIOTOMOGRAFIA PARA TAVI ($66.550)
     * 901244 - TAC SCORE ($66.550)
     * 902233 - TAC TRIPLE RULE OUT ($66.550)
   - **Estudios con precio diferenciado (`precio_unico=False`):**
     * Ecografías (variantes) - COBER vs OTRAS OS
     * Doppler (Periférico, Cardíaco, etc.) - COBER vs OTRAS OS
2. ✅ Script para actualizar precios (con registro en HistorialPrecioEstudio)
3. ✅ Vista en Admin para ver historial de precios por estudio
4. ✅ Crear sesión contable del mes actual (ABIERTA)

### Fase 6: Testing y Deploy (2-3 horas)

**Tareas:**
1. ✅ Tests unitarios de modelos
2. ✅ Tests de cálculo de montos
3. ✅ Tests de validaciones
4. ✅ Tests de vistas
5. ✅ Deploy a Heroku
6. ✅ Capacitación a usuarios

---

## 6. EJEMPLO COMPLETO DE FLUJO

### Escenario: Dra. Arianne Gonzalez - Noviembre 2025

**Contexto:**
- Rol: Jefa de Residentes
- Modalidad: Tiene prácticas INTRA y EXTRA residencia
- OS: COBER y OTRAS

**Registros realizados:**

| Fecha | Paciente | Estudio | OS | Horario | Regiones | Cálculo |
|-------|----------|---------|----|---------|-----------| --------|
| Fecha | Paciente | Estudio | OS | Horario | Regiones | Cálculo | Urgencia |
|-------|----------|---------|----|---------|-----------| --------|-----------|
| 05/11 | Gómez J. | Doppler Periférico Servicio | COBER | EXTRA | 1 | $8.500 × 1 × 100% = $8.500 | - |
| 05/11 | López M. | Doppler Periférico Servicio | OTRAS | INTRA | 1 | $10.000 × 1 × 50% = $5.000 | - |
| 12/11 | Ruiz P. | Doppler Cardíaco Lecho | COBER | EXTRA | 2 | $12.000 × 2 × 100% = $24.000 | - |
| 15/11 | Díaz S. | TAC con contraste | OTRAS | INTRA | 1 | $5.000 × 1 × 50% = $2.500 | - |
| 18/11 | Fernández L. | RMN Cardíaca | COBER | EXTRA | 1 | $66.550 × 1 × 100% × 1.20 = $79.860 | **+20% (Internado, <24hs)** |
| 14/11 | (Guardia Pasiva - Sábado) | - | COBER | - | - | $36.500 (fijo por día) | - |
| ... | ... | ... | ... | ... | ... | ... | ... |

**Totales calculados:**

```python
# Resumen mes Noviembre 2025
total_practicas = 45

# Desglose por OS
cober_practicas = 12
cober_monto = 125000

otras_os_practicas = 33
otras_os_monto = 287500

# Desglose por horario
intra_regiones = 23
intra_monto = 95000  # (promedio 50% de precio base)

extra_regiones = 22
extra_monto = 180000  # (100% de precio base)

# TOTAL
total_a_cobrar = 412500

# Guardias Pasivas (ejemplo: 4 días en el mes)
guardias_pasivas = 4
total_guardias = 4 * 36500  # $146.000

# TOTAL GENERAL
total_general = total_a_cobrar + total_guardias  # $558.500
```

**En el dashboard de la Dra. Gonzalez verá:**

```
════════════════════════════════════════════
MIS PRÁCTICAS - NOVIEMBRE 2025
════════════════════════════════════════════

RESUMEN MENSUAL
────────────────────────────────────────────
Total Prácticas:        45

Por Obra Social:
  COBER:        12 →  $125.000,00
  OTRAS OS:     33 →  $287.500,00

Por Horario:
  INTRA:        23 →  $ 95.000,00
  EXTRA:        22 →  $180.000,00

Bonus Urgencia (RM <24hs):
  Internados:    2 →  $ 26.620,00  (+20%)

Guardias Pasivas:
  4 días × $36.500 →  $146.000,00

════════════════════════════════════════════
TOTAL A COBRAR:         $559.120,00
════════════════════════════════════════════

Fecha de facturación: 01-10 Diciembre 2025
Fecha de cobro estimada: 20-31 Diciembre 2025
```

---

## 7. CONSIDERACIONES TÉCNICAS

### 7.1 Performance

**Optimizaciones necesarias:**
```python
# En MisPracticasView
practicas = Practica.objects.filter(
    medico=request.user,
    sesion_contable__mes=mes,
    sesion_contable__año=año
).select_related(
    'estudio', 'sesion_contable'
).only(
    'fecha_practica', 'estudio__nombre', 'cantidad_regiones',
    'tipo_obra_social', 'horario'
)

# Cálculo de totales (una sola query)
from django.db.models import Sum, Count, Case, When, DecimalField, F

totales = practicas.aggregate(
    total_practicas=Count('id'),
    # Usar anotaciones para calcular montos en DB
)
```

### 7.2 Seguridad

**Control de accesos:**
```python
# En cada vista
@login_required
@require_role(['jefe_residentes', 'instructor_residentes', 'residente', 'radiólogo_staff'])
def registrar_practica(request):
    # Solo puede registrar en sesión abierta
    # Solo puede ver sus propias prácticas
    # Admin puede ver todo
```

### 7.3 Auditoría

**Log de cambios:**
```python
# Al modificar una práctica
practica.modificado_por = request.user
practica.fecha_modificacion = timezone.now()
practica.motivo_modificacion = "Corrección de OS (era OTRAS, ahora COBER)"
practica.save()

# Crear registro en tabla de auditoría
AuditoriaLiquidacion.objects.create(
    usuario=request.user,
    accion='MODIFICAR_PRACTICA',
    practica=practica,
    datos_anteriores={...},
    datos_nuevos={...}
)
```

---

## 8. PREGUNTAS PENDIENTES PARA VALIDAR

Antes de implementar, necesito que confirmes:

### 8.1 Sobre Estudios y Precios

1. ✅ **¿Los precios cambian cada mes?**
   - **RESPUESTA:** NO. Los precios se mantienen estables hasta que se negocie un aumento periódico.
   - **Implementación:** 
     * Sistema de actualización manual con fecha de última actualización
     * **SÍ necesitamos historial de precios** para auditoría y tracking
     * Modelo `HistorialPrecioEstudio` guarda cambios automáticamente

2. ✅ **¿Todos los estudios tienen precio COBER y OTRAS OS?**
   - **RESPUESTA:** NO. Algunos estudios tienen **precio único** (mismo para COBER y OTRAS OS).
   - **Estudios con precio único (Octubre-25):**
     * TAC: $4.000
     * TAC con/cte: $5.000
     * ANGIO TAC: $7.000
     * RMN: $5.000
     * RMN con contraste: $6.000
     * ANGIO RMN: $8.000
     * RMN DIFUSION: $8.000
     * RX: $1.500
     * MAMOGRAFIA REGION: $1.500
   - **Estudios con precio único (Noviembre-25 - Cardíacos):**
     * 902225 - ANGIOTOMOGRAFIA CARDIACA: $66.550
     * 902226 - ANGIOTOMOGRAFIA PARA TAVI: $66.550
     * 901244 - TAC SCORE DE RIESGO CORONARIO: $66.550
     * 902233 - TAC TRIPLE RULE OUT: $66.550
   - **Implementación:** Campo `precio_unico=True` → precio_cober = precio_otras_os

3. ✅ **¿Las guardias pasivas son un registro aparte?**
   - **RESPUESTA:** SÍ. Se registran por DÍA completo (no por práctica individual).
   - **Ejemplo:** "La Dra. estuvo de guardia pasiva el sábado 14 de febrero" → $36.500 por día
   - **Implementación:** Modelo `GuardiaPasiva` independiente.

### 8.2 Sobre Horarios

4. ✅ **¿Staff NUNCA tiene diferencia INTRA/EXTRA?**
   - **CONFIRMADO:** Solo jefes/instructores/residentes tienen diferenciación INTRA (50%) vs EXTRA (100%).

5. ✅ **¿El porcentaje 50% INTRA es siempre fijo?**
   - **CONFIRMADO:** Siempre 50% INTRA, 100% EXTRA (no varía por estudio).

### 8.3 Sobre Ciclo de Liquidación

6. ✅ **¿Quién puede cerrar una sesión contable?**
   - **RESPUESTA:** Admin cierra la sesión del mes.
   - **IMPORTANTE:** Debe haber posibilidad de **REVISIÓN y CARGA DE FALTANTES** después del cierre.
   - **Implementación:** Estados: ABIERTA → REVISION → CERRADA → FACTURADA → PAGADA.

7. ✅ **¿Los médicos pueden editar/borrar prácticas después del cierre?**
   - **RESPUESTA:** Médicos pueden registrar tarde (después del mes que corresponde).
   - **Implementación:** Permitir registros retroactivos con validación de Admin.
   - Solo Admin puede hacer correcciones después de FACTURADA.

### 8.4 Sobre Regiones

8. ✅ **¿La cantidad de regiones puede ser fraccionaria?**
   - **RESPUESTA:** NO. Las regiones NO se fraccionan, siempre números enteros (1, 2, 3, etc.).

9. ✅ **¿Hay estudios que no tienen concepto de "regiones"?**
   - **CONFIRMADO:** Estudios como RX, Mamografía = 1 región fija.
   - Otros como ECO Doppler pueden tener múltiples regiones.

### 8.5 Sobre RM a Distancia con URGENCIA (NUEVO REQUISITO)

10. ✅ **Médicos de RM a distancia con pacientes internados**
    - **REQUISITO:** Estudios de pacientes INTERNADOS informados en **menos de 24 horas** → **+20% sobre precio base**
    - **Estado:** Ya aceptado, aún NO implementado
    - **Implementación:** Campos `paciente_internado`, `fecha_hora_solicitud`, `fecha_hora_informe`

---

## ⚠️ DECISIONES FINALES CONFIRMADAS:

**1. ✅ Prácticas usan precio del momento del registro (INMUTABLE)**
   - Modelo `Practica` tendrá campo `monto_calculado` (Decimal)
   - Se calcula y guarda al momento de crear/editar la práctica
   - Si cambio precio de estudio, prácticas viejas NO se recalculan
   - **Implementación:** `monto_calculado = models.DecimalField()` + `save()` override

**2. ✅ Bonus urgencia (+20%) aplica SOLO a médicos de RM a distancia (remoto)**
   - NO aplica a staff de RM del hospital
   - **Implementación:** 
     * Agregar campo `User.trabaja_remoto` (Boolean) o rol específico
     * `calcular_bonus_urgencia()` valida: `if medico.trabaja_remoto and modalidad=='RES'`

**3. ✅ Cardiólogos son Staff (sin INTRA/EXTRA)**
   - Cardiólogos siempre cobran 100%, no tienen diferenciación de horario
   - **Implementación:** Rol 'cardiólogo' en lista de staff: `['radiólogo_staff', 'jefe_servicio', 'cardiólogo']`

---

## 9. PRÓXIMOS PASOS

### ✅ COMPLETADO:
- 📄 Documento completo de especificación v2.0
- 📊 Modelo de datos con historial de precios
- 🏥 GuardiaPasiva (registro por día)
- 🚀 Bonus urgencia RM (<24hs internados, solo remotos)
- 🔄 Estados de sesión contable (ABIERTA → REVISION → CERRADA → FACTURADA → PAGADA)
- ✅ Validaciones y reglas de negocio
- 📋 Listado de estudios con precio único vs diferenciado
- ✅ **TODAS LAS DECISIONES CONFIRMADAS** (inmutable, remoto, cardiólogos=staff)

### 🚀 COMENZANDO IMPLEMENTACIÓN:

**FASE 1: MODELOS Y MIGRACIONES (4-5 horas)**
1. ✅ Crear HistorialPrecioEstudio
2. ✅ Actualizar Estudio (precio_unico, actualizado_por)
3. ✅ Crear SesionContable (5 estados)
4. ✅ Crear/Actualizar Practica:
   - Campo `monto_calculado` (Decimal, se guarda al crear)
   - Campos urgencia (paciente_internado, fechas)
   - Método `calcular_monto()` (valida trabaja_remoto)
5. ✅ Crear GuardiaPasiva
6. ✅ Actualizar User: campo `trabaja_remoto` (Boolean)
7. ✅ Migración de datos existentes

**Tiempo estimado total:** 18-22 horas de desarrollo + 5 horas de testing/deploy

---

🚀 **ARRANCANDO CON LA IMPLEMENTACIÓN AHORA...**
