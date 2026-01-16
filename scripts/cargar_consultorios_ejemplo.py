"""
Script para cargar datos de ejemplo en el sistema de consultorios.

Ejecutar:
    python manage.py shell < consultorios/fixtures/cargar_datos_ejemplo.py

O desde la shell de Django:
    python manage.py shell
    exec(open('consultorios/fixtures/cargar_datos_ejemplo.py').read())
"""

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import time, date, timedelta

from consultorios.models import (
    Consultorio,
    ProfesionalExterno,
    AsignacionEquipoConsultorio,
    BloqueHorario,
    TipoActividad,
    EstadoBloque,
    DiaSemana
)
from equipos.models import EquipoImagen, AreaServicio

User = get_user_model()

def cargar_datos():
    """Carga datos de ejemplo para el sistema de consultorios"""
    
    print("\n" + "="*60)
    print("🏥 CARGANDO DATOS DE EJEMPLO - SISTEMA DE CONSULTORIOS")
    print("="*60 + "\n")
    
    # ============================
    # 1. CONSULTORIOS
    # ============================
    print("📍 Creando consultorios...")
    
    consultorios_data = [
        {
            'nombre': 'Eco 1',
            'ubicacion': 'Piso 2, Ala Norte',
            'capacidad_pacientes_hora': 4,
            'esta_activo': True,
        },
        {
            'nombre': 'Eco 2',
            'ubicacion': 'Piso 2, Ala Norte',
            'capacidad_pacientes_hora': 4,
            'esta_activo': True,
        },
        {
            'nombre': 'Eco 3',
            'ubicacion': 'Piso 1, Ala Sur',
            'capacidad_pacientes_hora': 3,
            'esta_activo': True,
        },
        {
            'nombre': 'Eco VIP',
            'ubicacion': 'Piso 3',
            'capacidad_pacientes_hora': 2,
            'esta_activo': True,
            'observaciones': 'Consultorio premium para pacientes VIP'
        },
    ]
    
    consultorios = {}
    for data in consultorios_data:
        consultorio, created = Consultorio.objects.get_or_create(
            nombre=data['nombre'],
            defaults=data
        )
        consultorios[data['nombre']] = consultorio
        status = "✓ Creado" if created else "○ Ya existía"
        print(f"  {status}: {consultorio.nombre}")
    
    # ============================
    # 2. EQUIPOS DE ECOGRAFÍA
    # ============================
    print("\n🔧 Creando equipos de ecografía...")
    
    equipos_data = [
        {
            'nombre': 'Ecógrafo GE Voluson E10',
            'area': AreaServicio.ECOGRAFIA,
            'fabricante': 'GE Healthcare',
            'modelo': 'Voluson E10',
            'ubicacion': 'Eco 1',
            'en_servicio': True,
        },
        {
            'nombre': 'Ecógrafo Philips EPIQ 7',
            'area': AreaServicio.ECOGRAFIA,
            'fabricante': 'Philips',
            'modelo': 'EPIQ 7',
            'ubicacion': 'Eco 2',
            'en_servicio': True,
        },
        {
            'nombre': 'Ecógrafo Samsung HS70A',
            'area': AreaServicio.ECOGRAFIA,
            'fabricante': 'Samsung',
            'modelo': 'HS70A',
            'ubicacion': 'Eco 3',
            'en_servicio': True,
        },
        {
            'nombre': 'Ecógrafo GE Logiq E9',
            'area': AreaServicio.ECOGRAFIA,
            'fabricante': 'GE Healthcare',
            'modelo': 'Logiq E9',
            'ubicacion': 'Eco VIP',
            'en_servicio': True,
        },
    ]
    
    equipos = {}
    for data in equipos_data:
        equipo, created = EquipoImagen.objects.get_or_create(
            nombre=data['nombre'],
            defaults=data
        )
        equipos[data['nombre']] = equipo
        status = "✓ Creado" if created else "○ Ya existía"
        print(f"  {status}: {equipo.nombre}")
    
    # ============================
    # 3. ASIGNACIONES EQUIPO-CONSULTORIO
    # ============================
    print("\n🔗 Asignando equipos a consultorios...")
    
    asignaciones_data = [
        {
            'consultorio': consultorios['Eco 1'],
            'equipo': equipos['Ecógrafo GE Voluson E10'],
            'es_permanente': True,
        },
        {
            'consultorio': consultorios['Eco 2'],
            'equipo': equipos['Ecógrafo Philips EPIQ 7'],
            'es_permanente': True,
        },
        {
            'consultorio': consultorios['Eco 3'],
            'equipo': equipos['Ecógrafo Samsung HS70A'],
            'es_permanente': True,
        },
        {
            'consultorio': consultorios['Eco VIP'],
            'equipo': equipos['Ecógrafo GE Logiq E9'],
            'es_permanente': True,
        },
    ]
    
    for data in asignaciones_data:
        asignacion, created = AsignacionEquipoConsultorio.objects.get_or_create(
            consultorio=data['consultorio'],
            equipo=data['equipo'],
            defaults=data
        )
        status = "✓ Asignado" if created else "○ Ya asignado"
        print(f"  {status}: {asignacion.equipo.nombre} → {asignacion.consultorio.nombre}")
    
    # ============================
    # 4. PROFESIONALES EXTERNOS
    # ============================
    print("\n👨‍⚕️ Creando profesionales externos...")
    
    profesionales_externos_data = [
        {
            'nombre': 'María',
            'apellido': 'González',
            'matricula': 'MN-98765',
            'especialidad': 'Ecografía General',
            'telefono': '+54 11 4567-8901',
            'email': 'mgonzalez@ejemplo.com',
            'esta_activo': True,
        },
        {
            'nombre': 'Roberto',
            'apellido': 'Fernández',
            'matricula': 'MN-87654',
            'especialidad': 'Ecografía Doppler',
            'telefono': '+54 11 4567-8902',
            'email': 'rfernandez@ejemplo.com',
            'esta_activo': True,
        },
        {
            'nombre': 'Laura',
            'apellido': 'Martínez',
            'matricula': 'MN-76543',
            'especialidad': 'Ecografía Obstétrica',
            'telefono': '+54 11 4567-8903',
            'email': 'lmartinez@ejemplo.com',
            'esta_activo': True,
        },
        {
            'nombre': 'Diego',
            'apellido': 'Rodríguez',
            'matricula': 'MN-65432',
            'especialidad': 'Ecografía Musculoesquelética',
            'telefono': '+54 11 4567-8904',
            'email': 'drodriguez@ejemplo.com',
            'esta_activo': True,
        },
    ]
    
    profesionales_externos = {}
    for data in profesionales_externos_data:
        profesional, created = ProfesionalExterno.objects.get_or_create(
            matricula=data['matricula'],
            defaults=data
        )
        profesionales_externos[data['matricula']] = profesional
        status = "✓ Creado" if created else "○ Ya existía"
        print(f"  {status}: Dr./Dra. {profesional.apellido}, {profesional.nombre}")
    
    # ============================
    # 5. USUARIOS INTERNOS (MÉDICOS STAFF)
    # ============================
    print("\n👤 Verificando usuarios internos (médicos staff)...")
    
    # Buscar usuarios con rol médico
    medicos_internos = User.objects.filter(rol='medico_staff')[:2]
    
    if medicos_internos.exists():
        print(f"  ✓ Encontrados {medicos_internos.count()} médicos staff")
        for medico in medicos_internos:
            print(f"    - {medico.get_full_name() or medico.username}")
    else:
        print("  ⚠ No se encontraron médicos staff en el sistema")
        print("    Creando usuario de ejemplo...")
        medico_ejemplo = User.objects.create_user(
            username='medico_ejemplo',
            email='medico@ejemplo.com',
            first_name='Carlos',
            last_name='López',
            rol='medico_staff'
        )
        medico_ejemplo.set_password('ejemplo123')
        medico_ejemplo.save()
        medicos_internos = [medico_ejemplo]
        print(f"  ✓ Creado: Dr. {medico_ejemplo.last_name}, {medico_ejemplo.first_name}")
    
    # ============================
    # 6. BLOQUES HORARIOS
    # ============================
    print("\n📅 Creando bloques horarios...")
    
    # Bloques con profesionales externos
    bloques_externos = [
        {
            'consultorio': consultorios['Eco 1'],
            'profesional_externo': profesionales_externos['MN-98765'],
            'equipo': equipos['Ecógrafo GE Voluson E10'],
            'dia_semana': DiaSemana.LUNES,
            'hora_inicio': time(8, 0),
            'hora_fin': time(12, 0),
            'tipo_actividad': TipoActividad.ECO_GENERAL,
            'estado': EstadoBloque.ACTIVO,
        },
        {
            'consultorio': consultorios['Eco 2'],
            'profesional_externo': profesionales_externos['MN-87654'],
            'equipo': equipos['Ecógrafo Philips EPIQ 7'],
            'dia_semana': DiaSemana.MARTES,
            'hora_inicio': time(14, 0),
            'hora_fin': time(18, 0),
            'tipo_actividad': TipoActividad.ECO_DOPPLER,
            'estado': EstadoBloque.ACTIVO,
        },
        {
            'consultorio': consultorios['Eco 3'],
            'profesional_externo': profesionales_externos['MN-76543'],
            'equipo': equipos['Ecógrafo Samsung HS70A'],
            'dia_semana': DiaSemana.MIERCOLES,
            'hora_inicio': time(9, 0),
            'hora_fin': time(13, 0),
            'tipo_actividad': TipoActividad.ECO_OBSTETRICA,
            'estado': EstadoBloque.ACTIVO,
        },
        {
            'consultorio': consultorios['Eco 1'],
            'profesional_externo': profesionales_externos['MN-65432'],
            'equipo': equipos['Ecógrafo GE Voluson E10'],
            'dia_semana': DiaSemana.JUEVES,
            'hora_inicio': time(15, 0),
            'hora_fin': time(19, 0),
            'tipo_actividad': TipoActividad.ECO_MUSCULOESQUELETICA,
            'estado': EstadoBloque.ACTIVO,
        },
        {
            'consultorio': consultorios['Eco VIP'],
            'profesional_externo': profesionales_externos['MN-98765'],
            'equipo': equipos['Ecógrafo GE Logiq E9'],
            'dia_semana': DiaSemana.VIERNES,
            'hora_inicio': time(10, 0),
            'hora_fin': time(14, 0),
            'tipo_actividad': TipoActividad.ECO_GENERAL,
            'estado': EstadoBloque.ACTIVO,
        },
    ]
    
    for data in bloques_externos:
        # Verificar si ya existe
        existe = BloqueHorario.objects.filter(
            consultorio=data['consultorio'],
            profesional_externo=data['profesional_externo'],
            dia_semana=data['dia_semana'],
            hora_inicio=data['hora_inicio']
        ).exists()
        
        if not existe:
            bloque = BloqueHorario.objects.create(**data)
            prof = bloque.profesional_externo
            print(f"  ✓ Creado: {bloque.consultorio.nombre} - Dr./Dra. {prof.apellido} - {bloque.get_dia_semana_display()} {bloque.hora_inicio}-{bloque.hora_fin}")
        else:
            print(f"  ○ Ya existe: {data['consultorio'].nombre} - {data['dia_semana']} {data['hora_inicio']}")
    
    # Bloques con profesionales internos (si existen)
    if medicos_internos:
        bloques_internos = [
            {
                'consultorio': consultorios['Eco 2'],
                'profesional_interno': medicos_internos[0],
                'equipo': equipos['Ecógrafo Philips EPIQ 7'],
                'dia_semana': DiaSemana.LUNES,
                'hora_inicio': time(8, 0),
                'hora_fin': time(12, 0),
                'tipo_actividad': TipoActividad.ECO_GENERAL,
                'estado': EstadoBloque.ACTIVO,
            },
            {
                'consultorio': consultorios['Eco 3'],
                'profesional_interno': medicos_internos[0] if len(medicos_internos) == 1 else medicos_internos[1],
                'equipo': equipos['Ecógrafo Samsung HS70A'],
                'dia_semana': DiaSemana.VIERNES,
                'hora_inicio': time(14, 0),
                'hora_fin': time(18, 0),
                'tipo_actividad': TipoActividad.ECO_DOPPLER,
                'estado': EstadoBloque.ACTIVO,
            },
        ]
        
        for data in bloques_internos:
            # Verificar si ya existe
            existe = BloqueHorario.objects.filter(
                consultorio=data['consultorio'],
                profesional_interno=data['profesional_interno'],
                dia_semana=data['dia_semana'],
                hora_inicio=data['hora_inicio']
            ).exists()
            
            if not existe:
                bloque = BloqueHorario.objects.create(**data)
                prof = bloque.profesional_interno
                print(f"  ✓ Creado: {bloque.consultorio.nombre} - {prof.get_full_name()} - {bloque.get_dia_semana_display()} {bloque.hora_inicio}-{bloque.hora_fin}")
            else:
                print(f"  ○ Ya existe: {data['consultorio'].nombre} - {data['dia_semana']} {data['hora_inicio']}")
    
    # ============================
    # RESUMEN FINAL
    # ============================
    print("\n" + "="*60)
    print("📊 RESUMEN DE DATOS CARGADOS")
    print("="*60)
    print(f"  Consultorios: {Consultorio.objects.count()}")
    print(f"  Equipos de Ecografía: {EquipoImagen.objects.filter(area=AreaServicio.ECOGRAFIA).count()}")
    print(f"  Asignaciones Equipo-Consultorio: {AsignacionEquipoConsultorio.objects.count()}")
    print(f"  Profesionales Externos: {ProfesionalExterno.objects.count()}")
    print(f"  Bloques Horarios Activos: {BloqueHorario.objects.filter(estado=EstadoBloque.ACTIVO).count()}")
    print(f"  Total Bloques Horarios: {BloqueHorario.objects.count()}")
    print("="*60)
    print("\n✅ ¡Datos de ejemplo cargados exitosamente!")
    print("\n💡 Ahora puedes acceder al admin en: http://localhost:8000/admin/")
    print("   Navega a: Consultorios → [Consultorios | Profesionales Externos | Bloques Horarios]\n")

if __name__ == '__main__':
    cargar_datos()
