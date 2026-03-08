from dictado_informes import views
from django.template.loader import get_template
from django.template import TemplateDoesNotExist

print("=" * 70)
print("VERIFICACIÓN DE OPTIMIZACIONES - Fase 1")
print("=" * 70)

# Verificar APIs
print("\n✅ APIs Disponibles:")
print(f"   - transcribir_audio_whisper: {'✅' if hasattr(views, 'transcribir_audio_whisper') else '❌'}")
print(f"   - mejorar_texto_ia: {'✅' if hasattr(views, 'mejorar_texto_ia') else '❌'}")
print(f"   - guardar_correccion_aprendizaje: {'✅' if hasattr(views, 'guardar_correccion_aprendizaje') else '❌'}")

print("\n🗑️  APIs Eliminadas:")
if hasattr(views, 'procesar_audio_dictado'):
    print("   ⚠️  procesar_audio_dictado TODAVÍA EXISTE (error)")
else:
    print("   ✅ procesar_audio_dictado correctamente eliminada")

print("\n📄 Templates:")
try:
    get_template('dictado_informes/dictado_rapido_whisper.html')
    print("   ✅ dictado_rapido_whisper.html (activo)")
except TemplateDoesNotExist:
    print("   ❌ dictado_rapido_whisper.html NO encontrado (error)")

try:
    get_template('dictado_informes/dictado_rapido.html')
    print("   ⚠️  dictado_rapido.html TODAVÍA EXISTE (error)")
except TemplateDoesNotExist:
    print("   ✅ dictado_rapido.html correctamente eliminado")

print("\n" + "=" * 70)
print("VERIFICACIÓN COMPLETADA")
print("=" * 70)
