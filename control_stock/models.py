from django.db import models
from django.conf import settings
from django.utils import timezone


class AreaServicio(models.Model):
    nombre = models.CharField(max_length=100, verbose_name='Área / Servicio')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='areas_a_cargo',
        verbose_name='Responsable',
    )
    activa = models.BooleanField(default=True, verbose_name='Activa')
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Área de Servicio'
        verbose_name_plural = 'Áreas de Servicio'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def items_bajo_stock(self):
        return self.stock_items.filter(
            cantidad__lt=models.F('producto__stock_minimo')
        ).count()

    def tiene_vencimientos_proximos(self, dias=30):
        fecha_limite = timezone.now().date() + timezone.timedelta(days=dias)
        return self.movimientos.filter(
            tipo='entrada',
            fecha_vencimiento__isnull=False,
            fecha_vencimiento__lte=fecha_limite,
            fecha_vencimiento__gte=timezone.now().date(),
        ).exists()


CATEGORIA_CHOICES = [
    ('descartable', 'Descartable'),
    ('medicamento', 'Medicamento'),
    ('material_procedimiento', 'Material de Procedimiento'),
    ('material_limpieza', 'Material de Limpieza'),
    ('instrumental', 'Instrumental'),
    ('equipo_menor', 'Equipo Menor'),
    ('otro', 'Otro'),
]

UNIDAD_CHOICES = [
    ('unidad', 'Unidad'),
    ('caja', 'Caja'),
    ('frasco', 'Frasco'),
    ('ampolla', 'Ampolla'),
    ('bolsa', 'Bolsa'),
    ('rollo', 'Rollo'),
    ('par', 'Par'),
    ('litro', 'Litro'),
    ('ml', 'ml'),
    ('gramo', 'Gramo'),
    ('otro', 'Otro'),
]


class Producto(models.Model):
    codigo_barras = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Código de Barras',
        db_index=True,
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    categoria = models.CharField(
        max_length=30,
        choices=CATEGORIA_CHOICES,
        default='descartable',
        verbose_name='Categoría',
    )
    unidad_medida = models.CharField(
        max_length=20,
        choices=UNIDAD_CHOICES,
        default='unidad',
        verbose_name='Unidad de medida',
    )
    stock_minimo = models.PositiveIntegerField(
        default=0,
        verbose_name='Stock mínimo de alerta',
    )
    imagen_url = models.URLField(blank=True, verbose_name='URL de imagen (producto)')
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos_registrados',
        verbose_name='Registrado por',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.codigo_barras})'


class StockPorArea(models.Model):
    """
    Cache del stock total por producto/área.  La fuente de verdad son los
    LoteEnArea; este modelo se actualiza en forma sincrónica cada vez que
    un LoteEnArea cambia, para que el resto del sistema siga funcionando
    sin cambios (detalle_area, dashboard, vencimientos, etc.).
    """
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='stock_por_area',
        verbose_name='Producto',
    )
    area = models.ForeignKey(
        AreaServicio,
        on_delete=models.CASCADE,
        related_name='stock_items',
        verbose_name='Área',
    )
    cantidad = models.IntegerField(default=0, verbose_name='Cantidad en stock')

    class Meta:
        verbose_name = 'Stock por Área'
        verbose_name_plural = 'Stock por Área'
        unique_together = ('producto', 'area')
        ordering = ['producto__nombre']

    def __str__(self):
        return f'{self.producto.nombre} — {self.area.nombre}: {self.cantidad}'

    @property
    def bajo_minimo(self):
        return self.cantidad < self.producto.stock_minimo

    @property
    def diferencia_minimo(self):
        return self.cantidad - self.producto.stock_minimo

    def recalcular(self):
        """Recalcula cantidad sumando todos los lotes activos."""
        from django.db.models import Sum
        total = self.lotes.filter(activo=True).aggregate(s=Sum('cantidad'))['s'] or 0
        self.cantidad = total
        self.save(update_fields=['cantidad'])


