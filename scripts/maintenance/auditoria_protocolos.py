"""
Script de auditoría completa del sistema de protocolos.
Ejecutar: python auditoria_protocolos.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from protocolos.models import Modalidad, RegionAnatomica, Tag, Protocolo, FaseAdquisicion
from django.db.models import Count, Q
from collections import defaultdict


def print_header(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_section(title):
    print(f"\n{'─'*80}")
    print(f"  {title}")
    print(f"{'─'*80}")


def auditoria_completa():
    print_header("🔍 AUDITORÍA COMPLETA DEL SISTEMA DE PROTOCOLOS")
    
    # ============================================================
    # 1. ESTADÍSTICAS GENERALES
    # ============================================================
    print_section("1. ESTADÍSTICAS GENERALES")
    
    total_modalidades = Modalidad.objects.count()
    total_regiones = RegionAnatomica.objects.count()
    total_tags = Tag.objects.count()
    total_protocolos = Protocolo.objects.count()
    total_fases = FaseAdquisicion.objects.count()
    
    protocolos_activos = Protocolo.objects.filter(es_activo=True).count()
    protocolos_inactivos = Protocolo.objects.filter(es_activo=False).count()
    
    print(f"📊 Modalidades: {total_modalidades}")
    print(f"📊 Regiones anatómicas: {total_regiones}")
    print(f"📊 Tags: {total_tags}")
    print(f"📊 Protocolos totales: {total_protocolos}")
    print(f"   ├─ Activos: {protocolos_activos}")
    print(f"   └─ Inactivos: {protocolos_inactivos}")
    print(f"📊 Fases de adquisición: {total_fases}")
    
    # ============================================================
    # 2. DETECTAR DUPLICADOS POR NOMBRE
    # ============================================================
    print_section("2. BÚSQUEDA DE PROTOCOLOS DUPLICADOS")
    
    duplicados_nombre = (
        Protocolo.objects
        .values('nombre')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )
    
    if duplicados_nombre.exists():
        print("⚠️  DUPLICADOS ENCONTRADOS:")
        for dup in duplicados_nombre:
            protocolos = Protocolo.objects.filter(nombre=dup['nombre'])
            print(f"\n   Nombre: '{dup['nombre']}' ({dup['count']} copias)")
            for p in protocolos:
                print(f"   ├─ ID {p.id}: Modalidad={p.modalidad.codigo}, Región={p.region.codigo}, Activo={p.es_activo}")
    else:
        print("✅ No se encontraron protocolos duplicados por nombre")
    
    # ============================================================
    # 3. PROTOCOLOS SIMILARES (posibles duplicados semánticos)
    # ============================================================
    print_section("3. PROTOCOLOS CON NOMBRES SIMILARES")
    
    protocolos = Protocolo.objects.all().order_by('nombre')
    nombres_normalizados = defaultdict(list)
    
    for p in protocolos:
        # Normalizar: minúsculas, sin tildes, sin paréntesis
        nombre_norm = (
            p.nombre.lower()
            .replace('á', 'a').replace('é', 'e').replace('í', 'i')
            .replace('ó', 'o').replace('ú', 'u')
            .replace('(', '').replace(')', '')
            .replace('-', ' ').strip()
        )
        nombres_normalizados[nombre_norm].append(p)
    
    similares_encontrados = False
    for nombre_norm, lista_protocolos in nombres_normalizados.items():
        if len(lista_protocolos) > 1:
            similares_encontrados = True
            print(f"\n⚠️  Posibles similares (normalizado: '{nombre_norm}'):")
            for p in lista_protocolos:
                print(f"   ├─ ID {p.id}: '{p.nombre}'")
    
    if not similares_encontrados:
        print("✅ No se encontraron protocolos con nombres similares")
    
    # ============================================================
    # 4. FASES HUÉRFANAS O MAL ASOCIADAS
    # ============================================================
    print_section("4. INTEGRIDAD DE FASES DE ADQUISICIÓN")
    
    # Fases sin protocolo (no deberían existir por FK)
    fases_huerfanas = FaseAdquisicion.objects.filter(protocolo__isnull=True)
    if fases_huerfanas.exists():
        print(f"❌ FASES HUÉRFANAS ENCONTRADAS: {fases_huerfanas.count()}")
        for fase in fases_huerfanas:
            print(f"   ├─ ID {fase.id}: {fase.nombre}")
    else:
        print("✅ No hay fases huérfanas")
    
    # Protocolos sin fases
    protocolos_sin_fases = Protocolo.objects.annotate(
        num_fases=Count('fases')
    ).filter(num_fases=0)
    
    if protocolos_sin_fases.exists():
        print(f"\n⚠️  PROTOCOLOS SIN FASES: {protocolos_sin_fases.count()}")
        for p in protocolos_sin_fases:
            print(f"   ├─ ID {p.id}: '{p.nombre}' ({p.modalidad.codigo})")
    else:
        print("✅ Todos los protocolos tienen al menos una fase")
    
    # Verificar orden de fases (deben ser secuenciales desde 1)
    print("\n🔍 Verificando secuencia de órdenes de fases...")
    problemas_orden = False
    for protocolo in Protocolo.objects.all():
        fases = list(protocolo.fases.all().order_by('orden'))
        ordenes = [f.orden for f in fases]
        esperado = list(range(1, len(fases) + 1))
        
        if ordenes != esperado:
            problemas_orden = True
            print(f"   ⚠️  Protocolo '{protocolo.nombre}' (ID {protocolo.id})")
            print(f"      Órdenes encontrados: {ordenes}")
            print(f"      Órdenes esperados: {esperado}")
    
    if not problemas_orden:
        print("✅ Todas las secuencias de fases son correctas")
    
    # ============================================================
    # 5. TAGS MAL ASIGNADOS O VACÍOS
    # ============================================================
    print_section("5. VERIFICACIÓN DE TAGS")
    
    # Tags sin protocolos
    tags_vacios = Tag.objects.annotate(
        num_protocolos=Count('protocolos')
    ).filter(num_protocolos=0)
    
    if tags_vacios.exists():
        print(f"⚠️  TAGS SIN PROTOCOLOS: {tags_vacios.count()}")
        for tag in tags_vacios:
            print(f"   ├─ '{tag.nombre}'")
    else:
        print("✅ Todos los tags están en uso")
    
    # Protocolos sin tags
    protocolos_sin_tags = Protocolo.objects.annotate(
        num_tags=Count('tags')
    ).filter(num_tags=0)
    
    if protocolos_sin_tags.exists():
        print(f"\n⚠️  PROTOCOLOS SIN TAGS: {protocolos_sin_tags.count()}")
        for p in protocolos_sin_tags:
            print(f"   ├─ ID {p.id}: '{p.nombre}'")
    else:
        print("✅ Todos los protocolos tienen tags asignados")
    
    # ============================================================
    # 6. CONSISTENCIA DE CONTRASTE
    # ============================================================
    print_section("6. CONSISTENCIA DE CONTRASTE EV")
    
    # Protocolos con contraste EV pero todas las fases SIN contraste
    inconsistencias_contraste = []
    for protocolo in Protocolo.objects.filter(requiere_contraste_ev=True):
        fases_con_contraste = protocolo.fases.exclude(tipo_fase='SIN').count()
        if fases_con_contraste == 0:
            inconsistencias_contraste.append(protocolo)
    
    if inconsistencias_contraste:
        print(f"⚠️  INCONSISTENCIAS DE CONTRASTE: {len(inconsistencias_contraste)}")
        for p in inconsistencias_contraste:
            print(f"   ├─ ID {p.id}: '{p.nombre}' (requiere_contraste_ev=True pero solo tiene fases SIN)")
    else:
        print("✅ Consistencia de contraste correcta")
    
    # Protocolos SIN contraste EV pero con fases CON contraste
    inconsistencias_contraste2 = []
    for protocolo in Protocolo.objects.filter(requiere_contraste_ev=False):
        fases_con_contraste = protocolo.fases.exclude(tipo_fase='SIN').count()
        if fases_con_contraste > 0:
            inconsistencias_contraste2.append(protocolo)
    
    if inconsistencias_contraste2:
        print(f"\n⚠️  INCONSISTENCIAS DE CONTRASTE (2): {len(inconsistencias_contraste2)}")
        for p in inconsistencias_contraste2:
            tipos_fases = list(p.fases.values_list('tipo_fase', flat=True))
            print(f"   ├─ ID {p.id}: '{p.nombre}' (requiere_contraste_ev=False pero tiene fases: {tipos_fases})")
    else:
        print("✅ No hay protocolos sin contraste con fases contrastadas")
    
    # ============================================================
    # 7. DELAYS INCONSISTENTES
    # ============================================================
    print_section("7. VERIFICACIÓN DE DELAYS")
    
    print("🔍 Revisando delays por tipo de fase...")
    
    # SIN contraste debería tener delay=None
    fases_sin_con_delay = FaseAdquisicion.objects.filter(
        tipo_fase='SIN',
        delay_segundos__isnull=False
    )
    
    if fases_sin_con_delay.exists():
        print(f"⚠️  FASES SIN CONTRASTE CON DELAY: {fases_sin_con_delay.count()}")
        for fase in fases_sin_con_delay:
            print(f"   ├─ Protocolo: '{fase.protocolo.nombre}' - Fase: '{fase.nombre}' - Delay: {fase.delay_segundos}s")
    else:
        print("✅ Todas las fases SIN contraste tienen delay=None")
    
    # Fases tardías deberían tener delay alto (>300s)
    fases_tard_delay_bajo = FaseAdquisicion.objects.filter(
        tipo_fase='TARD',
        delay_segundos__lt=300
    )
    
    if fases_tard_delay_bajo.exists():
        print(f"\n⚠️  FASES TARDÍAS CON DELAY BAJO: {fases_tard_delay_bajo.count()}")
        for fase in fases_tard_delay_bajo:
            print(f"   ├─ Protocolo: '{fase.protocolo.nombre}' - Delay: {fase.delay_segundos}s (esperado >300s)")
    else:
        print("✅ Todas las fases tardías tienen delays apropiados")
    
    # ============================================================
    # 8. LISTADO COMPLETO DE PROTOCOLOS
    # ============================================================
    print_section("8. LISTADO COMPLETO DE PROTOCOLOS")
    
    for protocolo in Protocolo.objects.all().order_by('modalidad__codigo', 'region__codigo', 'nombre'):
        num_fases = protocolo.fases.count()
        num_tags = protocolo.tags.count()
        estado = "✅ Activo" if protocolo.es_activo else "⚪ Inactivo"
        contraste = "💉 Con contraste" if protocolo.requiere_contraste_ev else "🚫 Sin contraste"
        
        print(f"\n{estado} ID {protocolo.id}: {protocolo.nombre}")
        print(f"   ├─ Modalidad: {protocolo.modalidad.codigo} | Región: {protocolo.region.nombre}")
        print(f"   ├─ {contraste}")
        print(f"   ├─ Fases: {num_fases}")
        
        for fase in protocolo.fases.all().order_by('orden'):
            delay_str = f"{fase.delay_segundos}s" if fase.delay_segundos else "None"
            print(f"   │  └─ Orden {fase.orden}: {fase.nombre} ({fase.tipo_fase}) - Delay: {delay_str}")
        
        if num_tags > 0:
            tags_str = ", ".join([tag.nombre for tag in protocolo.tags.all()])
            print(f"   └─ Tags: {tags_str}")
        else:
            print(f"   └─ ⚠️  Sin tags")
    
    # ============================================================
    # 9. RESUMEN FINAL
    # ============================================================
    print_header("📋 RESUMEN DE AUDITORÍA")
    
    issues_encontrados = []
    
    if duplicados_nombre.exists():
        issues_encontrados.append(f"❌ {duplicados_nombre.count()} protocolos duplicados por nombre")
    
    if similares_encontrados:
        issues_encontrados.append("⚠️  Protocolos con nombres similares encontrados")
    
    if protocolos_sin_fases.exists():
        issues_encontrados.append(f"⚠️  {protocolos_sin_fases.count()} protocolos sin fases")
    
    if problemas_orden:
        issues_encontrados.append("⚠️  Problemas en la secuencia de órdenes de fases")
    
    if tags_vacios.exists():
        issues_encontrados.append(f"⚠️  {tags_vacios.count()} tags sin uso")
    
    if protocolos_sin_tags.exists():
        issues_encontrados.append(f"⚠️  {protocolos_sin_tags.count()} protocolos sin tags")
    
    if inconsistencias_contraste:
        issues_encontrados.append(f"⚠️  {len(inconsistencias_contraste)} inconsistencias de contraste (tipo 1)")
    
    if inconsistencias_contraste2:
        issues_encontrados.append(f"⚠️  {len(inconsistencias_contraste2)} inconsistencias de contraste (tipo 2)")
    
    if fases_sin_con_delay.exists():
        issues_encontrados.append(f"⚠️  {fases_sin_con_delay.count()} fases SIN con delay incorrecto")
    
    if fases_tard_delay_bajo.exists():
        issues_encontrados.append(f"⚠️  {fases_tard_delay_bajo.count()} fases TARD con delay bajo")
    
    if issues_encontrados:
        print("⚠️  ISSUES ENCONTRADOS:\n")
        for issue in issues_encontrados:
            print(f"   {issue}")
        print(f"\n   Total: {len(issues_encontrados)} problemas detectados")
    else:
        print("✅ ¡SISTEMA EN PERFECTO ESTADO!")
        print("   No se encontraron problemas de integridad")
    
    print(f"\n{'='*80}\n")


if __name__ == '__main__':
    auditoria_completa()
