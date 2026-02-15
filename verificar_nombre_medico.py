from pedidos_estudios.models import MedicoGuardia

medicos = MedicoGuardia.objects.all()

print("\n=== MÉDICOS EN BASE DE DATOS ===")
for medico in medicos:
    print(f"\nID: {medico.id}")
    print(f"Nombre: {medico.nombre_completo}")
    print(f"Nombre (repr): {repr(medico.nombre_completo)}")
    print(f"Especialidad: {medico.especialidad}")
    print(f"Email: {medico.email}")
