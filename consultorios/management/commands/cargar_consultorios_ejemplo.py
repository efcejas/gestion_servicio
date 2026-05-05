# -*- coding: utf-8 -*-
"""
Comando para cargar datos de ejemplo del modulo consultorios.

Escenarios cubiertos:
- Staff interno con usuario
- Staff externo sin usuario
- Cardiologos como externos
- Jefes/Instructores operando como staff
- Pool de residentes para extras/coberturas
- Listas especializadas con competencia requerida

Uso:
    python manage.py cargar_consultorios_ejemplo
    python manage.py cargar_consultorios_ejemplo --reset
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from consultorios.models import (
    AsignacionEquipoConsultorio,
    BloqueHorario,
    CategoriaProfesionalExterno,
    Consultorio,
    DiaSemana,
    EstadoBloque,
    ProfesionalExterno,
    TipoActividad,
    TipoLista,
)
from equipos.models import AreaServicio, EquipoImagen

User = get_user_model()


class Command(BaseCommand):
    help = 'Carga datos de ejemplo para pruebas locales del modulo consultorios'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Elimina primero los datos demo de consultorios y los recrea desde cero.'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('CARGA DE DATOS DEMO - CONSULTORIOS ECOGRAFIA'))
        self.stdout.write('=' * 70)

        if options['reset']:
            self._reset_demo_data()

        usuarios = self._crear_usuarios_demo()
        consultorios = self._crear_consultorios_demo()
        equipos = self._crear_equipos_demo()
        self._asignar_equipos(consultorios, equipos)
        externos = self._crear_profesionales_externos_demo()
        self._crear_bloques_demo(consultorios, equipos, externos, usuarios)

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('RESUMEN FINAL'))
        self.stdout.write('=' * 70)
        self.stdout.write(f"Consultorios: {Consultorio.objects.count()}")
        self.stdout.write(f"Profesionales externos: {ProfesionalExterno.objects.count()}")
        self.stdout.write(f"Bloques activos: {BloqueHorario.objects.filter(estado=EstadoBloque.ACTIVO).count()}")
        self.stdout.write(f"Bloques pool residentes: {BloqueHorario.objects.filter(tipo_lista=TipoLista.LISTA_RESIDENTE_POOL).count()}")
        self.stdout.write(f"Bloques especializados: {BloqueHorario.objects.filter(tipo_lista=TipoLista.LISTA_ESPECIALIZADA).count()}")
        self.stdout.write(self.style.SUCCESS('\nDatos demo cargados OK.'))

    def _reset_demo_data(self):
        self.stdout.write(self.style.WARNING('\n--reset activo: limpiando datos demo...'))

        usernames_demo = [
            'demo_staff_eco_1',
            'demo_staff_eco_2',
            'demo_jefe_residentes_eco',
            'demo_instructor_eco',
            'demo_residente_r1_eco',
            'demo_residente_r2_eco',
            'demo_residente_r3_eco',
        ]

        matriculas_demo = [
            'DEMO-EXT-001',
            'DEMO-EXT-002',
            'DEMO-CARD-001',
            'DEMO-CARD-002',
        ]

        nombres_consultorio_demo = ['Eco 1', 'Eco 2', 'Eco 3', 'Eco Intervencionismo']

        BloqueHorario.objects.filter(consultorio__nombre__in=nombres_consultorio_demo).delete()
        AsignacionEquipoConsultorio.objects.filter(consultorio__nombre__in=nombres_consultorio_demo).delete()
        Consultorio.objects.filter(nombre__in=nombres_consultorio_demo).delete()
        ProfesionalExterno.objects.filter(matricula__in=matriculas_demo).delete()
        User.objects.filter(username__in=usernames_demo).delete()
        EquipoImagen.objects.filter(nombre__startswith='Demo Eco ').delete()

        self.stdout.write(self.style.SUCCESS('Datos demo previos eliminados.'))

    def _crear_usuarios_demo(self):
        self.stdout.write(self.style.WARNING('\nCreando usuarios internos demo...'))

        usuarios_data = [
            {
                'username': 'demo_staff_eco_1',
                'first_name': 'Sofia',
                'last_name': 'Ledesma',
                'email': 'demo.staff1@clegiales.local',
                'rol': 'medico_staff',
                'cargo': 'Ecografia General',
            },
            {
                'username': 'demo_staff_eco_2',
                'first_name': 'Martin',
                'last_name': 'Pereyra',
                'email': 'demo.staff2@clegiales.local',
                'rol': 'medico_staff',
                'cargo': 'Doppler',
            },
            {
                'username': 'demo_jefe_residentes_eco',
                'first_name': 'Luciano',
                'last_name': 'Gimenez',
                'email': 'demo.jefe@clegiales.local',
                'rol': 'jefe_residentes',
                'cargo': 'Jefe de Residentes',
            },
            {
                'username': 'demo_instructor_eco',
                'first_name': 'Paula',
                'last_name': 'Molina',
                'email': 'demo.instructor@clegiales.local',
                'rol': 'instructor_residentes',
                'cargo': 'Instructora',
            },
            {
                'username': 'demo_residente_r1_eco',
                'first_name': 'Julian',
                'last_name': 'Ruiz',
                'email': 'demo.residente.r1@clegiales.local',
                'rol': 'medico_residente',
                'cargo': 'Residente',
                'fecha_ingreso_residencia': date.today() - timedelta(days=90),
            },
            {
                'username': 'demo_residente_r2_eco',
                'first_name': 'Valeria',
                'last_name': 'Costa',
                'email': 'demo.residente.r2@clegiales.local',
                'rol': 'medico_residente',
                'cargo': 'Residente',
                'fecha_ingreso_residencia': date.today() - timedelta(days=450),
            },
            {
                'username': 'demo_residente_r3_eco',
                'first_name': 'Tomas',
                'last_name': 'Navarro',
                'email': 'demo.residente.r3@clegiales.local',
                'rol': 'medico_residente',
                'cargo': 'Residente',
                'fecha_ingreso_residencia': date.today() - timedelta(days=820),
            },
        ]

        usuarios = {}
        for data in usuarios_data:
            defaults = {
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'email': data['email'],
                'rol': data['rol'],
                'cargo': data['cargo'],
                'perfil_completo': True,
            }
            if 'fecha_ingreso_residencia' in data:
                defaults['fecha_ingreso_residencia'] = data['fecha_ingreso_residencia']

            user, created = User.objects.update_or_create(
                username=data['username'],
                defaults=defaults,
            )
            user.set_password('demo1234')
            user.save()

            if user.rol == 'medico_residente':
                user.actualizar_anio_residencia()

            usuarios[data['username']] = user
            estado = 'Creado' if created else 'Actualizado'
            self.stdout.write(f"  {estado}: {user.username} ({user.rol})")

        return usuarios

    def _crear_consultorios_demo(self):
        self.stdout.write(self.style.WARNING('\nCreando consultorios demo...'))

        consultorios_data = [
            {'nombre': 'Eco 1', 'ubicacion': 'Piso 2, Ala Norte', 'capacidad_pacientes_hora': 4, 'esta_activo': True},
            {'nombre': 'Eco 2', 'ubicacion': 'Piso 2, Ala Norte', 'capacidad_pacientes_hora': 4, 'esta_activo': True},
            {'nombre': 'Eco 3', 'ubicacion': 'Piso 1, Ala Sur', 'capacidad_pacientes_hora': 3, 'esta_activo': True},
            {
                'nombre': 'Eco Intervencionismo',
                'ubicacion': 'Piso 1, Quirófano Ambulatorio',
                'capacidad_pacientes_hora': 2,
                'esta_activo': True,
                'observaciones': 'Consultorio para punciones, elastografia y procedimientos especiales.',
            },
        ]

        consultorios = {}
        for data in consultorios_data:
            consultorio, created = Consultorio.objects.update_or_create(
                nombre=data['nombre'],
                defaults=data,
            )
            consultorios[data['nombre']] = consultorio
            estado = 'Creado' if created else 'Actualizado'
            self.stdout.write(f"  {estado}: {consultorio.nombre}")

        return consultorios

    def _crear_equipos_demo(self):
        self.stdout.write(self.style.WARNING('\nCreando equipos de ecografia demo...'))

        equipos_data = [
            {'nombre': 'Demo Eco GE Voluson E10', 'area': AreaServicio.ECOGRAFIA, 'fabricante': 'GE', 'modelo': 'Voluson E10', 'en_servicio': True},
            {'nombre': 'Demo Eco Philips EPIQ 7', 'area': AreaServicio.ECOGRAFIA, 'fabricante': 'Philips', 'modelo': 'EPIQ 7', 'en_servicio': True},
            {'nombre': 'Demo Eco Samsung HS70A', 'area': AreaServicio.ECOGRAFIA, 'fabricante': 'Samsung', 'modelo': 'HS70A', 'en_servicio': True},
            {'nombre': 'Demo Eco Mindray Resona', 'area': AreaServicio.ECOGRAFIA, 'fabricante': 'Mindray', 'modelo': 'Resona I9', 'en_servicio': True},
        ]

        equipos = {}
        for data in equipos_data:
            equipo, created = EquipoImagen.objects.update_or_create(
                nombre=data['nombre'],
                defaults=data,
            )
            equipos[data['nombre']] = equipo
            estado = 'Creado' if created else 'Actualizado'
            self.stdout.write(f"  {estado}: {equipo.nombre}")

        return equipos

    def _asignar_equipos(self, consultorios, equipos):
        self.stdout.write(self.style.WARNING('\nAsignando equipos a consultorios...'))

        asignaciones = [
            ('Eco 1', 'Demo Eco GE Voluson E10'),
            ('Eco 2', 'Demo Eco Philips EPIQ 7'),
            ('Eco 3', 'Demo Eco Samsung HS70A'),
            ('Eco Intervencionismo', 'Demo Eco Mindray Resona'),
        ]

        for nombre_consultorio, nombre_equipo in asignaciones:
            asig, created = AsignacionEquipoConsultorio.objects.update_or_create(
                consultorio=consultorios[nombre_consultorio],
                equipo=equipos[nombre_equipo],
                defaults={
                    'es_permanente': True,
                    'fecha_inicio': date.today(),
                },
            )
            estado = 'Asignado' if created else 'Actualizado'
            self.stdout.write(f"  {estado}: {asig.equipo.nombre} -> {asig.consultorio.nombre}")

    def _crear_profesionales_externos_demo(self):
        self.stdout.write(self.style.WARNING('\nCreando profesionales externos demo...'))

        externos_data = [
            {
                'matricula': 'DEMO-EXT-001',
                'nombre': 'Mariana',
                'apellido': 'Quiroga',
                'especialidad': 'Ecografia General',
                'categoria': CategoriaProfesionalExterno.STAFF_EXTERNO,
            },
            {
                'matricula': 'DEMO-EXT-002',
                'nombre': 'Fernando',
                'apellido': 'Ramos',
                'especialidad': 'Ecografia Doppler',
                'categoria': CategoriaProfesionalExterno.STAFF_EXTERNO,
            },
            {
                'matricula': 'DEMO-CARD-001',
                'nombre': 'Agustin',
                'apellido': 'Vega',
                'especialidad': 'Cardiologia',
                'categoria': CategoriaProfesionalExterno.CARDIOLOGO_EXTERNO,
            },
            {
                'matricula': 'DEMO-CARD-002',
                'nombre': 'Noelia',
                'apellido': 'Sanchez',
                'especialidad': 'Cardiologia',
                'categoria': CategoriaProfesionalExterno.CARDIOLOGO_EXTERNO,
            },
        ]

        externos = {}
        for data in externos_data:
            profesional, created = ProfesionalExterno.objects.update_or_create(
                matricula=data['matricula'],
                defaults={
                    'nombre': data['nombre'],
                    'apellido': data['apellido'],
                    'especialidad': data['especialidad'],
                    'categoria': data['categoria'],
                    'esta_activo': True,
                },
            )
            externos[data['matricula']] = profesional
            estado = 'Creado' if created else 'Actualizado'
            self.stdout.write(f"  {estado}: {profesional.apellido}, {profesional.nombre} ({profesional.get_categoria_display()})")

        return externos

    def _crear_o_actualizar_bloque(self, unique_filter, payload):
        bloque = BloqueHorario.objects.filter(**unique_filter).first()
        created = bloque is None
        if created:
            bloque = BloqueHorario(**payload)
        else:
            for key, value in payload.items():
                setattr(bloque, key, value)
        bloque.full_clean()
        bloque.save()
        return bloque, created

    def _crear_bloques_demo(self, consultorios, equipos, externos, usuarios):
        self.stdout.write(self.style.WARNING('\nCreando bloques de ejemplo por escenario real...'))

        escenarios = [
            # Staff externo tradicional
            {
                'unique': {
                    'consultorio': consultorios['Eco 1'],
                    'profesional_externo': externos['DEMO-EXT-001'],
                    'dia_semana': DiaSemana.LUNES,
                    'hora_inicio': time(8, 0),
                },
                'payload': {
                    'consultorio': consultorios['Eco 1'],
                    'profesional_externo': externos['DEMO-EXT-001'],
                    'profesional_interno': None,
                    'equipo': equipos['Demo Eco GE Voluson E10'],
                    'dia_semana': DiaSemana.LUNES,
                    'hora_inicio': time(8, 0),
                    'hora_fin': time(12, 0),
                    'fecha_inicio_vigencia': date.today() - timedelta(days=30),
                    'estado': EstadoBloque.ACTIVO,
                    'tipo_actividad': TipoActividad.ECO_GENERAL,
                    'tipo_lista': TipoLista.LISTA_STAFF,
                    'permite_cobertura_residente': False,
                    'prioridad_cobertura': 3,
                    'competencia_requerida': None,
                },
            },
            # Staff interno
            {
                'unique': {
                    'consultorio': consultorios['Eco 2'],
                    'profesional_interno': usuarios['demo_staff_eco_1'],
                    'dia_semana': DiaSemana.MARTES,
                    'hora_inicio': time(8, 0),
                },
                'payload': {
                    'consultorio': consultorios['Eco 2'],
                    'profesional_interno': usuarios['demo_staff_eco_1'],
                    'profesional_externo': None,
                    'equipo': equipos['Demo Eco Philips EPIQ 7'],
                    'dia_semana': DiaSemana.MARTES,
                    'hora_inicio': time(8, 0),
                    'hora_fin': time(12, 0),
                    'fecha_inicio_vigencia': date.today() - timedelta(days=15),
                    'estado': EstadoBloque.ACTIVO,
                    'tipo_actividad': TipoActividad.ECO_DOPPLER,
                    'tipo_lista': TipoLista.LISTA_STAFF,
                    'permite_cobertura_residente': False,
                    'prioridad_cobertura': 3,
                    'competencia_requerida': None,
                },
            },
            # Jefe/instructor como staff
            {
                'unique': {
                    'consultorio': consultorios['Eco 3'],
                    'profesional_interno': usuarios['demo_jefe_residentes_eco'],
                    'dia_semana': DiaSemana.MIERCOLES,
                    'hora_inicio': time(13, 0),
                },
                'payload': {
                    'consultorio': consultorios['Eco 3'],
                    'profesional_interno': usuarios['demo_jefe_residentes_eco'],
                    'profesional_externo': None,
                    'equipo': equipos['Demo Eco Samsung HS70A'],
                    'dia_semana': DiaSemana.MIERCOLES,
                    'hora_inicio': time(13, 0),
                    'hora_fin': time(17, 0),
                    'fecha_inicio_vigencia': date.today(),
                    'estado': EstadoBloque.ACTIVO,
                    'tipo_actividad': TipoActividad.ECO_GENERAL,
                    'tipo_lista': TipoLista.LISTA_DOCENTE_COMO_STAFF,
                    'permite_cobertura_residente': False,
                    'prioridad_cobertura': 2,
                    'competencia_requerida': None,
                },
            },
            {
                'unique': {
                    'consultorio': consultorios['Eco 3'],
                    'profesional_interno': usuarios['demo_instructor_eco'],
                    'dia_semana': DiaSemana.JUEVES,
                    'hora_inicio': time(8, 0),
                },
                'payload': {
                    'consultorio': consultorios['Eco 3'],
                    'profesional_interno': usuarios['demo_instructor_eco'],
                    'profesional_externo': None,
                    'equipo': equipos['Demo Eco Samsung HS70A'],
                    'dia_semana': DiaSemana.JUEVES,
                    'hora_inicio': time(8, 0),
                    'hora_fin': time(12, 0),
                    'fecha_inicio_vigencia': date.today(),
                    'estado': EstadoBloque.ACTIVO,
                    'tipo_actividad': TipoActividad.ECO_PEDIATRICA,
                    'tipo_lista': TipoLista.LISTA_DOCENTE_COMO_STAFF,
                    'permite_cobertura_residente': True,
                    'prioridad_cobertura': 2,
                    'competencia_requerida': None,
                },
            },
            # Cardiologos como externos
            {
                'unique': {
                    'consultorio': consultorios['Eco 1'],
                    'profesional_externo': externos['DEMO-CARD-001'],
                    'dia_semana': DiaSemana.VIERNES,
                    'hora_inicio': time(9, 0),
                },
                'payload': {
                    'consultorio': consultorios['Eco 1'],
                    'profesional_externo': externos['DEMO-CARD-001'],
                    'profesional_interno': None,
                    'equipo': equipos['Demo Eco GE Voluson E10'],
                    'dia_semana': DiaSemana.VIERNES,
                    'hora_inicio': time(9, 0),
                    'hora_fin': time(12, 0),
                    'fecha_inicio_vigencia': date.today() - timedelta(days=10),
                    'estado': EstadoBloque.ACTIVO,
                    'tipo_actividad': TipoActividad.ECO_DOPPLER,
                    'tipo_lista': TipoLista.LISTA_STAFF,
                    'permite_cobertura_residente': False,
                    'prioridad_cobertura': 3,
                    'competencia_requerida': None,
                },
            },
            # Pool residentes (extras/coberturas)
            {
                'unique': {
                    'consultorio': consultorios['Eco 2'],
                    'profesional_interno': usuarios['demo_residente_r1_eco'],
                    'dia_semana': DiaSemana.SABADO,
                    'hora_inicio': time(8, 0),
                },
                'payload': {
                    'consultorio': consultorios['Eco 2'],
                    'profesional_interno': usuarios['demo_residente_r1_eco'],
                    'profesional_externo': None,
                    'equipo': equipos['Demo Eco Philips EPIQ 7'],
                    'dia_semana': DiaSemana.SABADO,
                    'hora_inicio': time(8, 0),
                    'hora_fin': time(12, 0),
                    'fecha_inicio_vigencia': date.today(),
                    'estado': EstadoBloque.ACTIVO,
                    'tipo_actividad': TipoActividad.ECO_GENERAL,
                    'tipo_lista': TipoLista.LISTA_RESIDENTE_POOL,
                    'permite_cobertura_residente': True,
                    'prioridad_cobertura': 1,
                    'competencia_requerida': None,
                },
            },
            {
                'unique': {
                    'consultorio': consultorios['Eco 2'],
                    'profesional_interno': usuarios['demo_residente_r2_eco'],
                    'dia_semana': DiaSemana.DOMINGO,
                    'hora_inicio': time(8, 0),
                },
                'payload': {
                    'consultorio': consultorios['Eco 2'],
                    'profesional_interno': usuarios['demo_residente_r2_eco'],
                    'profesional_externo': None,
                    'equipo': equipos['Demo Eco Philips EPIQ 7'],
                    'dia_semana': DiaSemana.DOMINGO,
                    'hora_inicio': time(8, 0),
                    'hora_fin': time(12, 0),
                    'fecha_inicio_vigencia': date.today(),
                    'estado': EstadoBloque.ACTIVO,
                    'tipo_actividad': TipoActividad.ECO_GENERAL,
                    'tipo_lista': TipoLista.LISTA_RESIDENTE_POOL,
                    'permite_cobertura_residente': True,
                    'prioridad_cobertura': 1,
                    'competencia_requerida': None,
                },
            },
            # Lista especializada
            {
                'unique': {
                    'consultorio': consultorios['Eco Intervencionismo'],
                    'profesional_interno': usuarios['demo_staff_eco_2'],
                    'dia_semana': DiaSemana.LUNES,
                    'hora_inicio': time(14, 0),
                },
                'payload': {
                    'consultorio': consultorios['Eco Intervencionismo'],
                    'profesional_interno': usuarios['demo_staff_eco_2'],
                    'profesional_externo': None,
                    'equipo': equipos['Demo Eco Mindray Resona'],
                    'dia_semana': DiaSemana.LUNES,
                    'hora_inicio': time(14, 0),
                    'hora_fin': time(18, 0),
                    'fecha_inicio_vigencia': date.today() - timedelta(days=5),
                    'estado': EstadoBloque.ACTIVO,
                    'tipo_actividad': TipoActividad.INTERVENCIONISMO,
                    'tipo_lista': TipoLista.LISTA_ESPECIALIZADA,
                    'permite_cobertura_residente': False,
                    'prioridad_cobertura': 1,
                    'competencia_requerida': 'Puncion mamaria y elastografia',
                },
            },
        ]

        for escenario in escenarios:
            payload = escenario['payload'].copy()
            if 'creado_por' not in payload:
                payload['creado_por'] = usuarios['demo_jefe_residentes_eco']
            bloque, created = self._crear_o_actualizar_bloque(escenario['unique'], payload)
            estado = 'Creado' if created else 'Actualizado'
            self.stdout.write(
                f"  {estado}: {bloque.get_dia_semana_display()} {bloque.hora_inicio.strftime('%H:%M')} "
                f"- {bloque.consultorio.nombre} - {bloque.get_tipo_lista_display()}"
            )
