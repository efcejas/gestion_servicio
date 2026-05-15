from django.core.management.base import BaseCommand
from liquidacion.models import TarifaGrupoTarifario


class Command(BaseCommand):
    help = 'Lista TODAS las tarifas cargadas sin filtros'

    def handle(self, *args, **options):
        print("\n" + "="*100)
        print("TODAS LAS TARIFAS CARGADAS (sin filtro de vigencia)")
        print("="*100 + "\n")

        tarifas = TarifaGrupoTarifario.objects.all().select_related('grupo_tarifario').order_by('grupo_tarifario__codigo', 'vigencia_desde')
        
        if not tarifas.exists():
            print("❌ NO HAY TARIFAS CARGADAS")
            return

        for t in tarifas:
            print(f"\n{t.grupo_tarifario.codigo:20} | COBER: ${t.precio_cober:12} | OTRAS_OS: ${t.precio_otras_os:12}")
            print(f"  Vigencia: {t.vigencia_desde} → {t.vigencia_hasta}")
            print(f"  ID: {t.id}")
        
        print(f"\n{'='*100}")
        print(f"TOTAL TARIFAS: {tarifas.count()}")
        print(f"{'='*100 + '\n'}")
