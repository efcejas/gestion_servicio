#!/usr/bin/env python
"""Script para verificar el estado de grupos, estudios y tarifas en Heroku."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from liquidacion.models import Estudios, GrupoTarifario, TarifaGrupoTarifario
from django.utils import timezone
from decimal import Decimal

print("\n" + "="*70)
print("ESTADO DE LIQUIDACION - GRUPOS TARIFARIOS")
print("="*70)

print(f"\n1. GRUPOS TARIFARIOS CARGADOS: {GrupoTarifario.objects.count()}")
for g in GrupoTarifario.objects.all().order_by('codigo'):
    print(f"   - {g.codigo:20} | {g.nombre}")

print(f"\n2. TARIFAS CARGADAS: {TarifaGrupoTarifario.objects.count()}")
hoy = timezone.now().date()
vigentes = TarifaGrupoTarifario.objects.filter(vigencia_desde__lte=hoy).exclude(vigencia_hasta__lt=hoy)
print(f"   Vigentes hoy ({hoy}): {vigentes.count()}")

print(f"\n3. ESTUDIOS CON GRUPO TARIFARIO:")
asignados = Estudios.objects.filter(grupo_tarifario__isnull=False).count()
sin_grupo = Estudios.objects.filter(grupo_tarifario__isnull=True).count()
total = Estudios.objects.count()
print(f"   Total: {total} | Con grupo: {asignados} | Sin grupo: {sin_grupo} | Cobertura: {100*asignados/total if total > 0 else 0:.1f}%")

print(f"\n4. DISTRIBUCION POR GRUPO:")
grupos_dist = Estudios.objects.filter(grupo_tarifario__isnull=False).values_list('grupo_tarifario__codigo').annotate(count=django.db.models.Count('id')).order_by('grupo_tarifario__codigo')
for codigo, count in grupos_dist:
    print(f"   {codigo:20} | {count:3} estudios")

print(f"\n5. EJEMPLOS DE ESTUDIOS CON GRUPO:")
ejemplos = Estudios.objects.filter(grupo_tarifario__isnull=False).select_related('grupo_tarifario')[:5]
for e in ejemplos:
    print(f"   {e.tipo:6} | {e.nombre[:45]:45} | {e.grupo_tarifario.codigo}")

print(f"\n6. EJEMPLOS DE TARIFAS VIGENTES:")
for t in vigentes[:3]:
    print(f"   {t.grupo_tarifario.codigo:20} | COBER: ${t.precio_cober:8} | OTRAS_OS: ${t.precio_otras_os:8} (desde {t.vigencia_desde})")

print("\n" + "="*70 + "\n")
