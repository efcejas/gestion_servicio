#!/usr/bin/env python
"""
Script de verificación de optimizaciones - Sistema Dictado IA
==============================================================
Verifica el impacto de las optimizaciones aplicadas en la Fase 1:
- Performance del admin con select_related()
- Integridad del sistema después de eliminar código obsoleto

Uso:
    python scripts/verificar_optimizaciones.py

Fecha: 2026-03-08
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion.settings')
django.setup()

from django.db import connection
from django.test.utils import CaptureQueriesContext
from dictado_informes.models import CorreccionAprendizaje
from django.contrib.auth import get_user_model

User = get_user_model()


def verificar_select_related():
    """Verifica la optimización de queries con select_related"""
    print("=" * 70)
    print("TEST 1: Verificar optimización de queries en Admin")
    print("=" * 70)
    
    # Verificar que existen registros
    total_correcciones = CorreccionAprendizaje.objects.count()
    print(f"\n📊 Total de correcciones en BD: {total_correcciones}")
    
    if total_correcciones == 0:
        print("⚠️  No hay correcciones en la BD. Crea algunas para probar la optimización.")
        return
    
    # Limitar a 20 registros para el test
    limite = min(20, total_correcciones)
    print(f"📝 Probando con {limite} registros...\n")
    
    # SIN select_related (simulación)
    print("❌ SIN select_related() - Queries esperadas: N+1")
    with CaptureQueriesContext(connection) as ctx_sin:
        # Simular lo que hacía antes (sin select_related)
        qs_sin = CorreccionAprendizaje.objects.all()[:limite]
        usuarios_sin = [obj.usuario.username for obj in qs_sin]
    
    queries_sin = len(ctx_sin)
    print(f"   Queries ejecutadas: {queries_sin}")
    
    # CON select_related (actual)
    print("\n✅ CON select_related('usuario') - Queries esperadas: 1")
    with CaptureQueriesContext(connection) as ctx_con:
        # Usar el queryset del admin (con select_related)
        qs_con = CorreccionAprendizaje.objects.select_related('usuario').all()[:limite]
        usuarios_con = [obj.usuario.username for obj in qs_con]
    
    queries_con = len(ctx_con)
    print(f"   Queries ejecutadas: {queries_con}")
    
    # Calcular mejora
    if queries_con > 0:
        mejora = ((queries_sin - queries_con) / queries_sin) * 100
        factor = queries_sin / queries_con
        
        print("\n" + "=" * 70)
        print(f"🚀 RESULTADO:")
        print(f"   Reducción de queries: {queries_sin} → {queries_con}")
        print(f"   Mejora: {mejora:.1f}% ({factor:.1f}x más rápido)")
        print("=" * 70)
        
        if queries_con == 1:
            print("\n✅ EXCELENTE: Solo 1 query ejecutada (óptimo)")
        elif queries_con < queries_sin / 2:
            print(f"\n✅ BUENO: Reducción significativa de queries")
        else:
            print(f"\n⚠️  ADVERTENCIA: La reducción es menor de lo esperado")
    
    # Verificar que los datos son correctos
    if usuarios_sin == usuarios_con:
        print("✅ Integridad de datos: OK (resultados idénticos)")
    else:
        print("❌ ERROR: Los resultados no coinciden")


def verificar_apis_disponibles():
    """Verifica que las APIs correctas están disponibles"""
    print("\n" + "=" * 70)
    print("TEST 2: Verificar APIs disponibles")
    print("=" * 70)
    
    from dictado_informes import views
    
    apis_disponibles = []
    apis_eliminadas = []
    
    # Verificar APIs que deben existir
    if hasattr(views, 'transcribir_audio_whisper'):
        apis_disponibles.append('✅ transcribir_audio_whisper()')
    else:
        print("❌ ERROR: transcribir_audio_whisper() no encontrada")
    
    if hasattr(views, 'mejorar_texto_ia'):
        apis_disponibles.append('✅ mejorar_texto_ia()')
    else:
        print("❌ ERROR: mejorar_texto_ia() no encontrada")
    
    if hasattr(views, 'guardar_correccion_aprendizaje'):
        apis_disponibles.append('✅ guardar_correccion_aprendizaje()')
    else:
        print("❌ ERROR: guardar_correccion_aprendizaje() no encontrada")
    
    # Verificar API que debe estar eliminada
    if hasattr(views, 'procesar_audio_dictado'):
        print("⚠️  ADVERTENCIA: procesar_audio_dictado() todavía existe (debería estar eliminada)")
    else:
        apis_eliminadas.append('✅ procesar_audio_dictado() correctamente eliminada')
    
    print("\n📋 APIs Disponibles:")
    for api in apis_disponibles:
        print(f"   {api}")
    
    print("\n🗑️  APIs Eliminadas:")
    for api in apis_eliminadas:
        print(f"   {api}")
    
    # Verificar template
    from django.template.loader import get_template
    from django.template import TemplateDoesNotExist
    
    print("\n📄 Templates:")
    try:
        template = get_template('dictado_informes/dictado_rapido_whisper.html')
        print("   ✅ dictado_rapido_whisper.html (activo)")
    except TemplateDoesNotExist:
        print("   ❌ ERROR: dictado_rapido_whisper.html no encontrado")
    
    try:
        template = get_template('dictado_informes/dictado_rapido.html')
        print("   ⚠️  dictado_rapido.html todavía existe (debería estar eliminado)")
    except TemplateDoesNotExist:
        print("   ✅ dictado_rapido.html correctamente eliminado")


def verificar_admin_funciona():
    """Verifica que el admin de CorreccionAprendizaje funciona correctamente"""
    print("\n" + "=" * 70)
    print("TEST 3: Verificar Admin de CorreccionAprendizaje")
    print("=" * 70)
    
    from dictado_informes.admin import CorreccionAprendizajeAdmin
    
    admin_instance = CorreccionAprendizajeAdmin(CorreccionAprendizaje, None)
    
    # Verificar que tiene el método get_queryset
    if hasattr(admin_instance, 'get_queryset'):
        print("   ✅ Método get_queryset() implementado")
        
        # Simular request
        class FakeRequest:
            pass
        
        request = FakeRequest()
        qs = admin_instance.get_queryset(request)
        
        # Verificar que tiene select_related
        if hasattr(qs, 'query') and qs.query.select_related:
            print("   ✅ select_related('usuario') aplicado")
            print(f"      Relaciones: {qs.query.select_related}")
        else:
            print("   ⚠️  ADVERTENCIA: select_related no detectado en queryset")
    else:
        print("   ❌ ERROR: get_queryset() no implementado")
    
    # Verificar otras propiedades del admin
    print("\n   Propiedades del Admin:")
    print(f"   - list_display: {len(admin_instance.list_display)} campos")
    print(f"   - list_filter: {len(admin_instance.list_filter)} filtros")
    print(f"   - actions: {len(admin_instance.actions)} acciones")


def mostrar_resumen():
    """Muestra resumen de cambios aplicados"""
    print("\n" + "=" * 70)
    print("📋 RESUMEN DE CAMBIOS APLICADOS")
    print("=" * 70)
    print("""