class LoteEnArea(models.Model):
    """
    Unidad mínima de trazabilidad: un lote de un producto en un área.
    Permite controlar stock por fecha de vencimiento (FEFO) y número de lote.
    """
    stock = models.ForeignKey(
        StockPorArea,
        on_delete=models.CASCADE,
        related_name='lotes',
        verbose_name='Stock por área',
    )
    numero_lote = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='Número de lote',
    )
    fecha_vencimiento = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de vencimiento',
    )
    cantidad = models.IntegerField(default=0, verbose_name='Cantidad en este lote')
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='False cuando el lote fue descartado o agotado.',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lote en Área'
        verbose_name_plural = 'Lotes en Área'
        ordering = ['fecha_vencimiento', 'creado_en']
        indexes = [
            models.Index(fields=['stock', 'activo', 'fecha_vencimiento']),
        ]

    def __str__(self):
        vence = self.fecha_vencimiento.strftime('%d/%m/%Y') if self.fecha_vencimiento else 'sin fecha'
        lote = self.numero_lote or 'sin lote'
        return f'{self.stock.producto.nombre} — {self.stock.area.nombre} — Lote {lote} ({vence}): {self.cantidad}'

    @property
    def vencido(self):
        if not self.fecha_vencimiento:
            return False
        return self.fecha_vencimiento < timezone.now().date()

    @property
    def vence_pronto(self, dias=30):
        if not self.fecha_vencimiento or self.vencido:
            return False
        return self.fecha_vencimiento <= timezone.now().date() + timezone.timedelta(days=dias)


class MovimientoStock(models.Model):
    TIPO_ENTRADA = 'entrada'
    TIPO_SALIDA = 'salida'       # uso genérico (legacy, se mantiene por compatibilidad)
    TIPO_USO = 'uso'             # consumo en procedimiento (reversible 15 min)
    TIPO_DESCARTE = 'descarte'   # retiro por vencimiento / daño (requiere motivo)
    TIPO_AJUSTE = 'ajuste'       # corrección de inventario (requiere motivo)
    TIPO_CHOICES = [
        (TIPO_ENTRADA,  'Entrada / Reposición'),
        (TIPO_SALIDA,   'Salida'),
        (TIPO_USO,      'Uso en procedimiento'),
        (TIPO_DESCARTE, 'Descarte'),
        (TIPO_AJUSTE,   'Ajuste de inventario'),
    ]

    TIPOS_REQUIEREN_MOTIVO = {TIPO_DESCARTE, TIPO_AJUSTE}
    ROLES_PUEDEN_DESCARTAR = ('jefe_servicio', 'medico_staff', 'jefe_residentes',
                               'instructor_residentes')

    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name='Tipo')

    # Referencia opcional al lote afectado (null = operación legacy sin lote)
    lote = models.ForeignKey(
        LoteEnArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos',
        verbose_name='Lote afectado',
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='movimientos',
        verbose_name='Producto',
    )
    area = models.ForeignKey(
        AreaServicio,
        on_delete=models.CASCADE,
        related_name='movimientos',
        verbose_name='Área',
    )
    cantidad = models.PositiveIntegerField(verbose_name='Cantidad')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='movimientos_stock',
        verbose_name='Registrado por',
    )
    fecha = models.DateTimeField(auto_now_add=True, verbose_name='Fecha')
    observacion = models.CharField(max_length=255, blank=True, verbose_name='Observación')
    # Datos extraídos por IA o ingresados manualmente
    fecha_vencimiento = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de vencimiento',
    )
    numero_lote = models.CharField(max_length=100, blank=True, verbose_name='Número de lote')

    # Anulación (audit trail)
    anulado = models.BooleanField(default=False, verbose_name='Anulado')
    anulacion_de = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='movimiento_anulacion',
        verbose_name='Anulación de',
    )

    ROLES_PUEDEN_ANULAR = (
        'jefe_servicio', 'medico_staff', 'jefe_residentes', 'instructor_residentes',
    )

    class Meta:
        verbose_name = 'Movimiento de Stock'
        verbose_name_plural = 'Movimientos de Stock'
        ordering = ['-fecha']

    def __str__(self):
        simbolo = '+' if self.tipo == self.TIPO_ENTRADA else '-'
        return f'{simbolo}{self.cantidad} {self.producto.nombre} ({self.area.nombre}) — {self.fecha.strftime("%d/%m/%Y %H:%M")}'

    def puede_anular(self, user):
        """Retorna True si el usuario puede anular este movimiento."""
        if self.anulado:
            return False
        # Roles autorizados pueden anular cualquier movimiento
        if user.is_superuser or getattr(user, 'rol', None) in self.ROLES_PUEDEN_ANULAR:
            return True
        # El propio usuario puede anular sus movimientos dentro de las 24 horas
        ventana = timezone.now() - timezone.timedelta(hours=24)
        return self.usuario == user and self.fecha >= ventana
