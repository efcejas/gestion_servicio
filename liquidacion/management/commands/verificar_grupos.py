from django.core.management.base import BaseCommand
from liquidacion.models import Estudios, GrupoTarifario, TarifaGrupoTarifario
from django.utils import timezone


class Command(BaseCommand):
    help = 'Verifica el estado de grupos tarifarios y estudios clasificados'

    def handle(self, *args, **options):
        print("\n" + "="*70)
        print("ESTADO DE LIQUIDACION - GRUPOS TARIFARIOS")
        print("="*70)

        # 1. Grupos
        print(f"\n1. GRUPOS TARIFARIOS CARGADOS: {GrupoTarifario.objects.count()}")
        for g in GrupoTarifario.objects.all().order_by('codigo'):
            print(f"   - {g.codigo:20} | {g.nombre}")

        # 2. Estudios
        asignados = Estudios.objects.filter(grupo_tarifario__isnull=False).count()
        sin_grupo = Estudios.objects.filter(grupo_tarifario__isnull=True).count()
        total = Estudios.objects.count()
        porc = (100 * asignados / total) if total > 0 else 0

        print(f"\n2. ESTUDIOS:")
        print(f"   Total: {total}")
        print(f"   Con grupo: {asignados} ({porc:.1f}%)")
        print(f"   Sin grupo: {sin_grupo}")

        # 3. Distribucion por grupo
        print(f"\n3. DISTRIBUCION POR GRUPO:")
        from django.db.models import Count
        dist = Estudios.objects.filter(grupo_tarifario__isnull=False)\
            .values_list('grupo_tarifario__codigo')\
            .annotate(cnt=Count('id'))\
            .order_by('-cnt')
        for codigo, cnt in dist:
            print(f"   {codigo:20} | {cnt:3} estudios")

        # 4. Ejemplos
        print(f"\n4. EJEMPLOS DE ESTUDIOS CON GRUPO:")
        ejemplos = Estudios.objects.filter(grupo_tarifario__isnull=False)\
            .select_related('grupo_tarifario')[:5]
        for e in ejemplos:
            nombre_short = e.nombre[:45] if e.nombre else "SIN NOMBRE"
            print(f"   {e.tipo:6} | {nombre_short:45} | {e.grupo_tarifario.codigo}")

        # 5. Tarifas vigentes
        hoy = timezone.now().date()
        vigentes = TarifaGrupoTarifario.objects.filter(vigencia_desde__lte=hoy)\
            .exclude(vigencia_hasta__lt=hoy)
        print(f"\n5. TARIFAS VIGENTES HOY ({hoy}): {vigentes.count()}")
        print(f"   Total tarifas cargadas: {TarifaGrupoTarifario.objects.count()}")
        for t in vigentes[:3]:
            print(f"   {t.grupo_tarifario.codigo:20} | COBER: ${t.precio_cober:8} | OTRAS_OS: ${t.precio_otras_os:8}")

        print("\n" + "="*70 + "\n")
