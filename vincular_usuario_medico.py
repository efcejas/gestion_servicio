from django.contrib.auth import get_user_model
from pedidos_estudios.models import MedicoGuardia

User = get_user_model()

print("=" * 80)
print("VINCULAR USUARIO CON MÉDICO DE GUARDIA")
print("=" * 80)

# Buscar tu usuario
try:
    usuario = User.objects.get(username='admin')  # Usuario principal
    print(f"\n✓ Usuario encontrado: {usuario.get_full_name() or usuario.username}")
    print(f"  Email: {usuario.email}")
except User.DoesNotExist:
    print("\n❌ Usuario 'efcejas' no encontrado")
    print("\nUsuarios disponibles:")
    for u in User.objects.all()[:10]:
        print(f"  - {u.username} ({u.get_full_name() or 'Sin nombre'})")
    exit()

# Buscar el médico con especialidad AMBOS
try:
    medico = MedicoGuardia.objects.get(especialidad='AMBOS')
    print(f"\n✓ Médico encontrado: {medico.nombre_completo}")
    print(f"  Especialidad: {medico.get_especialidad_display()}")
except MedicoGuardia.DoesNotExist:
    print("\n❌ No se encontró médico con especialidad AMBOS")
    exit()

# Vincular
if medico.usuario:
    print(f"\n⚠️  El médico ya está vinculado a: {medico.usuario.username}")
    print("   ¿Desvincularlo y vincular a tu usuario? Ejecuta manualmente si es necesario.")
else:
    medico.usuario = usuario
    # Usar el email del usuario si existe
    if usuario.email and not medico.email:
        medico.email = usuario.email
    medico.save()
    
    print(f"\n✅ VINCULACIÓN EXITOSA")
    print(f"   Usuario: {usuario.username}")
    print(f"   Médico: {medico.nombre_completo}")
    print(f"   Especialidad: {medico.get_especialidad_display()}")
    print(f"\n🎯 Ahora puedes acceder a: /pedidos/mis-estudios/")

print("\n" + "=" * 80)
