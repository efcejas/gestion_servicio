"""
Management command para cargar los grupos tarifarios con contexto de ubicación
y actualizar las tarifas con los valores reales de la matriz Abril 2026.

Grupos nuevos:
  Doppler Periférico: DOP_PERIFERICO (servicio), DOP_PERIFERICO_LECHO
  Doppler Cardíaco:   DOP_CARDIACO (servicio),   DOP_CARDIACO_LECHO
  ETE:                ECO_TE (consultorio),       ECO_TE_QUIROFANO
  Eco especiales:     ECO_STRESS, ECO_BURBUJA

Corrección de tarifas placeholder existentes con valores reales.
Backfill: marca estudios Doppler/ECOCAR con tiene_contexto_ubicacion=True.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from liquidacion.models import GrupoTarifario, TarifaGrupoTarifario, Estudios


# ---------------------------------------------------------------------------
# Definición de grupos nuevos y tarifas reales (Abril 2026)
# ---------------------------------------------------------------------------
GRUPOS_NUEVOS = [
    # (codigo, nombre, modalidad)
    ('DOP_PERIFERICO',       'Doppler Periférico en Servicio',    'DOP'),
    ('DOP_PERIFERICO_LECHO', 'Doppler Periférico en Lecho',       'DOP'),
    ('DOP_CARDIACO',         'Doppler Cardíaco en Servicio',      'DOP'),
    ('DOP_CARDIACO_LECHO',   'Doppler Cardíaco en Lecho',         'DOP'),
    ('ECO_TE',               'Ecocardiograma Transesofágico',     'ECOCAR'),
    ('ECO_TE_QUIROFANO',     'Ecocardiograma Transesofágico en Quirófano', 'ECOCAR'),
    ('ECO_STRESS',           'Ecostress / Ecostress con Dobutamina', 'ECOCAR'),
    ('ECO_BURBUJA',          'Ecocardiograma con Contraste (Burbuja)', 'ECOCAR'),
]

# Tarifas reales: (codigo_grupo, precio_cober, precio_otras_os)
# Valores de la Matriz Tarifaria Abril 2026
TARIFAS_NUEVAS = [
    ('DOP_PERIFERICO',       Decimal('9400.00'),  Decimal('11000.00')),
    ('DOP_PERIFERICO_LECHO', Decimal('11600.00'), Decimal('13200.00')),
    ('DOP_CARDIACO',         Decimal('11600.00'), Decimal('13200.00')),
    ('DOP_CARDIACO_LECHO',   Decimal('13200.00'), Decimal('15400.00')),
    ('ECO_TE',               Decimal('27500.00'), Decimal('33000.00')),
    ('ECO_TE_QUIROFANO',     Decimal('49500.00'), Decimal('55000.00')),
    ('ECO_STRESS',           Decimal('27500.00'), Decimal('27500.00')),
    ('ECO_BURBUJA',          Decimal('26500.00'), Decimal('30500.00')),
]

# Corrección de tarifas existentes (placeholders → valores reales)
# Los grupos ya existen pero sus tarifas tienen valores de prueba
TARIFAS_CORRECCION = [
    ('TOM_SIMPLE',        Decimal('4400.00'),  Decimal('4400.00')),
    ('TOM_CONTRASTE',     Decimal('5500.00'),  Decimal('5500.00')),
    ('TOM_SIN_CONTRASTE', Decimal('4400.00'),  Decimal('4400.00')),
    ('TOM_ANGIO',         Decimal('7700.00'),  Decimal('7700.00')),
    ('RES_SIMPLE',        Decimal('5500.00'),  Decimal('5500.00')),
    ('RES_ANGIO',         Decimal('8800.00'),  Decimal('8800.00')),
    ('RAD_RADIOGRAFIA',   Decimal('1650.00'),  Decimal('1650.00')),
    ('MAM_MAMOGRAFIA',    Decimal('1650.00'),  Decimal('1650.00')),
    ('ECO_DOPPLER',       Decimal('9400.00'),  Decimal('11000.00')),  # fallback genérico
    ('ECO_ECOGRAFIA',     Decimal('8500.00'),  Decimal('10000.00')),
]

# Patrones para backfill tiene_contexto_ubicacion=True
# Estudios con tipo DOP o ECOCAR que NO son ecografías generales
TIPOS_CON_CONTEXTO = {'DOP', 'ECOCAR'}


class Command(BaseCommand):
    help = 'Carga grupos tarifarios con contexto y tarifas reales (Abril 2026)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo muestra qué haría sin guardar nada')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hoy = timezone.now().date()

        self.stdout.write('\n' + '='*70)
        self.stdout.write('CARGA DE GRUPOS TARIFARIOS CON CONTEXTO — ABRIL 2026')
        self.stdout.write('='*70 + '\n')

        with transaction.atomic():
            # 1. Crear grupos nuevos
            self.stdout.write('\n[1] CREANDO GRUPOS NUEVOS...')
            for codigo, nombre, modalidad in GRUPOS_NUEVOS:
                grupo, created = GrupoTarifario.objects.get_or_create(
                    codigo=codigo,
                    defaults={'nombre': nombre, 'modalidad': modalidad, 'activo': True}
                )
                estado = 'CREADO' if created else 'YA EXISTE'
                self.stdout.write(f'   {codigo:25} [{estado}]')

            # 2. Cargar tarifas para grupos nuevos
            self.stdout.write('\n[2] CARGANDO TARIFAS NUEVAS...')
            for codigo, precio_cober, precio_otras_os in TARIFAS_NUEVAS:
                try:
                    grupo = GrupoTarifario.objects.get(codigo=codigo)
                except GrupoTarifario.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'   GRUPO NO ENCONTRADO: {codigo}'))
                    continue

                # Cerrar tarifa anterior si existe abierta
                TarifaGrupoTarifario.objects.filter(
                    grupo_tarifario=grupo,
                    vigencia_hasta__isnull=True
                ).update(vigencia_hasta=hoy)

                if not dry_run:
                    TarifaGrupoTarifario.objects.create(
                        grupo_tarifario=grupo,
                        vigencia_desde=hoy,
                        vigencia_hasta=None,
                        precio_cober=precio_cober,
                        precio_otras_os=precio_otras_os,
                    )
                self.stdout.write(f'   {codigo:25} COBER=${precio_cober:8} OTRAS_OS=${precio_otras_os:8}')

            # 3. Corregir tarifas existentes con valores reales
            self.stdout.write('\n[3] CORRIGIENDO TARIFAS EXISTENTES...')
            for codigo, precio_cober, precio_otras_os in TARIFAS_CORRECCION:
                try:
                    grupo = GrupoTarifario.objects.get(codigo=codigo)
                except GrupoTarifario.DoesNotExist:
                    self.stdout.write(f'   SALTADO (no existe): {codigo}')
                    continue

                tarifa_actual = grupo.get_tarifa_vigente(fecha=hoy)

                if tarifa_actual and tarifa_actual.precio_cober == precio_cober and tarifa_actual.precio_otras_os == precio_otras_os:
                    self.stdout.write(f'   {codigo:25} SIN CAMBIO (ya correcto)')
                    continue

                # Cerrar la actual
                TarifaGrupoTarifario.objects.filter(
                    grupo_tarifario=grupo,
                    vigencia_hasta__isnull=True
                ).update(vigencia_hasta=hoy)

                if not dry_run:
                    TarifaGrupoTarifario.objects.create(
                        grupo_tarifario=grupo,
                        vigencia_desde=hoy,
                        vigencia_hasta=None,
                        precio_cober=precio_cober,
                        precio_otras_os=precio_otras_os,
                    )
                self.stdout.write(f'   {codigo:25} COBER=${precio_cober:8} OTRAS_OS=${precio_otras_os:8}  ← CORREGIDO')

            # 4. Backfill tiene_contexto_ubicacion en estudios Doppler/ECOCAR
            self.stdout.write('\n[4] MARCANDO ESTUDIOS CON CONTEXTO DE UBICACIÓN...')
            estudios_con_contexto = Estudios.objects.filter(tipo__in=TIPOS_CON_CONTEXTO)
            count = estudios_con_contexto.count()
            if not dry_run:
                estudios_con_contexto.update(tiene_contexto_ubicacion=True)
            self.stdout.write(f'   {count} estudios (DOP + ECOCAR) marcados con tiene_contexto_ubicacion=True')

            if dry_run:
                self.stdout.write(self.style.WARNING('\n   [DRY-RUN] Ningún cambio guardado.'))
                raise Exception('dry-run rollback')

        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('✓ Carga completada exitosamente'))
        self.stdout.write('='*70 + '\n')
