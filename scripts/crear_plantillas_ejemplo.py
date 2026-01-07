#!/usr/bin/env python3
"""
Script para crear plantillas de ejemplo para el sistema de preinformes
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from preinformes.models import TipoEstudio, Region, PlantillaPreinforme
from django.contrib.auth import get_user_model

User = get_user_model()

def crear_tipos_estudio():
    """Crear tipos de estudio básicos"""
    tipos = [
        ('RX', 'Radiografía'),
        ('TC', 'Tomografía Computada'),
        ('RM', 'Resonancia Magnética'),
        ('ECO', 'Ecografía'),
        ('Mamografía', 'Mamografía'),
    ]
    
    for codigo, descripcion in tipos:
        tipo, created = TipoEstudio.objects.get_or_create(
            nombre=codigo,
            defaults={'descripcion': descripcion}
        )
        if created:
            print(f"✓ Creado tipo de estudio: {codigo}")

def crear_regiones():
    """Crear regiones anatómicas básicas"""
    regiones = [
        'Tórax',
        'Abdomen',
        'Pelvis',
        'Extremidades Superiores',
        'Extremidades Inferiores',
        'Cabeza y Cuello',
        'Columna',
        'SNC (Sistema Nervioso Central)',
    ]
    
    for nombre in regiones:
        region, created = Region.objects.get_or_create(
            nombre=nombre,
            defaults={'descripcion': f'Región anatómica: {nombre}'}
        )
        if created:
            print(f"✓ Creada región: {nombre}")

def crear_plantillas():
    """Crear plantillas de ejemplo"""
    
    # Obtener el primer usuario disponible (o crear uno de prueba)
    try:
        user = User.objects.filter(is_staff=True).first()
        if not user:
            user = User.objects.first()
        if not user:
            print("❌ No hay usuarios en el sistema. Crear un superuser primero.")
            return
    except Exception as e:
        print(f"❌ Error obteniendo usuario: {e}")
        return
    
    plantillas_data = [
        {
            'nombre': 'RX de Tórax Normal',
            'tipo_estudio': 'RX',
            'region': 'Tórax',
            'tecnica': '<p><strong>TÉCNICA:</strong></p><p>Radiografía de tórax en proyección posteroanterior y lateral, con el paciente en bipedestación e inspiración profunda.</p>',
            'hallazgos': '<p><strong>HALLAZGOS:</strong></p><p>Los campos pulmonares se muestran bien expandidos, de transparencia conservada, sin lesiones focales ni difusas.</p><p>Silueta cardiovascular de tamaño y forma normales.</p><p>Hilios pulmonares de morfología conservada.</p><p>Estructuras óseas sin alteraciones significativas.</p>',
            'conclusion': '<p><strong>CONCLUSIÓN:</strong></p><p>Radiografía de tórax sin alteraciones patológicas evidentes.</p>'
        },
        {
            'nombre': 'TC de Abdomen y Pelvis',
            'tipo_estudio': 'TC',
            'region': 'Abdomen',
            'tecnica': '<p><strong>TÉCNICA:</strong></p><p>Tomografía computada de abdomen y pelvis con administración de contraste endovenoso. Cortes axiales de 3mm de espesor.</p>',
            'hallazgos': '<p><strong>HALLAZGOS:</strong></p><p>Hígado de tamaño, morfología y densidad normales. Vía biliar intrahepática no dilatada.</p><p>Vesícula biliar sin alteraciones.</p><p>Páncreas de características normales.</p><p>Bazo homogéneo, de tamaño normal.</p><p>Riñones de tamaño y morfología conservados, con eliminación normal del contraste.</p><p>Estructura intestinal sin alteraciones significativas.</p>',
            'conclusion': '<p><strong>CONCLUSIÓN:</strong></p><p>TC de abdomen y pelvis sin hallazgos patológicos relevantes.</p>'
        },
        {
            'nombre': 'Ecografía Abdominal',
            'tipo_estudio': 'ECO',
            'region': 'Abdomen',
            'tecnica': '<p><strong>TÉCNICA:</strong></p><p>Ecografía abdominal completa con transductor convexo de 2-5 MHz. Paciente en ayunas.</p>',
            'hallazgos': '<p><strong>HALLAZGOS:</strong></p><p>Hígado de tamaño normal, ecoestructura homogénea. Vía biliar intrahepática no dilatada.</p><p>Vesícula biliar de paredes finas, sin litiasis.</p><p>Páncreas de ecogenicidad normal.</p><p>Bazo de tamaño y ecoestructura conservados.</p><p>Riñones de morfología y tamaño normales.</p>',
            'conclusion': '<p><strong>CONCLUSIÓN:</strong></p><p>Ecografía abdominal dentro de límites normales.</p>'
        }
    ]
    
    for plantilla_data in plantillas_data:
        try:
            tipo_estudio = TipoEstudio.objects.get(nombre=plantilla_data['tipo_estudio'])
            region = Region.objects.get(nombre=plantilla_data['region'])
            
            plantilla, created = PlantillaPreinforme.objects.get_or_create(
                nombre=plantilla_data['nombre'],
                tipo_estudio=tipo_estudio,
                region=region,
                defaults={
                    'tecnica_template': plantilla_data['tecnica'],
                    'hallazgos_template': plantilla_data['hallazgos'],
                    'conclusion_template': plantilla_data['conclusion'],
                    'creada_por': user,
                    'activa': True
                }
            )
            
            if created:
                print(f"✓ Creada plantilla: {plantilla_data['nombre']}")
            else:
                print(f"→ Plantilla ya existe: {plantilla_data['nombre']}")
                
        except Exception as e:
            print(f"❌ Error creando plantilla {plantilla_data['nombre']}: {e}")

def main():
    print("🏥 Creando datos de ejemplo para el sistema de preinformes...")
    print()
    
    print("📋 Creando tipos de estudio...")
    crear_tipos_estudio()
    print()
    
    print("🎯 Creando regiones anatómicas...")
    crear_regiones()
    print()
    
    print("📝 Creando plantillas de ejemplo...")
    crear_plantillas()
    print()
    
    print("✅ ¡Datos de ejemplo creados exitosamente!")
    print()
    print("Ahora puedes:")
    print("1. Ir a /preinformes/nuevo/ para probar el sistema")
    print("2. Seleccionar tipo de estudio + región para ver las plantillas")
    print("3. Elegir una plantilla y ver cómo se autocompletan los campos")

if __name__ == '__main__':
    main()