#!/usr/bin/env python
"""Script temporal para verificar registro ID 36"""
from liquidacion.models import RegistroEstudiosPorMedico
from django.db.models import Q

# Verificar registro ID 36
print("=" * 60)
print("VERIFICANDO REGISTRO ID 36")
print("=" * 60)

try:
    r = RegistroEstudiosPorMedico.objects.get(pk=36)
    print(f"\n✓ Registro encontrado:")
    print(f"  ID: {r.pk}")
    print(f"  Paciente: {r.apellido_paciente}, {r.nombre_paciente}")
    print(f"  DNI: {r.dni_paciente}")
    print(f"  Fecha del informe: {r.fecha_del_informe}")
    print(f"  Año/Mes: {r.fecha_del_informe.year}/{r.fecha_del_informe.month}")
    print(f"  Estudios: {', '.join([e.nombre for e in r.estudio.all()])}")
    print(f"  Médico: {r.medico.get_full_name()} (ID: {r.medico.pk})")
    print(f"  Cantidad regiones: {r.cantidad_regiones}")
    print(f"  Monto calculado: ${r.monto_calculado}")
    print(f"  Sesión contable: {r.sesion_contable if hasattr(r, 'sesion_contable') and r.sesion_contable else 'None'}")
except RegistroEstudiosPorMedico.DoesNotExist:
    print("\n❌ Registro ID 36 NO encontrado")

# Buscar todos los registros del médico en diciembre 2025
print("\n" + "=" * 60)
print("TODOS LOS REGISTROS DEL MÉDICO EN DICIEMBRE 2025")
print("=" * 60)

registros_dic = RegistroEstudiosPorMedico.objects.filter(
    medico__pk=2,  # Enso Fermín Cejas
    fecha_del_informe__year=2025,
    fecha_del_informe__month=12
).order_by('-fecha_del_informe')

print(f"\nTotal encontrados: {registros_dic.count()}")
for reg in registros_dic:
    print(f"\n  ID {reg.pk}: {reg.apellido_paciente}, {reg.nombre_paciente}")
    print(f"    Fecha: {reg.fecha_del_informe}")
    print(f"    Estudios: {', '.join([e.nombre for e in reg.estudio.all()])}")
    print(f"    Monto: ${reg.monto_calculado}")

# Verificar si ID 36 está incluido
if registros_dic.filter(pk=36).exists():
    print("\n✓ ID 36 ESTÁ en el queryset filtrado")
else:
    print("\n❌ ID 36 NO ESTÁ en el queryset filtrado")
    print("\nPosibles causas:")
    print("  - Fecha no es diciembre 2025")
    print("  - Médico no es el correcto")
    print("  - Registro tiene algún filtro aplicado")
