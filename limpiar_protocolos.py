"""
Script de limpieza y corrección de la base de datos de protocolos.
Ejecutar: python limpiar_protocolos.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from protocolos.models import Modalidad, RegionAnatomica, Tag, Protocolo, FaseAdquisicion


def print_header(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_section(title):
    print(f"\n{'─'*80}")
    print(f"  {title}")
    print(f"{'─'*80}")


def limpiar_protocolos():
    print_header("🧹 LIMPIEZA DE BASE DE DATOS DE PROTOCOLOS")
    
    acciones_realizadas = []
    
    # ============================================================
    # 1. ELIMINAR PROTOCOLO DUPLICADO URO-TC HEMATURIA (ID 23)
    # ============================================================
    print_section("1. ELIMINAR PROTOCOLO DUPLICADO URO-TC")
    
    # El ID 23 es la versión vieja (urograma por TC, 3 fases)
    # El ID 25 es la versión correcta (urograma CT, 2 fases)
    
    protocolo_viejo = Protocolo.objects.filter(
        id=23,
        nombre='Uro-TC hematuria (urograma por TC)'
    ).first()
    
    if protocolo_viejo:
        print(f"⚠️  Encontrado protocolo duplicado para eliminar:")
        print(f"   ID: {protocolo_viejo.id}")
        print(f"   Nombre: {protocolo_viejo.nombre}")
        print(f"   Fases: {protocolo_viejo.fases.count()}")
        
        # Eliminar fases asociadas (por FK cascade se borran automáticamente)
        num_fases = protocolo_viejo.fases.count()
        
        # Eliminar el protocolo
        protocolo_viejo.delete()
        print(f"✅ Protocolo ID 23 eliminado (junto con {num_fases} fases)")
        acciones_realizadas.append(f"Eliminado protocolo duplicado ID 23 (Uro-TC hematuria viejo)")
    else:
        print("✅ No se encontró el protocolo duplicado ID 23 (ya fue eliminado o no existe)")
    
    # ============================================================
    # 2. AGREGAR FASES A PROTOCOLOS SIN FASES
    # ============================================================
    print_section("2. PROTOCOLOS SIN FASES")
    
    # ID 13: Ecografía abdominal completa
    eco_abdomen = Protocolo.objects.filter(id=13, nombre='Ecografía abdominal completa').first()
    if eco_abdomen and eco_abdomen.fases.count() == 0:
        print(f"⚠️  Protocolo ID 13 'Ecografía abdominal completa' sin fases")
        print("   → Este protocolo es de US, no requiere fases específicas de contraste")
        print("   → Se puede dejar sin fases o agregar fase única 'Estudio basal'")
        print("   → ACCIÓN: Se dejará sin fases (US no tiene fases de contraste)")
        acciones_realizadas.append("Protocolo US ID 13 sin fases (correcto, no requiere)")
    
    # ID 14: Radiografía de columna lumbosacra
    rx_columna = Protocolo.objects.filter(id=14, nombre='Radiografía de columna lumbosacra').first()
    if rx_columna and rx_columna.fases.count() == 0:
        print(f"\n⚠️  Protocolo ID 14 'Radiografía de columna lumbosacra' sin fases")
        print("   → Este protocolo es de RX, no requiere fases específicas")
        print("   → ACCIÓN: Se dejará sin fases (RX no tiene fases de contraste)")
        acciones_realizadas.append("Protocolo RX ID 14 sin fases (correcto, no requiere)")
    
    # ============================================================
    # 3. TAGS SIN USO
    # ============================================================
    print_section("3. LIMPIAR TAGS SIN USO")
    
    tags_vacios = Tag.objects.annotate(
        num_protocolos=Count('protocolos')
    ).filter(num_protocolos=0)
    
    if tags_vacios.exists():
        print(f"⚠️  Encontrados {tags_vacios.count()} tags sin protocolos asociados:")
        for tag in tags_vacios:
            print(f"   ├─ '{tag.nombre}'")
        
        print(f"\n❓ ¿Eliminar estos tags? (s/n): ", end='')
        respuesta = input().strip().lower()
        
        if respuesta == 's':
            nombres_eliminados = list(tags_vacios.values_list('nombre', flat=True))
            tags_vacios.delete()
            print(f"✅ {len(nombres_eliminados)} tags eliminados")
            acciones_realizadas.append(f"Eliminados {len(nombres_eliminados)} tags sin uso: {', '.join(nombres_eliminados)}")
        else:
            print("⏭️  Tags sin uso conservados")
    else:
        print("✅ No hay tags sin uso")
    
    # ============================================================
    # 4. AGREGAR TAGS A PROTOCOLOS SIN TAGS
    # ============================================================
    print_section("4. PROTOCOLOS SIN TAGS")
    
    # ID 14: Radiografía de columna lumbosacra
    if rx_columna and rx_columna.tags.count() == 0:
        print(f"⚠️  Protocolo ID 14 'Radiografía de columna lumbosacra' sin tags")
        
        # Buscar o crear tags apropiados
        tag_trauma, _ = Tag.objects.get_or_create(nombre='Trauma')
        tag_dolor_lumbar, _ = Tag.objects.get_or_create(nombre='Dolor lumbar')
        
        rx_columna.tags.set([tag_trauma, tag_dolor_lumbar])
        print(f"✅ Tags agregados: Trauma, Dolor lumbar")
        acciones_realizadas.append("Agregados tags a RX columna lumbosacra (Trauma, Dolor lumbar)")
    
    # ============================================================
    # 5. CORRECCIÓN DE FASE TARDÍA CON DELAY INCORRECTO (URO-TC ID 23)
    # ============================================================
    print_section("5. VERIFICAR DELAYS EN FASES")
    
    # Ya eliminamos el protocolo ID 23, pero verificamos el ID 25
    uro_tc_nuevo = Protocolo.objects.filter(id=25).first()
    if uro_tc_nuevo:
        fase_tardia = uro_tc_nuevo.fases.filter(tipo_fase='TARD').first()
        if fase_tardia and fase_tardia.delay_segundos != 600:
            print(f"⚠️  Fase tardía del protocolo ID 25 tiene delay incorrecto: {fase_tardia.delay_segundos}s")
            print(f"   Corrigiendo a 600s (10 minutos)...")
            fase_tardia.delay_segundos = 600
            fase_tardia.save()
            print(f"✅ Delay corregido")
            acciones_realizadas.append("Corregido delay de fase tardía en Uro-TC ID 25")
        else:
            print(f"✅ Delay de fase tardía en Uro-TC ID 25 correcto: {fase_tardia.delay_segundos if fase_tardia else 'N/A'}s")
    
    # ============================================================
    # 6. RESUMEN FINAL
    # ============================================================
    print_header("📋 RESUMEN DE LIMPIEZA")
    
    if acciones_realizadas:
        print("✅ ACCIONES REALIZADAS:\n")
        for i, accion in enumerate(acciones_realizadas, 1):
            print(f"   {i}. {accion}")
        print(f"\n   Total: {len(acciones_realizadas)} acciones completadas")
    else:
        print("✅ No se realizaron cambios (base de datos ya limpia)")
    
    # Estadísticas finales
    print("\n📊 ESTADÍSTICAS FINALES:")
    print(f"   • Protocolos activos: {Protocolo.objects.filter(es_activo=True).count()}")
    print(f"   • Total de fases: {FaseAdquisicion.objects.count()}")
    print(f"   • Tags en uso: {Tag.objects.annotate(num_protocolos=Count('protocolos')).filter(num_protocolos__gt=0).count()}")
    
    print(f"\n{'='*80}\n")


def confirmar_cambios():
    print("⚠️  ADVERTENCIA: Esta acción modificará la base de datos.")
    print("   Se recomienda hacer un backup antes de continuar.")
    print(f"\n¿Continuar con la limpieza? (s/n): ", end='')
    respuesta = input().strip().lower()
    return respuesta == 's'


if __name__ == '__main__':
    from django.db.models import Count
    
    if confirmar_cambios():
        limpiar_protocolos()
    else:
        print("\n❌ Operación cancelada por el usuario\n")
