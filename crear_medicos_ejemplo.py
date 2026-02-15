from pedidos_estudios.models import MedicoGuardia

print("=" * 80)
print("CREANDO MÉDICOS DE GUARDIA DE EJEMPLO")
print("=" * 80)

medicos_ejemplo = [
    {
        'nombre_completo': 'Dr. Juan Pérez',
        'matricula': 'MN 12345',
        'especialidad': 'DOPPLER',
        'email': 'juan.perez@sanatoriocolegiales.com.ar',
        'telefono': '011-4567-8901',
        'whatsapp': '+5491145678901',
        'activo': True,
        'orden_rotacion': 1,
        'notas': 'Disponible de lunes a viernes'
    },
    {
        'nombre_completo': 'Dra. María González',
        'matricula': 'MN 23456',
        'especialidad': 'ECOCARDIO',
        'email': 'maria.gonzalez@sanatoriocolegiales.com.ar',
        'telefono': '011-4567-8902',
        'whatsapp': '+5491145678902',
        'activo': True,
        'orden_rotacion': 1,
        'notas': 'Especialista en ecocardiogramas TT y TEE'
    },
    {
        'nombre_completo': 'Dr. Carlos Rodríguez',
        'matricula': 'MN 34567',
        'especialidad': 'AMBOS',
        'email': 'carlos.rodriguez@sanatoriocolegiales.com.ar',
        'telefono': '011-4567-8903',
        'whatsapp': '+5491145678903',
        'activo': True,
        'orden_rotacion': 2,
        'notas': 'Guardia 24hs, realiza doppler y ecocardio'
    },
]

for datos in medicos_ejemplo:
    # Verificar si ya existe
    existe = MedicoGuardia.objects.filter(email=datos['email']).exists()
    
    if existe:
        print(f"\n⚠️  Ya existe: {datos['nombre_completo']}")
    else:
        medico = MedicoGuardia.objects.create(**datos)
        print(f"\n✅ Creado: {medico}")
        print(f"   Email: {medico.email}")
        print(f"   Especialidad: {medico.get_especialidad_display()}")
        print(f"   Estado: {'Activo' if medico.activo else 'Inactivo'}")

print("\n" + "=" * 80)
print("RESUMEN DE MÉDICOS EN SISTEMA")
print("=" * 80)

medicos = MedicoGuardia.objects.all()
print(f"\nTotal médicos: {medicos.count()}\n")

for medico in medicos:
    estado = "✓" if medico.activo else "✗"
    print(f"{estado} {medico.nombre_completo}")
    print(f"   {medico.get_especialidad_display()} - {medico.email}")
    print()

print("=" * 80)
print("✅ Proceso completado")
print("=" * 80)
