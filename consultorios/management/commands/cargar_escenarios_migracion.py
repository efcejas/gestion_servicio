# -*- coding: utf-8 -*-
"""
Carga escenarios concretos para probar el asistente de migracion de agendas.

Escenarios creados (jueves 15:00-18:00 como referencia):
  - LIBRE: consultorio sin bloques en ese rango
  - BLANDO: solo bloques R1-R4 superpuestos
  - BLOQUEADO: al menos un bloque duro superpuesto

Uso:
    python manage.py cargar_escenarios_migracion
    python manage.py cargar_escenarios_migracion --reset
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from consultorios.models import (
    BloqueHorario,
    Consultorio,
    DiaSemana,
    EstadoBloque,
    TipoActividad,
    TipoLista,
    TipoTitularBloque,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Carga escenarios demo de migracion: libre, blando y bloqueado.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Elimina los bloques de este seed antes de recrearlos.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('SEED DE ESCENARIOS DE MIGRACION'))
        self.stdout.write('=' * 70)

        if options['reset']:
            eliminados = BloqueHorario.objects.filter(observaciones__icontains='SEED_MIGRACION').delete()[0]
            self.stdout.write(self.style.WARNING(f'Bloques seed previos eliminados: {eliminados}'))

        consultorios = self._asegurar_consultorios()
        users = self._asegurar_usuarios_base()
        self._crear_escenarios(consultorios, users)

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('RESUMEN'))
        self.stdout.write('=' * 70)
        seed_qs = BloqueHorario.objects.filter(observaciones__icontains='SEED_MIGRACION')
        self.stdout.write(f'Bloques seed activos: {seed_qs.filter(estado=EstadoBloque.ACTIVO).count()}')
        self.stdout.write(f'Consultorios involucrados: {seed_qs.values("consultorio_id").distinct().count()}')
        self.stdout.write(self.style.SUCCESS('Escenarios de migracion cargados OK.'))

    def _asegurar_consultorios(self):
        specs = [
            ('Eco 1', 'Piso 2, Ala Norte'),
            ('Eco 2', 'Piso 2, Ala Norte'),
            ('Eco 3', 'Piso 1, Ala Sur'),
            ('Eco 4', 'Piso 1, Ala Sur'),
        ]
        resultado = {}
        for nombre, ubicacion in specs:
            consultorio, _ = Consultorio.objects.update_or_create(
                nombre=nombre,
                defaults={
                    'ubicacion': ubicacion,
                    'esta_activo': True,
                    'capacidad_pacientes_hora': 4,
                },
            )
            resultado[nombre] = consultorio
        return resultado

    def _asegurar_usuarios_base(self):
        data = [
            {
                'username': 'seed_staff_migracion',
                'first_name': 'Staff',
                'last_name': 'Migracion',
                'email': 'seed.staff.migracion@clegiales.local',
                'rol': 'medico_staff',
                'cargo': 'Ecografia General',
            },
            {
                'username': 'seed_residente_r2_migracion',
                'first_name': 'Residente',
                'last_name': 'R2 Migracion',
                'email': 'seed.residente.r2@clegiales.local',
                'rol': 'medico_residente',
                'cargo': 'Residente',
                'fecha_ingreso_residencia': date.today() - timedelta(days=450),
            },
            {
                'username': 'seed_jefe_migracion',
                'first_name': 'Jefe',
                'last_name': 'Migracion',
                'email': 'seed.jefe.migracion@clegiales.local',
                'rol': 'jefe_residentes',
                'cargo': 'Jefatura',
            },
        ]

        users = {}
        for item in data:
            defaults = {
                'first_name': item['first_name'],
                'last_name': item['last_name'],
                'email': item['email'],
                'rol': item['rol'],
                'cargo': item['cargo'],
                'perfil_completo': True,
            }
            if 'fecha_ingreso_residencia' in item:
                defaults['fecha_ingreso_residencia'] = item['fecha_ingreso_residencia']

            user, _ = User.objects.update_or_create(username=item['username'], defaults=defaults)
            user.set_password('demo1234')
            user.save()

            if user.rol == 'medico_residente' and hasattr(user, 'actualizar_anio_residencia'):
                user.actualizar_anio_residencia()

            users[item['username']] = user

        return users

    def _upsert_bloque(self, unique_filter, payload):
        bloque = BloqueHorario.objects.filter(**unique_filter).first()
        creado = bloque is None
        if creado:
            bloque = BloqueHorario(**payload)
        else:
            for key, value in payload.items():
                setattr(bloque, key, value)
        bloque.full_clean()
        bloque.save()
        return bloque, creado

    def _crear_escenarios(self, consultorios, users):
        jueves = DiaSemana.JUEVES

        escenarios = [
            # BLOQUE ORIGEN para probar migracion
            {
                'label': 'Origen staff',
                'unique': {
                    'consultorio': consultorios['Eco 1'],
                    'dia_semana': jueves,
                    'hora_inicio': time(15, 0),
                    'hora_fin': time(18, 0),
                    'observaciones': 'SEED_MIGRACION:ORIGEN_STAFF',
                },
                'payload': {
                    'consultorio': consultorios['Eco 1'],
                    'tipo_titular': TipoTitularBloque.NOMINAL,
                    'profesional_interno': users['seed_staff_migracion'],
                    'profesional_externo': None,
                    'profesional_asignado_temporal': None,
                    'equipo': None,
                    'dia_semana': jueves,
                    'hora_inicio': time(15, 0),
                    'hora_fin': time(18, 0),
                    'fecha_inicio_vigencia': date.today() - timedelta(days=30),
                    'fecha_fin_vigencia': None,
                    'tipo_actividad': TipoActividad.ECO_GENERAL,
                    'tipo_lista': TipoLista.LISTA_STAFF,
                    'permite_cobertura_residente': False,
                    'prioridad_cobertura': 3,
                    'competencia_requerida': None,
                    'estado': EstadoBloque.ACTIVO,
                    'observaciones': 'SEED_MIGRACION:ORIGEN_STAFF',
                    'creado_por': None,
                },
            },
            # ESCENARIO LIBRE (Eco 2: no bloque superpuesto en 15-18)
            {
                'label': 'Libre (sin superposicion)',
                'unique': {
                    'consultorio': consultorios['Eco 2'],
                    'dia_semana': jueves,
                    'hora_inicio': time(8, 0),
                    'hora_fin': time(11, 0),
                    'observaciones': 'SEED_MIGRACION:LIBRE_APOYO',
                },
                'payload': {
                    'consultorio': consultorios['Eco 2'],
                    'tipo_titular': TipoTitularBloque.NOMINAL,
                    'profesional_interno': users['seed_staff_migracion'],
                    'profesional_externo': None,
                    'profesional_asignado_temporal': None,
                    'equipo': None,
                    'dia_semana': jueves,
                    'hora_inicio': time(8, 0),
                    'hora_fin': time(11, 0),
                    'fecha_inicio_vigencia': date.today() - timedelta(days=30),
                    'fecha_fin_vigencia': None,
                    'tipo_actividad': TipoActividad.ECO_GENERAL,
                    'tipo_lista': TipoLista.LISTA_STAFF,
                    'permite_cobertura_residente': False,
                    'prioridad_cobertura': 3,
                    'competencia_requerida': None,
                    'estado': EstadoBloque.ACTIVO,
                    'observaciones': 'SEED_MIGRACION:LIBRE_APOYO',
                    'creado_por': None,
                },
            },
            # ESCENARIO BLANDO (Eco 3: solo R2 en 15-18)
            {
                'label': 'Blando R2',
                'unique': {
                    'consultorio': consultorios['Eco 3'],
                    'dia_semana': jueves,
                    'hora_inicio': time(15, 0),
                    'hora_fin': time(18, 0),
                    'observaciones': 'SEED_MIGRACION:BLANDO_R2',
                },
                'payload': {
                    'consultorio': consultorios['Eco 3'],
                    'tipo_titular': TipoTitularBloque.RESIDENTE_R2,
                    'profesional_interno': None,
                    'profesional_externo': None,
                    'profesional_asignado_temporal': users['seed_residente_r2_migracion'],
                    'equipo': None,
                    'dia_semana': jueves,
                    'hora_inicio': time(15, 0),
                    'hora_fin': time(18, 0),
                    'fecha_inicio_vigencia': date.today() - timedelta(days=30),
                    'fecha_fin_vigencia': None,
                    'tipo_actividad': TipoActividad.ECO_GENERAL,
                    'tipo_lista': TipoLista.LISTA_RESIDENTE_POOL,
                    'permite_cobertura_residente': True,
                    'prioridad_cobertura': 1,
                    'competencia_requerida': None,
                    'estado': EstadoBloque.ACTIVO,
                    'observaciones': 'SEED_MIGRACION:BLANDO_R2',
                    'creado_por': None,
                },
            },
            # ESCENARIO BLOQUEADO (Eco 4: jefe en 15-18)
            {
                'label': 'Bloqueado por jefe',
                'unique': {
                    'consultorio': consultorios['Eco 4'],
                    'dia_semana': jueves,
                    'hora_inicio': time(15, 0),
                    'hora_fin': time(18, 0),
                    'observaciones': 'SEED_MIGRACION:BLOQUEADO_JEFE',
                },
                'payload': {
                    'consultorio': consultorios['Eco 4'],
                    'tipo_titular': TipoTitularBloque.JEFES_RESIDENTES,
                    'profesional_interno': None,
                    'profesional_externo': None,
                    'profesional_asignado_temporal': users['seed_jefe_migracion'],
                    'equipo': None,
                    'dia_semana': jueves,
                    'hora_inicio': time(15, 0),
                    'hora_fin': time(18, 0),
                    'fecha_inicio_vigencia': date.today() - timedelta(days=30),
                    'fecha_fin_vigencia': None,
                    'tipo_actividad': TipoActividad.ECO_GENERAL,
                    'tipo_lista': TipoLista.LISTA_DOCENTE_COMO_STAFF,
                    'permite_cobertura_residente': False,
                    'prioridad_cobertura': 2,
                    'competencia_requerida': None,
                    'estado': EstadoBloque.ACTIVO,
                    'observaciones': 'SEED_MIGRACION:BLOQUEADO_JEFE',
                    'creado_por': None,
                },
            },
        ]

        for escenario in escenarios:
            bloque, created = self._upsert_bloque(escenario['unique'], escenario['payload'])
            estado = 'Creado' if created else 'Actualizado'
            self.stdout.write(f"  {estado}: {escenario['label']} (ID {bloque.pk})")