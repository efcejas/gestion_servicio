from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


MONEDA_CHOICES = [
    ('ARS', 'Pesos Argentinos (ARS)'),
    ('USD', 'Dólares (USD)'),
    ('EUR', 'Euros (EUR)'),
    ('BRL', 'Reales (BRL)'),
    ('otro', 'Otra moneda'),
]

TIPO_ACTIVO_CHOICES = [
    ('efectivo', 'Efectivo'),
    ('cuenta_bancaria', 'Cuenta Bancaria'),
    ('billetera_virtual', 'Billetera Virtual'),
    ('cripto', 'Criptomonedas'),
    ('otro', 'Otro'),
]

COTIZACION_TIPO_CHOICES = [
    ('blue_venta', 'Dólar Blue (venta)'),
    ('blue_compra', 'Dólar Blue (compra)'),
    ('oficial_venta', 'Dólar Oficial (venta)'),
    ('oficial_compra', 'Dólar Oficial (compra)'),
    ('mep', 'Dólar MEP'),
    ('manual', 'Cotización manual'),
    ('uno_a_uno', '1:1 (ya está en USD)'),
]


class ConfiguracionMeta(models.Model):
    """Configuración de la meta de ahorro. Solo debe existir una instancia."""
    nombre = models.CharField(
        max_length=200,
        default='Anticipo primera vivienda',
        verbose_name='Nombre del proyecto',
    )
    meta_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Meta en USD',
        help_text='Monto total objetivo en dólares',
    )
    fecha_objetivo = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha objetivo',
        help_text='Fecha estimada para alcanzar la meta (opcional)',
    )
    notas = models.TextField(
        blank=True,
        verbose_name='Notas',
    )
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de Meta'
        verbose_name_plural = 'Configuración de Meta'

    def __str__(self):
        return f'{self.nombre} — USD {self.meta_usd:,.0f}'

    @classmethod
    def get_config(cls):
        """Retorna la única instancia de configuración, o None si no existe."""
        return cls.objects.first()


class Cotizacion(models.Model):
    """Cotizaciones del dólar para una fecha dada."""
    fecha = models.DateField(
        unique=True,
        verbose_name='Fecha',
    )
    blue_compra = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Blue compra',
    )
    blue_venta = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Blue venta',
    )
    oficial_compra = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Oficial compra',
    )
    oficial_venta = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Oficial venta',
    )
    mep = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='MEP',
    )
    eur_usd = models.DecimalField(
        max_digits=10, decimal_places=4, default=Decimal('1.0800'),
        verbose_name='EUR/USD',
        help_text='Tipo de cambio Euro a Dólar (ej: 1.08)',
    )
    FUENTE_CHOICES = [('api', 'API Bluelytics'), ('manual', 'Manual')]
    fuente = models.CharField(
        max_length=10, choices=FUENTE_CHOICES, default='manual',
        verbose_name='Fuente',
    )
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cotización'
        verbose_name_plural = 'Cotizaciones'
        ordering = ['-fecha']

    def __str__(self):
        return f'Cotización {self.fecha} — Blue venta: {self.blue_venta}'

    def get_valor(self, tipo):
        """Retorna el valor de cotización según el tipo elegido."""
        valores = {
            'blue_venta': self.blue_venta,
            'blue_compra': self.blue_compra,
            'oficial_venta': self.oficial_venta,
            'oficial_compra': self.oficial_compra,
            'mep': self.mep,
        }
        return valores.get(tipo, self.blue_venta)

    @classmethod
    def mas_cercana(cls, fecha):
        """Retorna la cotización más cercana (anterior o igual) a la fecha dada."""
        return cls.objects.filter(fecha__lte=fecha).order_by('-fecha').first()


class Snapshot(models.Model):
    """Registro del capital total en un momento determinado."""
    fecha = models.DateField(
        verbose_name='Fecha del registro',
    )
    cotizacion = models.ForeignKey(
        Cotizacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='snapshots',
        verbose_name='Cotización utilizada',
    )
    total_usd_calculado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name='Total en USD',
        help_text='Suma de todos los ítems convertidos a USD',
    )
    notas = models.TextField(blank=True, verbose_name='Notas')
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='snapshots_vivienda',
        verbose_name='Registrado por',
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Snapshot de Capital'
        verbose_name_plural = 'Snapshots de Capital'
        ordering = ['-fecha']

    def __str__(self):
        return f'Snapshot {self.fecha} — USD {self.total_usd_calculado:,.2f}'

    def recalcular_total(self):
        """Recalcula el total en USD sumando todos los ítems."""
        total = sum(item.monto_usd for item in self.items.all() if item.monto_usd)
        self.total_usd_calculado = total
        self.save(update_fields=['total_usd_calculado'])
        return total