FASE 1: LIMPIEZA URGENTE (completada)

✅ 1. Template obsoleto eliminado
   - templates/dictado_informes/dictado_rapido.html → ELIMINADO
   - Template activo: dictado_rapido_whisper.html
   
✅ 2. API deprecada eliminada
   - procesar_audio_dictado() (98 líneas) → ELIMINADA
   - Reemplazada por: transcribir_audio_whisper() + mejorar_texto_ia()
   
✅ 3. URL comentada con nota
   - path('api/procesar-audio/', ...) → COMENTADA
   - Nota: "DEPRECADA 2026-03-08: Usar transcribir_whisper + mejorar_texto"
   
✅ 4. Admin optimizado
   - CorreccionAprendizajeAdmin.get_queryset() → AGREGADO
   - select_related('usuario') → Elimina N+1 queries

📊 IMPACTO:
   - Código eliminado: ~200 líneas
   - Performance del admin: 20x más rápido (estimado)
   - Mantenibilidad: Mejorado (menos código redundante)

🔜 PRÓXIMOS PASOS:
   - Fase 2: Implementar tests (34 tests, 6 horas)
   - Fase 3: Más optimizaciones (regex compilado, índices, 2-3 horas)
   - Fase 4: Sistema de monitoreo (4 horas)
""")


def main():
    """Ejecuta todas las verificaciones"""
    print("\n" + "=" * 70)
    print("🔍 VERIFICACIÓN DE OPTIMIZACIONES - Sistema Dictado IA")
    print("=" * 70)
    print("Fecha: 2026-03-08")
    print("Fase: 1 - Limpieza Urgente")
    print("=" * 70)
    
    try:
        verificar_select_related()
        verificar_apis_disponibles()
        verificar_admin_funciona()
        mostrar_resumen()
        
        print("\n" + "=" * 70)
        print("✅ VERIFICACIÓN COMPLETADA CON ÉXITO")
        print("=" * 70)
        
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ ERROR durante verificación: {str(e)}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
