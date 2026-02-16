from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date
from .models import Estudios, RegistroEstudiosPorMedico, DiaSinPacientes

# [ELIMINADO - 16 de febrero 2026]
# Import de RegistroProcedimientosIntervensionismo eliminado

User = get_user_model()


class EstudiosModelTest(TestCase):
    """Pruebas para el modelo Estudios"""

    def test_crear_estudio(self):
        """Verifica que se puede crear un estudio"""
        estudio = Estudios.objects.create(
            nombre='Ecografía abdominal',
            tipo='ECO',
            conteo_regiones=1
        )
        self.assertEqual(estudio.nombre, 'Ecografía abdominal')
        self.assertEqual(estudio.tipo, 'ECO')
        self.assertEqual(estudio.conteo_regiones, 1)

    def test_estudio_str(self):
        """Verifica la representación en string del estudio"""
        estudio = Estudios.objects.create(
            nombre='Tomografía de tórax',
            tipo='TOM',
            conteo_regiones=2
        )
        self.assertEqual(str(estudio), 'Tomografía de tórax')

    def test_tipos_estudio_disponibles(self):
        """Verifica que todos los tipos de estudio están disponibles"""
        tipos = [choice[0] for choice in Estudios.TIPO_ESTUDIO_CHOICES]
        self.assertIn('ECO', tipos)
        self.assertIn('TOM', tipos)
        self.assertIn('RES', tipos)
        self.assertIn('RAD', tipos)

    def test_estudio_nombre_unico(self):
        """Verifica que el nombre del estudio debe ser único"""
        from django.db import IntegrityError
        Estudios.objects.create(
            nombre='Estudio único',
            tipo='ECO',
            conteo_regiones=1
        )
        with self.assertRaises(IntegrityError):
            Estudios.objects.create(
                nombre='Estudio único',  # Nombre duplicado
                tipo='TOM',
                conteo_regiones=2
            )


class RegistroEstudiosPorMedicoModelTest(TestCase):
    """Pruebas para el modelo RegistroEstudiosPorMedico"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.user = User.objects.create_user(
            username='drtest',
            password='testpass123',
            first_name='Test',
            last_name='Doctor'
        )
        self.estudio1 = Estudios.objects.create(
            nombre='Ecografía abdominal',
            tipo='ECO',
            conteo_regiones=1
        )
        self.estudio2 = Estudios.objects.create(
            nombre='Ecografía pélvica',
            tipo='ECO',
            conteo_regiones=1
        )

    def test_crear_registro(self):
        """Verifica que se puede crear un registro de estudio"""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.user,
            nombre_paciente='Juan',
            apellido_paciente='Pérez',
            dni_paciente='12345678',
            fecha_del_informe=date.today(),
            cantidad_estudio=1
        )
        registro.estudio.add(self.estudio1)
        
        self.assertEqual(registro.medico, self.user)
        self.assertEqual(registro.nombre_paciente, 'Juan')
        self.assertEqual(registro.estudio.count(), 1)

    def test_registro_str(self):
        """Verifica la representación en string del registro"""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.user,
            nombre_paciente='Juan',
            apellido_paciente='Pérez',
            dni_paciente='12345678',
            fecha_del_informe=date.today()
        )
        str_registro = str(registro)
        self.assertIn(self.user.username, str_registro)

    def test_total_regiones_un_estudio(self):
        """Verifica el cálculo de regiones con un estudio"""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.user,
            nombre_paciente='Juan',
            apellido_paciente='Pérez',
            dni_paciente='12345678',
            fecha_del_informe=date.today(),
            cantidad_estudio=2
        )
        registro.estudio.add(self.estudio1)  # 1 región
        
        # 1 región * 2 cantidad = 2 regiones totales
        self.assertEqual(registro.total_regiones(), 2)

    def test_total_regiones_multiples_estudios(self):
        """Verifica el cálculo de regiones con múltiples estudios"""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.user,
            nombre_paciente='María',
            apellido_paciente='González',
            dni_paciente='87654321',
            fecha_del_informe=date.today(),
            cantidad_estudio=1
        )
        registro.estudio.add(self.estudio1, self.estudio2)  # 1 + 1 = 2 regiones
        
        self.assertEqual(registro.total_regiones(), 2)

    def test_fecha_registro_automatica(self):
        """Verifica que la fecha de registro se asigna automáticamente"""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.user,
            nombre_paciente='Pedro',
            apellido_paciente='López',
            dni_paciente='11111111',
            fecha_del_informe=date.today()
        )
        self.assertIsNotNone(registro.fecha_registro)


class DiaSinPacientesModelTest(TestCase):
    """Pruebas para el modelo DiaSinPacientes"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.user = User.objects.create_user(
            username='drtest',
            password='testpass123',
            first_name='Test',
            last_name='Doctor'
        )

    def test_crear_dia_sin_pacientes(self):
        """Verifica que se puede crear un registro de día sin pacientes"""
        dia = DiaSinPacientes.objects.create(
            medico=self.user,
            fecha=date.today(),
            observacion='No hubo pacientes programados'
        )
        self.assertEqual(dia.medico, self.user)
        self.assertEqual(dia.fecha, date.today())

    def test_dia_sin_pacientes_str(self):
        """Verifica la representación en string"""
        dia = DiaSinPacientes.objects.create(
            medico=self.user,
            fecha=date.today()
        )
        str_dia = str(dia)
        self.assertIn(self.user.get_full_name(), str_dia)

    def test_unique_together_medico_fecha(self):
        """Verifica que no se pueden crear dos registros para el mismo médico y fecha"""
        from django.db import IntegrityError
        DiaSinPacientes.objects.create(
            medico=self.user,
            fecha=date.today()
        )
        with self.assertRaises(IntegrityError):
            DiaSinPacientes.objects.create(
                medico=self.user,
                fecha=date.today()  # Misma fecha para el mismo médico
            )


# [ANULADO - 16 de febrero 2026]
# Tests de RegistroProcedimientosIntervensionismo eliminados
# Razón: En Colegiales no se usa, se registra como Estudios
# Si necesitas recuperar: git log o liquidacion_backup_completo_2026-02-16.json

class LiquidacionViewsTest(TestCase):
    """Pruebas para las vistas de liquidación"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='drtest',
            password='testpass123',
            is_staff=True
        )
        self.estudio = Estudios.objects.create(
            nombre='Ecografía abdominal',
            tipo='ECO',
            conteo_regiones=1
        )
        self.client.login(username='drtest', password='testpass123')

    def test_acceso_sin_autenticacion(self):
        """Verifica que las vistas requieren autenticación"""
        self.client.logout()
        response = self.client.get(reverse('liquidacion:informados_por_medico_por_mes'))
        self.assertEqual(response.status_code, 302)  # Redirige al login

    def test_vista_informados_por_medico_por_mes(self):
        """Verifica que la vista de informes por médico funciona"""
        response = self.client.get(reverse('liquidacion:informados_por_medico_por_mes'))
        self.assertEqual(response.status_code, 200)

    def test_crear_registro_estudio(self):
        """Verifica que se puede crear un registro de estudio"""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.user,
            nombre_paciente='Test',
            apellido_paciente='Patient',
            dni_paciente='12345678',
            fecha_del_informe=date.today()
        )
        registro.estudio.add(self.estudio)
        
        self.assertEqual(RegistroEstudiosPorMedico.objects.count(), 1)
        self.assertEqual(registro.total_regiones(), 1)
