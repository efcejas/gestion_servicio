"""
Script de configuración para el Sistema de Clases de Residentes.
Ejecutar: python scripts/maintenance/configurar_clases_residentes.py
"""

print("="*80)
print(" CONFIGURACIÓN DEL SISTEMA DE CLASES DE RESIDENTES")
print("="*80)

print("\n📋 PASOS A SEGUIR MANUALMENTE:\n")

print("1️⃣ INSTALAR CLOUDINARY")
print("   pip install django-cloudinary-storage")

print("\n2️⃣ AGREGAR A INSTALLED_APPS en gestion_estudios/settings.py:")
print("""
INSTALLED_APPS = [
    'django.contrib.admin',
    ...
    'cloudinary_storage',  # NUEVO - Antes de cloudinary
    'cloudinary',          # NUEVO
    ...
    'protocolos.apps.ProtocolosConfig',
    'clases_residentes.apps.ClasesResidentesConfig',  # NUEVO
    ...
]
""")

print("\n3️⃣ AGREGAR CONFIGURACIÓN DE CLOUDINARY en settings.py:")
print("""
# Cloudinary Configuration (después de STATIC_URL)
import cloudinary
import cloudinary.uploader
import cloudinary.api

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': env('CLOUDINARY_CLOUD_NAME', default=''),
    'API_KEY': env('CLOUDINARY_API_KEY', default=''),
    'API_SECRET': env('CLOUDINARY_API_SECRET', default='')
}

# Solo usar Cloudinary si está configurado
if all([CLOUDINARY_STORAGE['CLOUD_NAME'], CLOUDINARY_STORAGE['API_KEY'], CLOUDINARY_STORAGE['API_SECRET']]):
    cloudinary.config(
        cloud_name=CLOUDINARY_STORAGE['CLOUD_NAME'],
        api_key=CLOUDINARY_STORAGE['API_KEY'],
        api_secret=CLOUDINARY_STORAGE['API_SECRET'],
        secure=True
    )
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    print("✓ Cloudinary configurado correctamente")
else:
    print("⚠ Cloudinary NO configurado - usando almacenamiento local")
""")

print("\n4️⃣ AGREGAR A .env:")
print("""
# Cloudinary (obtener de https://cloudinary.com/console)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
""")

print("\n5️⃣ AGREGAR URLS en gestion_estudios/urls.py:")
print("""
urlpatterns = [
    ...
    path('protocolos/', include('protocolos.urls')),
    path('clases/', include('clases_residentes.urls')),  # NUEVO
    ...
]
""")

print("\n6️⃣ ACTUALIZAR config_sanatorio.py:")
print("""
MODULOS_ACTIVOS = {
    ...
    'protocolos': True,
    'clases': True,  # NUEVO
}
""")

print("\n7️⃣ EJECUTAR MIGRACIONES:")
print("   python manage.py makemigrations clases_residentes")
print("   python manage.py migrate")

print("\n8️⃣ CREAR CUENTA EN CLOUDINARY:")
print("   https://cloudinary.com/users/register/free")
print("   Dashboard: https://cloudinary.com/console")

print("\n9️⃣ AGREGAR ENLACE EN SIDEBAR (templates/includes/sidebar.html):")
print("""
{% if SANATORIO_MODULOS.clases %}
<a href="{% url 'clases_residentes:lista' %}" class="...">
    <i class="fas fa-graduation-cap mr-3"></i>Clases
</a>
{% endif %}
""")

print("\n🔟 AGREGAR ENLACE EN NAVBAR (templates/layouts/base_tailwind.html):")
print("""
{% if user.es_medico %}
    <a href="{% url 'clases_residentes:lista' %}" class="...">
        <i class="fas fa-graduation-cap mr-2"></i>Clases
    </a>
{% endif %}
""")

print("\n" + "="*80)
print(" ✅ CONFIGURACIÓN LISTA")
print("="*80)
print("\nDocumentación completa en: docs/SISTEMA_CLASES_RESIDENTES.md")
