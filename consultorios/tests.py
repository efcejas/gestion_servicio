"""
Tests para la app consultorios.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import time, date, timedelta

from .models import (
    Consultorio,
    ProfesionalExterno,
    AsignacionEquipoConsultorio,
    AusenciaCobertura,
    BloqueHorario,
    CategoriaProfesionalExterno,
    EstadoAusenciaCobertura,
    EstadoBloque,
    DiaSemana,
    MotivoAusencia,
    TipoLista,
)
from .utils import ConflictDetector
from equipos.models import EquipoImagen, AreaServicio

User = get_user_model()


class ConsultorioModelTest(TestCase):
    """Tests para el modelo Consultorio"""
    
    def setUp(self):
        self.consultorio = Consultorio.objects.create(
            nombre="Eco 1",
            ubicacion="Piso 2",
            capacidad_pacientes_hora=4
        )
    
    def test_creacion_consultorio(self):
        """Test de creación básica de consultorio"""
        self.assertEqual(self.consultorio.nombre, "Eco 1")
        self.assertTrue(self.consultorio.esta_activo)
    
    def test_str_consultorio(self):
        """Test del método __str__"""
        self.assertIn("Eco 1", str(self.consultorio))


class ProfesionalExternoModelTest(TestCase):
    """Tests para el modelo ProfesionalExterno"""
    
    def setUp(self):
        self.profesional = ProfesionalExterno.objects.create(
            nombre="Juan",
            apellido="Pérez",
            matricula="12345",
            especialidad="Ecografía"
        )
    
    def test_creacion_profesional_externo(self):
        """Test de creación de profesional externo"""
        self.assertEqual(self.profesional.nombre_completo(), "Juan Pérez")
        self.assertTrue(self.profesional.esta_activo)
    
    def test_matricula_unica(self):
        """Test que la matrícula sea única"""
        with self.assertRaises(Exception):
            ProfesionalExterno.objects.create(
                nombre="María",
                apellido="González",
                matricula="12345"  # Duplicada
            )


class BloqueHorarioModelTest(TestCase):
    """Tests para el modelo BloqueHorario"""
    
    def setUp(self):
        # Crear consultorio
        self.consultorio = Consultorio.objects.create(
            nombre="Eco 1",
            ubicacion="Piso 2"
        )
        
        # Crear profesional interno
        self.user = User.objects.create_user(
            username='medico1',
            password='test123',
            first_name='Carlos',
            last_name='Rodríguez'
        )
        
        # Crear profesional externo
        self.profesional_externo = ProfesionalExterno.objects.create(
            nombre="Ana",
            apellido="Martínez",
            matricula="67890"
        )
    
    def test_bloque_con_profesional_interno(self):
        """Test de bloque horario con profesional interno"""
        bloque = BloqueHorario.objects.create(
            consultorio=self.consultorio,
            profesional_interno=self.user,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(9, 0),
            hora_fin=time(12, 0)
        )
        
        self.assertIn("Carlos Rodríguez", bloque.nombre_profesional())
        self.assertEqual(bloque.duracion_horas(), 3.0)
    
    def test_bloque_con_profesional_externo(self):
        """Test de bloque horario con profesional externo"""
        bloque = BloqueHorario.objects.create(
            consultorio=self.consultorio,
            profesional_externo=self.profesional_externo,
            dia_semana=DiaSemana.MARTES,
            hora_inicio=time(14, 0),
            hora_fin=time(18, 0)
        )
        
        self.assertIn("Ana Martínez", bloque.nombre_profesional())
        self.assertEqual(bloque.duracion_horas(), 4.0)
    
    def test_validacion_sin_profesional(self):
        """Test que falla si no hay profesional asignado"""
        bloque = BloqueHorario(
            consultorio=self.consultorio,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(9, 0),
            hora_fin=time(12, 0)
        )
        
        with self.assertRaises(ValidationError):
            bloque.full_clean()
    
    def test_validacion_ambos_profesionales(self):
        """Test que falla si se asignan ambos tipos de profesional"""
        bloque = BloqueHorario(
            consultorio=self.consultorio,
            profesional_interno=self.user,
            profesional_externo=self.profesional_externo,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(9, 0),
            hora_fin=time(12, 0)
        )
        
        with self.assertRaises(ValidationError):
            bloque.full_clean()
    
    def test_validacion_horario_invalido(self):
        """Test que falla si hora_inicio >= hora_fin"""
        bloque = BloqueHorario(
            consultorio=self.consultorio,
            profesional_interno=self.user,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(12, 0),
            hora_fin=time(9, 0)  # Hora fin antes que inicio
        )
        
        with self.assertRaises(ValidationError):
            bloque.full_clean()
    
    def test_vigencia_bloque(self):
        """Test de verificación de vigencia"""
        # Bloque vigente
        bloque_vigente = BloqueHorario.objects.create(
            consultorio=self.consultorio,
            profesional_interno=self.user,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(9, 0),
            hora_fin=time(12, 0),
            fecha_inicio_vigencia=date.today() - timedelta(days=10),
            estado=EstadoBloque.ACTIVO
        )
        
        self.assertTrue(bloque_vigente.esta_vigente())
        
        # Bloque no vigente (finalizado)
        bloque_finalizado = BloqueHorario.objects.create(
            consultorio=self.consultorio,
            profesional_externo=self.profesional_externo,
            dia_semana=DiaSemana.MARTES,
            hora_inicio=time(14, 0),
            hora_fin=time(18, 0),
            estado=EstadoBloque.FINALIZADO
        )
        
        self.assertFalse(bloque_finalizado.esta_vigente())


class ManagersTest(TestCase):
    """Tests para los managers personalizados (Fase 2)"""
    
    def setUp(self):
        # Crear consultorios
        self.consultorio1 = Consultorio.objects.create(nombre="Eco 1")
        self.consultorio2 = Consultorio.objects.create(nombre="Eco 2", esta_activo=False)
        
        # Crear usuario
        self.user = User.objects.create_user(
            username='medico1',
            password='test123',
            first_name='Carlos',
            last_name='Rodriguez'
        )
        
        # Crear profesional externo
        self.profesional_externo = ProfesionalExterno.objects.create(
            nombre="Ana",
            apellido="Martinez",
            matricula="67890"
        )
        
        # Crear bloques
        self.bloque1 = BloqueHorario.objects.create(
            consultorio=self.consultorio1,
            profesional_interno=self.user,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(9, 0),
            hora_fin=time(12, 0),
            estado=EstadoBloque.ACTIVO
        )
        
        self.bloque2 = BloqueHorario.objects.create(
            consultorio=self.consultorio1,
            profesional_externo=self.profesional_externo,
            dia_semana=DiaSemana.MARTES,
            hora_inicio=time(14, 0),
            hora_fin=time(18, 0),
            estado=EstadoBloque.PAUSADO
        )
    
    def test_consultorio_manager_activos(self):
        """Test que el manager retorna solo consultorios activos"""
        activos = Consultorio.objects.activos()
        self.assertEqual(activos.count(), 1)
        self.assertEqual(activos.first(), self.consultorio1)
    
    def test_bloque_manager_activos(self):
        """Test que el manager retorna solo bloques activos"""
        activos = BloqueHorario.objects.activos()
        self.assertEqual(activos.count(), 1)
        self.assertEqual(activos.first(), self.bloque1)
    
    def test_bloque_manager_por_consultorio(self):
        """Test filtrado por consultorio"""
        bloques = BloqueHorario.objects.por_consultorio(self.consultorio1)
        self.assertEqual(bloques.count(), 2)
    
    def test_bloque_manager_por_dia_semana(self):
        """Test filtrado por dia de semana"""
        bloques = BloqueHorario.objects.por_dia_semana(DiaSemana.LUNES)
        self.assertEqual(bloques.count(), 1)
        self.assertEqual(bloques.first(), self.bloque1)


class ConflictDetectorTest(TestCase):
    """Tests para detección de conflictos (Fase 2)"""
    
    def setUp(self):
        # Crear consultorio
        self.consultorio = Consultorio.objects.create(nombre="Eco 1")
        
        # Crear usuarios
        self.user1 = User.objects.create_user(
            username='medico1',
            password='test123',
            first_name='Carlos',
            last_name='Rodriguez'
        )
        
        self.user2 = User.objects.create_user(
            username='medico2',
            password='test123',
            first_name='Maria',
            last_name='Gonzalez'
        )
        
        # Crear bloque existente
        self.bloque_existente = BloqueHorario.objects.create(
            consultorio=self.consultorio,
            profesional_interno=self.user1,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(9, 0),
            hora_fin=time(12, 0),
            estado=EstadoBloque.ACTIVO
        )
    
    def test_detectar_conflicto_consultorio(self):
        """Test detección de conflicto en consultorio"""
        resultado = ConflictDetector.verificar_conflictos(
            consultorio=self.consultorio,
            profesional_interno=self.user2,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(10, 0),  # Se superpone con bloque existente
            hora_fin=time(13, 0)
        )
        
        self.assertTrue(resultado['tiene_conflictos'])
        self.assertIsNotNone(resultado['conflictos_consultorio'])
    
    def test_sin_conflicto_diferente_horario(self):
        """Test sin conflicto cuando el horario no se superpone"""
        resultado = ConflictDetector.verificar_conflictos(
            consultorio=self.consultorio,
            profesional_interno=self.user2,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(14, 0),  # No se superpone
            hora_fin=time(17, 0)
        )
        
        self.assertFalse(resultado['tiene_conflictos'])
    
    def test_detectar_conflicto_profesional(self):
        """Test detección de conflicto de profesional en múltiples consultorios"""
        # Crear segundo consultorio
        consultorio2 = Consultorio.objects.create(nombre="Eco 2")
        
        # Intentar asignar al mismo profesional en el mismo horario
        resultado = ConflictDetector.verificar_conflictos(
            consultorio=consultorio2,
            profesional_interno=self.user1,  # Mismo profesional
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(10, 0),  # Se superpone
            hora_fin=time(13, 0)
        )
        
        self.assertTrue(resultado['tiene_conflictos'])
        self.assertIsNotNone(resultado['conflictos_profesional'])
    
    def test_validacion_bloque_con_conflicto(self):
        """Test que la validación de bloque lanza error con conflictos"""
        # Crear bloque que entra en conflicto
        bloque_conflictivo = BloqueHorario(
            consultorio=self.consultorio,
            profesional_interno=self.user2,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(10, 0),
            hora_fin=time(13, 0),
            estado=EstadoBloque.ACTIVO
        )
        
        with self.assertRaises(ValidationError):
            bloque_conflictivo.full_clean()
    
    def test_disponibilidad_consultorio(self):
        """Test obtención de disponibilidad de consultorio"""
        disponibilidad = ConflictDetector.obtener_disponibilidad_consultorio(
            consultorio=self.consultorio,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0)
        )
        
        self.assertFalse(disponibilidad['esta_disponible'])
        self.assertEqual(len(disponibilidad['bloques_ocupados']), 1)
    
    def test_sugerir_horarios_disponibles(self):
        """Test sugerencia de horarios disponibles"""
        sugerencias = ConflictDetector.sugerir_horarios_disponibles(
            consultorio=self.consultorio,
            dia_semana=DiaSemana.LUNES,
            duracion_horas=2
        )
        
        self.assertIsInstance(sugerencias, list)
        self.assertTrue(len(sugerencias) > 0)
        
        # Verificar que ninguna sugerencia se superpone con el bloque existente
        for hora_inicio, hora_fin in sugerencias:
            # No debe superponerse con 9:00-12:00
            self.assertTrue(
                hora_fin <= self.bloque_existente.hora_inicio or
                hora_inicio >= self.bloque_existente.hora_fin
            )


class BloqueHorarioReglasOperativasTest(TestCase):
    """Tests de reglas operativas para listas y coberturas."""

    def setUp(self):
        self.consultorio = Consultorio.objects.create(nombre="Eco 3")
        self.user = User.objects.create_user(
            username='staff1',
            password='test123',
            first_name='Staff',
            last_name='Uno'
        )

    def test_lista_pool_requiere_cobertura_residente(self):
        bloque = BloqueHorario(
            consultorio=self.consultorio,
            profesional_interno=self.user,
            dia_semana=DiaSemana.MIERCOLES,
            hora_inicio=time(8, 0),
            hora_fin=time(12, 0),
            tipo_lista=TipoLista.LISTA_RESIDENTE_POOL,
            permite_cobertura_residente=False,
        )

        with self.assertRaises(ValidationError):
            bloque.full_clean()

    def test_lista_especializada_requiere_competencia(self):
        bloque = BloqueHorario(
            consultorio=self.consultorio,
            profesional_interno=self.user,
            dia_semana=DiaSemana.JUEVES,
            hora_inicio=time(8, 0),
            hora_fin=time(10, 0),
            tipo_lista=TipoLista.LISTA_ESPECIALIZADA,
            competencia_requerida='',
        )

        with self.assertRaises(ValidationError):
            bloque.full_clean()

    def test_profesional_externo_categoria_por_defecto_staff(self):
        externo = ProfesionalExterno.objects.create(
            nombre='Lucia',
            apellido='Perez',
            matricula='MAT-99999',
        )
        self.assertEqual(externo.categoria, CategoriaProfesionalExterno.STAFF_EXTERNO)


class ConsultorioEquiposAsignadosTest(TestCase):
    """Tests para asegurar que equipos_asignados no duplique resultados."""

    def setUp(self):
        self.consultorio = Consultorio.objects.create(nombre='Eco Equipos')
        self.equipo = EquipoImagen.objects.create(
            nombre='Eco GE',
            area=AreaServicio.ECOGRAFIA,
            fabricante='GE',
            modelo='LOGIQ',
        )

    def test_equipos_asignados_no_duplica(self):
        hoy = timezone.now().date()
        AsignacionEquipoConsultorio.objects.create(
            consultorio=self.consultorio,
            equipo=self.equipo,
            es_permanente=True,
            fecha_inicio=hoy - timedelta(days=1),
        )

        asignados = list(self.consultorio.equipos_asignados())
        self.assertEqual(len(asignados), 1)


class SugerirCoberturaServiceTest(TestCase):
    """Tests para el servicio sugerir_cobertura en consultorios/services.py."""

    def setUp(self):
        from consultorios.models import TipoActividad
        self.consultorio = Consultorio.objects.create(nombre='Eco Coberturas')
        self.medico = User.objects.create_user(
            username='staff_cob_test',
            password='x',
            rol='medico_staff',
            first_name='Ana',
            last_name='Torres',
        )
        self.residente1 = User.objects.create_user(
            username='residente_cob_1',
            password='x',
            rol='medico_residente',
            first_name='Pedro',
            last_name='Gomez',
            anio_residencia=2,
        )
        self.residente2 = User.objects.create_user(
            username='residente_cob_2',
            password='x',
            rol='medico_residente',
            first_name='Laura',
            last_name='Vidal',
            anio_residencia=3,
        )
        self.bloque_pool = BloqueHorario.objects.create(
            consultorio=self.consultorio,
            profesional_interno=self.residente1,
            dia_semana=DiaSemana.SABADO,
            hora_inicio=time(8, 0),
            hora_fin=time(12, 0),
            tipo_lista=TipoLista.LISTA_RESIDENTE_POOL,
            permite_cobertura_residente=True,
            prioridad_cobertura=1,
        )
        self.bloque_sin_cobertura = BloqueHorario.objects.create(
            consultorio=self.consultorio,
            profesional_interno=self.medico,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(9, 0),
            hora_fin=time(13, 0),
            tipo_lista=TipoLista.LISTA_STAFF,
            permite_cobertura_residente=False,
        )

    def test_sugerir_cobertura_retorna_candidatos(self):
        """Bloque pool con residentes disponibles → lista de candidatos."""
        from consultorios.services import sugerir_cobertura
        resultado = sugerir_cobertura(self.bloque_pool)
        self.assertTrue(resultado['exito'])
        self.assertGreater(len(resultado['candidatos']), 0)

    def test_sugerir_cobertura_candidato_tiene_campos(self):
        """Cada candidato expone los campos esperados."""
        from consultorios.services import sugerir_cobertura
        resultado = sugerir_cobertura(self.bloque_pool)
        candidato = resultado['candidatos'][0]
        self.assertIn('usuario', candidato)
        self.assertIn('nombre', candidato)
        self.assertIn('anio_residencia', candidato)
        self.assertIn('justificacion', candidato)

    def test_sugerir_cobertura_orden_por_anio_desc(self):
        """Residentes de mayor año van primero."""
        from consultorios.services import sugerir_cobertura
        resultado = sugerir_cobertura(self.bloque_pool)
        anios = [c['anio_residencia'] for c in resultado['candidatos']]
        self.assertEqual(anios, sorted(anios, reverse=True))

    def test_sugerir_cobertura_bloque_no_admite_lanza_error(self):
        """Bloque con permite_cobertura_residente=False → BloqueNoCubreError."""
        from consultorios.services import sugerir_cobertura, BloqueNoCubreError
        with self.assertRaises(BloqueNoCubreError):
            sugerir_cobertura(self.bloque_sin_cobertura)

    def test_sugerir_cobertura_sin_residentes_lanza_error(self):
        """Sin ningún residente activo → SinResidentesDisponiblesError."""
        from consultorios.services import sugerir_cobertura, SinResidentesDisponiblesError
        User.objects.filter(rol='medico_residente').update(is_active=False)
        with self.assertRaises(SinResidentesDisponiblesError):
            sugerir_cobertura(self.bloque_pool)

    def test_bloques_con_cobertura_posible_filtra_correctamente(self):
        """Solo retorna bloques activos con cobertura habilitada."""
        from consultorios.services import bloques_con_cobertura_posible
        bloques = bloques_con_cobertura_posible()
        pks = [b.pk for b in bloques]
        self.assertIn(self.bloque_pool.pk, pks)
        self.assertNotIn(self.bloque_sin_cobertura.pk, pks)

    def test_sugerir_cobertura_prioriza_menor_historial_confirmado(self):
        """Con historial real, sugiere primero al residente con menos coberturas previas."""
        bloque_historial = BloqueHorario.objects.create(
            consultorio=self.consultorio,
            profesional_interno=self.medico,
            dia_semana=DiaSemana.SABADO,
            hora_inicio=time(13, 0),
            hora_fin=time(16, 0),
            tipo_lista=TipoLista.LISTA_RESIDENTE_POOL,
            permite_cobertura_residente=True,
            estado=EstadoBloque.ACTIVO,
        )

        AusenciaCobertura.objects.create(
            bloque=bloque_historial,
            fecha_ausencia=timezone.now().date() - timedelta(days=7),
            profesional_ausente_interno=self.medico,
            residente_asignado=self.residente2,
            estado=EstadoAusenciaCobertura.CONFIRMADA,
        )

        from consultorios.services import sugerir_cobertura
        resultado = sugerir_cobertura(self.bloque_pool)
        self.assertEqual(resultado['candidatos'][0]['usuario'].pk, self.residente1.pk)
        self.assertEqual(resultado['candidatos'][0]['coberturas_previas_dia'], 0)


class AusenciaCoberturaModelTest(TestCase):
    """Tests de dominio para el circuito de ausencias/coberturas."""

    def setUp(self):
        self.consultorio = Consultorio.objects.create(nombre='Eco Ausencias')
        self.staff = User.objects.create_user(
            username='staff_aus_1',
            password='x',
            rol='medico_staff',
            first_name='Marta',
            last_name='Sosa',
        )
        self.staff2 = User.objects.create_user(
            username='staff_aus_2',
            password='x',
            rol='medico_staff',
            first_name='Pablo',
            last_name='Rios',
        )
        self.residente = User.objects.create_user(
            username='res_aus_1',
            password='x',
            rol='medico_residente',
            first_name='Nora',
            last_name='Luna',
            anio_residencia=3,
        )

        self.bloque = BloqueHorario.objects.create(
            consultorio=self.consultorio,
            profesional_interno=self.staff,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(8, 0),
            hora_fin=time(12, 0),
            tipo_lista=TipoLista.LISTA_DOCENTE_COMO_STAFF,
            permite_cobertura_residente=True,
            estado=EstadoBloque.ACTIVO,
        )

    def test_creacion_ausencia_basica_ok(self):
        ausencia = AusenciaCobertura(
            bloque=self.bloque,
            fecha_ausencia=timezone.now().date(),
            profesional_ausente_interno=self.staff,
            motivo=MotivoAusencia.ENFERMEDAD,
            reportado_por=self.staff,
        )
        ausencia.full_clean()
        ausencia.save()

        self.assertEqual(ausencia.estado, EstadoAusenciaCobertura.REPORTADA)
        self.assertEqual(ausencia.nombre_profesional_ausente(), self.staff.get_full_name())

    def test_confirmada_requiere_residente_asignado(self):
        ausencia = AusenciaCobertura(
            bloque=self.bloque,
            fecha_ausencia=timezone.now().date(),
            profesional_ausente_interno=self.staff,
            estado=EstadoAusenciaCobertura.CONFIRMADA,
        )

        with self.assertRaises(ValidationError):
            ausencia.full_clean()

    def test_no_permite_dos_ausentes(self):
        externo = ProfesionalExterno.objects.create(
            nombre='Carla',
            apellido='Vega',
            matricula='MAT-AUS-001',
        )
        ausencia = AusenciaCobertura(
            bloque=self.bloque,
            fecha_ausencia=timezone.now().date(),
            profesional_ausente_interno=self.staff,
            profesional_ausente_externo=externo,
        )

        with self.assertRaises(ValidationError):
            ausencia.full_clean()

    def test_residente_asignado_debe_ser_rol_residente(self):
        ausencia = AusenciaCobertura(
            bloque=self.bloque,
            fecha_ausencia=timezone.now().date(),
            profesional_ausente_interno=self.staff,
            residente_asignado=self.staff2,
            estado=EstadoAusenciaCobertura.CONFIRMADA,
        )

        with self.assertRaises(ValidationError):
            ausencia.full_clean()

    def test_unique_bloque_fecha(self):
        hoy = timezone.now().date()
        AusenciaCobertura.objects.create(
            bloque=self.bloque,
            fecha_ausencia=hoy,
            profesional_ausente_interno=self.staff,
        )

        duplicada = AusenciaCobertura(
            bloque=self.bloque,
            fecha_ausencia=hoy,
            profesional_ausente_interno=self.staff,
        )
        with self.assertRaises(Exception):
            duplicada.save()


# ---------------------------------------------------------------------------
# Tests de las vistas de ausencias
# ---------------------------------------------------------------------------

class ReportarAusenciaViewTest(TestCase):
    """Tests del flujo HTTP para reportar ausencias y confirmar coberturas."""

    def setUp(self):
        self.consultorio = Consultorio.objects.create(nombre='Eco Test View')

        self.gestor = User.objects.create_user(
            username='gestor_view',
            password='pass',
            rol='jefe_servicio',
            first_name='Ana',
            last_name='Jefa',
            perfil_completo=True,
        )
        self.medico = User.objects.create_user(
            username='medico_view',
            password='pass',
            rol='medico_staff',
            first_name='Luis',
            last_name='Médico',
            perfil_completo=True,
        )
        self.residente = User.objects.create_user(
            username='residente_view',
            password='pass',
            rol='medico_residente',
            first_name='Pedro',
            last_name='Residente',
            anio_residencia=2,
            perfil_completo=True,
        )

        self.bloque = BloqueHorario.objects.create(
            consultorio=self.consultorio,
            profesional_interno=self.medico,
            dia_semana=DiaSemana.MARTES,
            hora_inicio=time(9, 0),
            hora_fin=time(13, 0),
            tipo_lista=TipoLista.LISTA_DOCENTE_COMO_STAFF,
            permite_cobertura_residente=True,
            estado=EstadoBloque.ACTIVO,
        )

    def _url_reportar(self):
        from django.urls import reverse
        return reverse('consultorios:reportar_ausencia', kwargs={'pk': self.bloque.pk})

    def _url_confirmar(self, ausencia_pk, residente_pk):
        from django.urls import reverse
        return reverse(
            'consultorios:confirmar_cobertura',
            kwargs={'ausencia_pk': ausencia_pk, 'residente_pk': residente_pk}
        )

    def test_get_requiere_login(self):
        response = self.client.get(self._url_reportar())
        self.assertNotEqual(response.status_code, 200)  # redirige a login

    def test_get_deniega_sin_permiso(self):
        """Un residente no puede reportar ausencias (rol sin permiso de gestión)."""
        self.client.force_login(self.residente)
        response = self.client.get(self._url_reportar())
        self.assertEqual(response.status_code, 403)

    def test_get_ok_para_gestor(self):
        self.client.force_login(self.gestor)
        response = self.client.get(self._url_reportar())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'consultorios/reportar_ausencia.html')

    def test_post_crea_ausencia_y_muestra_candidatos(self):
        self.client.force_login(self.gestor)
        fecha = (timezone.now() + timezone.timedelta(days=3)).date()
        response = self.client.post(self._url_reportar(), {
            'fecha_ausencia': fecha.isoformat(),
            'motivo': MotivoAusencia.ENFERMEDAD,
            'detalle_motivo': 'Gripe',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AusenciaCobertura.objects.filter(bloque=self.bloque, fecha_ausencia=fecha).exists()
        )
        ausencia = AusenciaCobertura.objects.get(bloque=self.bloque, fecha_ausencia=fecha)
        self.assertEqual(ausencia.motivo, MotivoAusencia.ENFERMEDAD)
        self.assertEqual(ausencia.reportado_por, self.gestor)
        # El estado debe ser PROPUESTA (hay al menos un residente disponible)
        self.assertEqual(ausencia.estado, EstadoAusenciaCobertura.PROPUESTA)

    def test_post_duplicado_no_crea_segunda_ausencia(self):
        self.client.force_login(self.gestor)
        fecha = (timezone.now() + timezone.timedelta(days=4)).date()
        AusenciaCobertura.objects.create(
            bloque=self.bloque,
            fecha_ausencia=fecha,
            profesional_ausente_interno=self.medico,
            motivo=MotivoAusencia.LICENCIA,
        )
        response = self.client.post(self._url_reportar(), {
            'fecha_ausencia': fecha.isoformat(),
            'motivo': MotivoAusencia.OTRO,
            'detalle_motivo': '',
        })
        self.assertEqual(response.status_code, 200)
        # No debe crearse una segunda ausencia
        self.assertEqual(
            AusenciaCobertura.objects.filter(bloque=self.bloque, fecha_ausencia=fecha).count(), 1
        )

    def test_confirmar_cobertura_actualiza_estado(self):
        self.client.force_login(self.gestor)
        fecha = (timezone.now() + timezone.timedelta(days=5)).date()
        ausencia = AusenciaCobertura.objects.create(
            bloque=self.bloque,
            fecha_ausencia=fecha,
            profesional_ausente_interno=self.medico,
            motivo=MotivoAusencia.PERSONAL,
            estado=EstadoAusenciaCobertura.PROPUESTA,
            residente_sugerido=self.residente,
        )
        response = self.client.post(self._url_confirmar(ausencia.pk, self.residente.pk))
        self.assertRedirects(response, '/consultorios/ausencias/pendientes/', fetch_redirect_response=False)
        ausencia.refresh_from_db()
        self.assertEqual(ausencia.estado, EstadoAusenciaCobertura.CONFIRMADA)
        self.assertEqual(ausencia.residente_asignado, self.residente)

    def test_confirmar_rechaza_usuario_sin_rol_residente(self):
        self.client.force_login(self.gestor)
        fecha = (timezone.now() + timezone.timedelta(days=6)).date()
        ausencia = AusenciaCobertura.objects.create(
            bloque=self.bloque,
            fecha_ausencia=fecha,
            profesional_ausente_interno=self.medico,
            motivo=MotivoAusencia.CAPACITACION,
        )
        response = self.client.post(self._url_confirmar(ausencia.pk, self.medico.pk))
        self.assertEqual(response.status_code, 403)


class FechasBloquEnRangoTest(TestCase):
    """Tests del helper _fechas_del_bloque_en_rango."""

    def _helper(self, dia_semana, inicio, fin):
        from consultorios.views import _fechas_del_bloque_en_rango
        return _fechas_del_bloque_en_rango(dia_semana, inicio, fin)

    def test_dia_unico_mismo_dia(self):
        """Un día único que coincide con el dia_semana del bloque → 1 fecha."""
        # 5 de mayo 2026 es Martes (weekday=1)
        fecha = date(2026, 5, 5)
        result = self._helper(dia_semana=1, inicio=fecha, fin=fecha)
        self.assertEqual(result, [fecha])

    def test_dia_unico_no_coincide(self):
        """Si el día único no es el del bloque → lista vacía."""
        fecha = date(2026, 5, 5)  # Martes
        result = self._helper(dia_semana=0, inicio=fecha, fin=fecha)  # Lunes
        self.assertEqual(result, [])

    def test_rango_vacaciones_dos_semanas(self):
        """
        Rango 18 may – 31 may 2026 (Lunes = weekday 0):
        Lunes 18/5 y 25/5 → 2 fechas.
        """
        inicio = date(2026, 5, 18)  # Lunes
        fin = date(2026, 5, 31)
        result = self._helper(dia_semana=0, inicio=inicio, fin=fin)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], date(2026, 5, 18))
        self.assertEqual(result[1], date(2026, 5, 25))

    def test_fecha_fin_antes_de_inicio_retorna_vacio(self):
        result = self._helper(
            dia_semana=0,
            inicio=date(2026, 6, 1),
            fin=date(2026, 5, 1),
        )
        self.assertEqual(result, [])

    def test_tope_365_dias(self):
        """Un rango mayor a 365 días no explota; retorna a lo sumo 52/53 fechas."""
        inicio = date(2026, 1, 1)
        fin = date(2028, 1, 1)  # > 1 año
        result = self._helper(dia_semana=0, inicio=inicio, fin=fin)
        # 365 días → como máximo 52 lunes
        self.assertLessEqual(len(result), 53)


class ReportarAusenciaRangoViewTest(TestCase):
    """Tests del flujo POST con rango de fechas."""

    def setUp(self):
        self.consultorio = Consultorio.objects.create(nombre='Eco Rango')
        self.gestor = User.objects.create_user(
            username='gestor_rango',
            password='pass',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.medico = User.objects.create_user(
            username='medico_rango',
            password='pass',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.residente = User.objects.create_user(
            username='residente_rango',
            password='pass',
            rol='medico_residente',
            anio_residencia=1,
            perfil_completo=True,
        )
        # Bloque los lunes
        self.bloque = BloqueHorario.objects.create(
            consultorio=self.consultorio,
            profesional_interno=self.medico,
            dia_semana=DiaSemana.LUNES,
            hora_inicio=time(8, 0),
            hora_fin=time(12, 0),
            tipo_lista=TipoLista.LISTA_STAFF,
            permite_cobertura_residente=True,
            estado=EstadoBloque.ACTIVO,
        )

    def _url(self):
        from django.urls import reverse
        return reverse('consultorios:reportar_ausencia', kwargs={'pk': self.bloque.pk})

    def test_rango_dos_semanas_crea_dos_ausencias(self):
        """
        Rango 18–31 may 2026 con bloque los lunes → debe crear 2 ausencias (18/5 y 25/5).
        """
        self.client.force_login(self.gestor)
        response = self.client.post(self._url(), {
            'fecha_ausencia': '2026-05-18',
            'fecha_fin_ausencia': '2026-05-31',
            'motivo': MotivoAusencia.LICENCIA,
            'detalle_motivo': 'Vacaciones anuales',
        })
        # Modo rango → redirige a grilla
        self.assertRedirects(response, '/consultorios/grilla/', fetch_redirect_response=False)
        self.assertEqual(
            AusenciaCobertura.objects.filter(bloque=self.bloque).count(), 2
        )
        fechas = list(
            AusenciaCobertura.objects.filter(bloque=self.bloque)
            .values_list('fecha_ausencia', flat=True)
            .order_by('fecha_ausencia')
        )
        self.assertEqual(fechas[0], date(2026, 5, 18))
        self.assertEqual(fechas[1], date(2026, 5, 25))

    def test_rango_omite_duplicados(self):
        """Si ya existe una ausencia para una de las fechas del rango, la omite."""
        AusenciaCobertura.objects.create(
            bloque=self.bloque,
            fecha_ausencia=date(2026, 5, 18),
            profesional_ausente_interno=self.medico,
            motivo=MotivoAusencia.OTRO,
        )
        self.client.force_login(self.gestor)
        self.client.post(self._url(), {
            'fecha_ausencia': '2026-05-18',
            'fecha_fin_ausencia': '2026-05-31',
            'motivo': MotivoAusencia.LICENCIA,
            'detalle_motivo': '',
        })
        # Solo se crea la del 25/5; la del 18/5 ya existía
        self.assertEqual(
            AusenciaCobertura.objects.filter(bloque=self.bloque).count(), 2
        )

    def test_form_rechaza_fin_antes_de_inicio(self):
        self.client.force_login(self.gestor)
        response = self.client.post(self._url(), {
            'fecha_ausencia': '2026-06-01',
            'fecha_fin_ausencia': '2026-05-01',
            'motivo': MotivoAusencia.OTRO,
            'detalle_motivo': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())
        self.assertEqual(AusenciaCobertura.objects.filter(bloque=self.bloque).count(), 0)
