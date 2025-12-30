from django.contrib.auth import get_user_model
from liquidacion.models import RegistroEstudiosPorMedico
from datetime import date
from collections import defaultdict

User = get_user_model()

# Buscar usuario Denise Buleter
user = User.objects.filter(first_name__icontains='Denise', last_name__icontains='Buleter').first()

if not user:
    print("Usuario no encontrado")
    exit()

print(f"Usuario encontrado: {user.get_full_name()} (ID: {user.id})")
print("=" * 80)

# Obtener registros de hoy
registros_hoy = RegistroEstudiosPorMedico.objects.filter(
    medico=user, 
    fecha_registro__date=date.today()
).order_by('fecha_registro')

print(f"\nRegistros de hoy ({date.today()}): {registros_hoy.count()}")
print("=" * 80)

# Agrupar registros por paciente y fecha de informe para detectar duplicados
duplicados_map = defaultdict(list)

for registro in registros_hoy:
    estudios = ", ".join([e.nombre for e in registro.estudio.all()])
    key = (registro.dni_paciente, registro.fecha_del_informe, estudios)
    duplicados_map[key].append(registro)
    
    print(f"\nID: {registro.id}")
    print(f"Hora registro: {registro.fecha_registro.strftime('%H:%M:%S')}")
    print(f"Paciente: {registro.apellido_paciente}, {registro.nombre_paciente}")
    print(f"DNI: {registro.dni_paciente}")
    print(f"Fecha informe: {registro.fecha_del_informe}")
    print(f"Estudios: {estudios}")
    print("-" * 80)

# Mostrar duplicados
print("\n\n" + "=" * 80)
print("ANÁLISIS DE DUPLICADOS")
print("=" * 80)

duplicados_encontrados = False
for key, registros in duplicados_map.items():
    if len(registros) > 1:
        duplicados_encontrados = True
        dni, fecha_informe, estudios = key
        print(f"\n⚠️  DUPLICADO ENCONTRADO:")
        print(f"DNI: {dni} | Fecha Informe: {fecha_informe} | Estudios: {estudios}")
        print(f"Cantidad de registros: {len(registros)}")
        for r in registros:
            print(f"  - ID: {r.id} | Hora: {r.fecha_registro.strftime('%H:%M:%S')}")
        print("-" * 80)

if not duplicados_encontrados:
    print("\n✅ No se encontraron registros duplicados")
