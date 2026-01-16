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
    BloqueHorario,
    EstadoBloque,
    DiaSemana
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
