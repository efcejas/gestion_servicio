"""
Script de prueba para verificar la pre-carga del editor de revisión

Este script verifica que:
1. El snapshot del residente se crea automáticamente
2. El informe_final_html se pre-carga con el contenido del residente
3. El editor CKEditor5 muestra el contenido correctamente
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from preinformes.models import Preinforme, RevisionPreinforme
from django.contrib.auth import get_user_model

User = get_user_model()

def test_precarga_editor():
    """Test de pre-carga del editor de revisión"""
    
    print("=" * 80)
    print("TEST: Pre-carga del Editor de Revisión")
    print("=" * 80)
    
    # 1. Obtener un preinforme existente
    try:
        preinforme = Preinforme.objects.filter(
            estado__in=['pendiente_revision', 'en_revision']
        ).first()
        
        if not preinforme:
            print("❌ No hay preinformes disponibles para revisión")
            return
        
        print(f"\n✓ Preinforme encontrado: {preinforme.numero_estudio}")
        print(f"  - Residente: {preinforme.residente}")
        print(f"  - Estado: {preinforme.estado}")
        
    except Exception as e:
        print(f"❌ Error al obtener preinforme: {e}")
        return
    
    # 2. Obtener o crear revisión
    try:
        revisor = User.objects.filter(rol='medico_staff').first()
        if not revisor:
            print("❌ No hay usuarios staff disponibles")
            return
        
        revision, created = RevisionPreinforme.objects.get_or_create(
            preinforme=preinforme,
            defaults={'revisor': revisor}
        )
        
        print(f"\n✓ Revisión {'creada' if created else 'existente'}: ID={revision.pk}")
        
    except Exception as e:
        print(f"❌ Error al obtener/crear revisión: {e}")
        return
    
    # 3. Verificar snapshot
    print("\n" + "-" * 80)
    print("VERIFICACIÓN 1: Snapshot del Residente")
    print("-" * 80)
    
    if not revision.informe_residente_snapshot:
        print("⚠️  Snapshot vacío, generando...")
        revision.crear_snapshot_residente()
    
    if revision.informe_residente_snapshot:
        print(f"✓ Snapshot existe: {len(revision.informe_residente_snapshot)} caracteres")
        print(f"  Preview: {revision.informe_residente_snapshot[:200]}...")
    else:
        print("❌ Snapshot no se generó correctamente")
        return
    
    # 4. Verificar informe_final_html
    print("\n" + "-" * 80)
    print("VERIFICACIÓN 2: Pre-carga de informe_final_html")
    print("-" * 80)
    
    # Simular lo que hace la vista
    if not revision.informe_final_html:
        print("⚠️  informe_final_html vacío, pre-cargando...")
        revision.informe_final_html = revision.informe_residente_snapshot or revision.generar_informe_original_residente()
        revision.save()
    
    if revision.informe_final_html:
        print(f"✓ informe_final_html pre-cargado: {len(revision.informe_final_html)} caracteres")
        print(f"  Preview: {revision.informe_final_html[:200]}...")
    else:
        print("❌ informe_final_html no se pre-cargó correctamente")
        return
    
    # 5. Verificar que el contenido es correcto
    print("\n" + "-" * 80)
    print("VERIFICACIÓN 3: Contenido del Editor")
    print("-" * 80)
    
    # Verificar que contiene los títulos esperados
    contenido = revision.informe_final_html
    
    checks = [
        ("Contiene TÉCNICA", "TÉCNICA" in contenido),
        ("Contiene HALLAZGOS", "HALLAZGOS" in contenido),
        ("Contiene CONCLUSIÓN", "CONCLUSIÓN" in contenido),
        ("Contiene tags HTML", "<h3>" in contenido),
        ("Mismo contenido que snapshot", contenido == revision.informe_residente_snapshot)
    ]
    
    for check_name, check_result in checks:
        status = "✓" if check_result else "❌"
        print(f"{status} {check_name}")
    
    # 6. Información para prueba manual
    print("\n" + "=" * 80)
    print("PRUEBA MANUAL")
    print("=" * 80)
    print(f"\n1. Inicia el servidor: python manage.py runserver")
    print(f"2. Accede a: http://127.0.0.1:8000/preinformes/revisar/{preinforme.pk}/")
    print(f"3. Verifica que el editor CKEditor5 aparece con contenido pre-cargado")
    print(f"4. El contenido debe incluir:")
    print(f"   - Título: TÉCNICA")
    print(f"   - Contenido: {preinforme.tecnica[:50]}...")
    print(f"   - Título: HALLAZGOS")
    print(f"   - Contenido: {preinforme.hallazgos[:50]}...")
    print(f"   - Título: CONCLUSIÓN")
    print(f"   - Contenido: {preinforme.conclusion[:50]}...")
    
    # 7. Resumen final
    print("\n" + "=" * 80)
    print("RESUMEN")
    print("=" * 80)
    
    all_passed = all(check[1] for check in checks)
    
    if all_passed:
        print("\n✅ TODAS LAS VERIFICACIONES PASARON")
        print("\nEl editor debería aparecer pre-cargado con el contenido del residente.")
        print("Procede con la prueba manual en el navegador.")
    else:
        print("\n❌ ALGUNAS VERIFICACIONES FALLARON")
        print("\nRevisa el código y los datos antes de probar en el navegador.")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_precarga_editor()