class CapitalItem(models.Model):
    """Un activo individual dentro de un snapshot."""
    snapshot = models.ForeignKey(
        Snapshot,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Snapshot',
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Descripción',
        help_text='Ej: Efectivo USD, Cuenta Galicia, Mercado Pago',
    )
    tipo = models.CharField(
        max_length=30,
        choices=TIPO_ACTIVO_CHOICES,
        default='efectivo',
        verbose_name='Tipo de activo',
    )
    moneda = models.CharField(
        max_length=10,
        choices=MONEDA_CHOICES,
        default='ARS',
        verbose_name='Moneda',
    )
    monto_original = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name='Monto original',
    )
    cotizacion_tipo = models.CharField(
        max_length=20,
        choices=COTIZACION_TIPO_CHOICES,
        default='blue_venta',
        verbose_name='Cotización a usar',
        help_text='Cómo convertir a USD',
    )
    cotizacion_manual = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='Cotización manual',
        help_text='Solo si elegiste "cotización manual"',
    )
    monto_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0'),
        verbose_name='Equivalente en USD',
    )
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden')

    class Meta:
        verbose_name = 'Ítem de Capital'
        verbose_name_plural = 'Ítems de Capital'
        ordering = ['orden', 'id']

    def __str__(self):
        return f'{self.nombre} ({self.moneda} {self.monto_original:,.2f})'

    def calcular_usd(self, cotizacion=None):
        """
        Calcula el equivalente en USD según la moneda y tipo de cotización.
        Si la moneda es USD, retorna el monto directamente.
        """
        monto = self.monto_original

        if self.moneda == 'USD' or self.cotizacion_tipo == 'uno_a_uno':
            return monto

        if self.cotizacion_tipo == 'manual':
            if self.cotizacion_manual and self.cotizacion_manual > 0:
                if self.moneda == 'EUR':
                    # EUR → USD directo con tasa EUR/USD
                    return monto * self.cotizacion_manual
                # ARS → USD: dividir por la cotización
                return monto / self.cotizacion_manual
            return Decimal('0')

        if cotizacion is None:
            cotizacion = self.snapshot.cotizacion

        if cotizacion is None:
            return Decimal('0')

        if self.moneda == 'ARS':
            valor = cotizacion.get_valor(self.cotizacion_tipo)
            if valor and valor > 0:
                return monto / valor
            return Decimal('0')

        if self.moneda == 'EUR':
            # EUR → USD: monto * (cotizacion.eur_usd or 1.08)
            eur_usd = cotizacion.eur_usd if cotizacion.eur_usd else Decimal('1.08')
            return monto * eur_usd

        if self.moneda == 'BRL':
            # BRL → USD: usar cotización manual (no hay en bluelytics)
            if self.cotizacion_manual and self.cotizacion_manual > 0:
                return monto / self.cotizacion_manual
            return Decimal('0')

        return Decimal('0')

    def save(self, *args, **kwargs):
        cotizacion = self.snapshot.cotizacion if self.snapshot_id else None
        self.monto_usd = round(self.calcular_usd(cotizacion), 2)
        super().save(*args, **kwargs)


class Conversion(models.Model):
    """Registro de una conversión entre monedas (ej: ARS → USD)."""
    fecha = models.DateField(
        default=timezone.now,
        verbose_name='Fecha',
    )
    descripcion = models.CharField(
        max_length=300,
        verbose_name='Descripción',
        help_text='Ej: Compra USD en cueva, Transferencia a cuenta exterior',
    )
    moneda_origen = models.CharField(
        max_length=10, choices=MONEDA_CHOICES, verbose_name='Moneda origen',
    )
    monto_origen = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name='Monto origen',
    )
    moneda_destino = models.CharField(
        max_length=10, choices=MONEDA_CHOICES, verbose_name='Moneda destino',
    )
    monto_destino = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name='Monto destino',
    )
    cotizacion_efectiva = models.DecimalField(
        max_digits=10, decimal_places=4,
        verbose_name='Cotización efectiva',
        help_text='Tipo de cambio real al que se realizó la operación',
    )
    cotizacion_ref = models.ForeignKey(
        Cotizacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversiones',
        verbose_name='Cotización de referencia',
    )
    notas = models.TextField(blank=True, verbose_name='Notas')
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='conversiones_vivienda',
        verbose_name='Registrado por',
    )
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Conversión'
        verbose_name_plural = 'Conversiones'
        ordering = ['-fecha', '-creada']

    def __str__(self):
        return (
            f'{self.fecha} — {self.moneda_origen} {self.monto_origen:,.2f}'
            f' → {self.moneda_destino} {self.monto_destino:,.2f}'
        )
