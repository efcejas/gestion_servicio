from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date
from decimal import Decimal

from .models import (
    DiaSinPacientes,
    Estudios,
    GrupoTarifario,
    RegistroEstudiosPorMedico,
    TarifaGrupoTarifario,
)
from .grupo_tarifario_mapping import inferir_codigo_grupo

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
            fecha_del_informe=date.today()
        )
        registro.estudio.add(self.estudio1)
        
        self.assertEqual(registro.medico, self.user)
        self.assertEqual(registro.nombre_paciente, 'Juan')
        self.assertIn(self.estudio1, registro.estudio.all())

    def test_registro_str(self):
        """Verifica la representación en string del registro"""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.user,
            nombre_paciente='Juan',
            apellido_paciente='Pérez',
            dni_paciente='12345678',
            fecha_del_informe=date.today()
        )
        registro.estudio.add(self.estudio1)
        str_registro = str(registro)
        self.assertIn(self.user.username, str_registro)

    def test_cantidad_regiones_campo(self):
        """Verifica que se puede establecer cantidad_regiones"""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.user,
            nombre_paciente='Juan',
            apellido_paciente='Pérez',
            dni_paciente='12345678',
            fecha_del_informe=date.today(),
            cantidad_regiones=2
        )
        registro.estudio.add(self.estudio1)
        
        # Verificar que cantidad_regiones se almacenó correctamente
        self.assertEqual(registro.cantidad_regiones, 2)

    def test_multiples_estudios_por_registro(self):
        """Verifica que cada registro puede tener múltiples estudios (M2M)"""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.user,
            nombre_paciente='María',
            apellido_paciente='González',
            dni_paciente='87654321',
            fecha_del_informe=date.today(),
            cantidad_regiones=3
        )
        # Agregar múltiples estudios
        registro.estudio.add(self.estudio1, self.estudio2)
        
        # Verificar que estudio es M2M y contiene ambos estudios
        self.assertEqual(registro.estudio.count(), 2)
        self.assertIn(self.estudio1, registro.estudio.all())
        self.assertIn(self.estudio2, registro.estudio.all())

    def test_fecha_registro_automatica(self):
        """Verifica que la fecha de registro se asigna automáticamente"""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.user,
            nombre_paciente='Pedro',
            apellido_paciente='López',
            dni_paciente='11111111',
            fecha_del_informe=date.today()
        )
        registro.estudio.add(self.estudio1)
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
            is_staff=True,
            rol='administrativo',
            perfil_completo=True
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
        response = self.client.get(reverse('liquidacion:liquidacion_mensual'))
        self.assertEqual(response.status_code, 302)  # Redirige al login

    def test_vista_informados_por_medico_por_mes(self):
        """Verifica que la vista de informes por médico funciona"""
        response = self.client.get(reverse('liquidacion:liquidacion_mensual'))
        self.assertEqual(response.status_code, 200)

    def test_crear_registro_estudio(self):
        """Verifica que se puede crear un registro de estudio"""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.user,
            nombre_paciente='Test',
            apellido_paciente='Patient',
            dni_paciente='12345678',
            fecha_del_informe=date.today(),
            cantidad_regiones=1
        )
        registro.estudio.add(self.estudio)
        
        self.assertEqual(RegistroEstudiosPorMedico.objects.count(), 1)
        self.assertEqual(registro.cantidad_regiones, 1)


class CalculoMontosTest(TestCase):
    """
    NUEVOS TESTS - Sistema de Liquidación v2.0
    Verificación de cálculo de montos con descuentos según horario
    """
    
    def setUp(self):
        """Configuración inicial para las pruebas de montos"""
        self.grupo_doppler = GrupoTarifario.objects.create(
            codigo='ECO_DOPPLER',
            nombre='Ecografía Doppler',
            modalidad='ECO',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.grupo_doppler,
            vigencia_desde=date.today(),
            precio_cober=Decimal('8500.00'),
            precio_otras_os=Decimal('10000.00'),
            motivo_actualizacion='Tarifa base de pruebas',
        )
        
        # Crear estudio con precios diferenciados
        self.estudio_doppler = Estudios.objects.create(
            codigo='902225',
            nombre='Doppler Periférico en Servicio',
            tipo='DOP',
            conteo_regiones=1,
            precio_unico=False,
            precio_cober=Decimal('9200.00'),
            precio_otras_os=Decimal('11200.00'),
            conteo_regiones_default=1,
            activo=True
        )
        self.estudio_doppler.grupo_tarifario = self.grupo_doppler
        self.estudio_doppler.save(update_fields=['grupo_tarifario'])
        
        # Crear segundo estudio para tests de múltiples estudios
        self.estudio_doppler2 = Estudios.objects.create(
            codigo='902226',
            nombre='Doppler Arterial MMII',
            tipo='DOP',
            conteo_regiones=1,
            precio_unico=False,
            precio_cober=Decimal('9300.00'),
            precio_otras_os=Decimal('11300.00'),
            conteo_regiones_default=1,
            activo=True
        )
        self.estudio_doppler2.grupo_tarifario = self.grupo_doppler
        self.estudio_doppler2.save(update_fields=['grupo_tarifario'])

        self.estudio_legado_sin_grupo = Estudios.objects.create(
            codigo='902227',
            nombre='Doppler Legado Sin Grupo',
            tipo='DOP',
            conteo_regiones=1,
            precio_unico=False,
            precio_cober=Decimal('12345.00'),
            precio_otras_os=Decimal('23456.00'),
            conteo_regiones_default=1,
            activo=True
        )
        
        # Crear usuarios con diferentes roles
        # 1. Residente
        self.residente = User.objects.create_user(
            username='residente1',
            password='testpass123',
            first_name='Ana',
            last_name='Residente',
            rol='medico_residente'
        )
        
        # 2. Jefe de Residentes
        self.jefe_residentes = User.objects.create_user(
            username='jefe_res',
            password='testpass123',
            first_name='Carlos',
            last_name='Jefe',
            rol='jefe_residentes'
        )
        
        # 3. Instructor
        self.instructor = User.objects.create_user(
            username='instructor1',
            password='testpass123',
            first_name='María',
            last_name='Instructor',
            rol='instructor_residentes'
        )
        
        # 4. Staff (siempre cobra 100%)
        self.staff = User.objects.create_user(
            username='staff1',
            password='testpass123',
            first_name='Luis',
            last_name='Staff',
            rol='medico_staff'
        )
    
    def test_residente_horario_intra_descuento_50_porciento_COBER(self):
        """
        CRÍTICO: Residente en horario INTRA residencia debe cobrar 50% del valor
        Fórmula: precio_cober × regiones × 0.5 (INTRA)
        """
        from decimal import Decimal
        
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='Juan',
            apellido_paciente='Pérez',
            dni_paciente='12345678',
            fecha_del_informe=date.today(),
            cantidad_regiones=1,
            tipo_obra_social='COBER',
            horario='INTRA'
        )
        registro.estudio.add(self.estudio_doppler)
        
        # Recalcular monto
        monto_calculado = registro.calcular_monto()
        
        # Esperado: $8.500 (COBER) × 1 región × 0.5 (INTRA) = $4.250
        esperado = Decimal('4250.00')
        
        self.assertEqual(
            monto_calculado, 
            esperado,
            f"❌ FALLA: Residente INTRA debería cobrar $4.250 (50% de la tarifa del grupo), pero cobra ${monto_calculado}"
        )

    def test_precio_para_os_prefiere_tarifa_vigente_del_grupo(self):
        """Verifica que el estudio prioriza la tarifa del grupo sobre el precio legado."""
        self.assertEqual(self.estudio_doppler.precio_para_os('COBER', fecha=date.today()), Decimal('8500.00'))
        self.assertEqual(self.estudio_doppler.precio_para_os('OTRAS_OS', fecha=date.today()), Decimal('10000.00'))

    def test_precio_para_os_sin_grupo_usa_fallback_legado(self):
        """Verifica que un estudio sin grupo conserva el comportamiento histórico."""
        self.assertEqual(self.estudio_legado_sin_grupo.precio_para_os('COBER'), Decimal('12345.00'))
        self.assertEqual(self.estudio_legado_sin_grupo.precio_para_os('OTRAS_OS'), Decimal('23456.00'))
    
    def test_residente_horario_extra_cobra_100_porciento_COBER(self):
        """
        Residente en horario EXTRA residencia debe cobrar 100% del valor
        Fórmula: precio_cober × regiones × 1.0 (EXTRA)
        """
        from decimal import Decimal
        
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='María',
            apellido_paciente='González',
            dni_paciente='87654321',
            fecha_del_informe=date.today(),
            cantidad_regiones=1,
            tipo_obra_social='COBER',
            horario='EXTRA'
        )
        registro.estudio.add(self.estudio_doppler)
        
        monto_calculado = registro.calcular_monto()
        
        # Esperado: $8.500 (COBER) × 1 región × 1.0 (EXTRA) = $8.500
        esperado = Decimal('8500.00')
        
        self.assertEqual(
            monto_calculado,
            esperado,
            f"❌ FALLA: Residente EXTRA debería cobrar $8.500 (100%), pero cobra ${monto_calculado}"
        )
    
    def test_residente_horario_intra_descuento_50_porciento_OTRAS_OS(self):
        """
        Residente INTRA con OTRAS OS: 50% del precio otras_os
        """
        from decimal import Decimal
        
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='Pedro',
            apellido_paciente='López',
            dni_paciente='11111111',
            fecha_del_informe=date.today(),
            cantidad_regiones=1,
            tipo_obra_social='OTRAS_OS',
            horario='INTRA'
        )
        registro.estudio.add(self.estudio_doppler)
        
        monto_calculado = registro.calcular_monto()
        
        # Esperado: $10.000 (OTRAS_OS) × 1 región × 0.5 (INTRA) = $5.000
        esperado = Decimal('5000.00')
        
        self.assertEqual(
            monto_calculado,
            esperado,
            f"❌ FALLA: Residente INTRA con OTRAS OS debería cobrar $5.000 (50% de $10.000), pero cobra ${monto_calculado}"
        )
    
    def test_jefe_residentes_horario_intra_descuento_50_porciento(self):
        """
        Jefe de Residentes en INTRA también tiene descuento del 50%
        """
        from decimal import Decimal
        
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.jefe_residentes,
            nombre_paciente='Laura',
            apellido_paciente='Martínez',
            dni_paciente='22222222',
            fecha_del_informe=date.today(),
            cantidad_regiones=1,
            tipo_obra_social='COBER',
            horario='INTRA'
        )
        registro.estudio.add(self.estudio_doppler)
        
        monto_calculado = registro.calcular_monto()
        esperado = Decimal('4250.00')  # 50% de $8.500
        
        self.assertEqual(
            monto_calculado,
            esperado,
            f"❌ FALLA: Jefe Residentes INTRA debe cobrar $4.250, pero cobra ${monto_calculado}"
        )
    
    def test_instructor_horario_intra_descuento_50_porciento(self):
        """
        Instructor en INTRA también tiene descuento del 50%
        """
        from decimal import Decimal
        
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.instructor,
            nombre_paciente='Diego',
            apellido_paciente='Fernández',
            dni_paciente='33333333',
            fecha_del_informe=date.today(),
            cantidad_regiones=1,
            tipo_obra_social='COBER',
            horario='INTRA'
        )
        registro.estudio.add(self.estudio_doppler)
        
        monto_calculado = registro.calcular_monto()
        esperado = Decimal('4250.00')  # 50% de $8.500
        
        self.assertEqual(
            monto_calculado,
            esperado,
            f"❌ FALLA: Instructor INTRA debe cobrar $4.250, pero cobra ${monto_calculado}"
        )
    
    def test_staff_siempre_cobra_100_porciento_sin_descuento(self):
        """
        CRÍTICO: Staff SIEMPRE cobra 100%, no importa el horario
        No aplica descuento INTRA/EXTRA
        """
        from decimal import Decimal
        
        # Staff en "horario INTRA" (que en realidad es N/A para ellos)
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.staff,
            nombre_paciente='Carmen',
            apellido_paciente='Ruiz',
            dni_paciente='44444444',
            fecha_del_informe=date.today(),
            cantidad_regiones=1,
            tipo_obra_social='COBER',
            horario='NA'  # Staff no tiene horario INTRA/EXTRA
        )
        registro.estudio.add(self.estudio_doppler)
        
        monto_calculado = registro.calcular_monto()
        
        # Esperado: $8.500 (COBER) × 1 región × 1.0 (Staff siempre 100%) = $8.500
        esperado = Decimal('8500.00')
        
        self.assertEqual(
            monto_calculado,
            esperado,
            f"❌ FALLA: Staff debe cobrar $8.500 (100% siempre), pero cobra ${monto_calculado}"
        )
    
    def test_residente_multiples_regiones_intra(self):
        """
        Verificar que el cálculo funciona con múltiples estudios (regiones)
        Fórmula v3.1 M2M: Σ(precio estudios) × porcentaje_horario
        """
        from decimal import Decimal
        
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='Roberto',
            apellido_paciente='Sánchez',
            dni_paciente='55555555',
            fecha_del_informe=date.today(),
            tipo_obra_social='COBER',
            horario='INTRA'
        )
        # Agregar 2 estudios diferentes
        registro.estudio.add(self.estudio_doppler, self.estudio_doppler2)
        
        monto_calculado = registro.calcular_monto()
        
        # Esperado: ($8.500 + $8.500) × 0.5 (INTRA) = $8.500
        esperado = Decimal('8500.00')
        
        self.assertEqual(
            monto_calculado,
            esperado,
            f"❌ FALLA: Residente con 2 estudios INTRA debe cobrar $8.500 según la tarifa del grupo, pero cobra ${monto_calculado}"
        )

    def test_calcular_monto_sin_grupo_usa_precios_legados(self):
        """Verifica que el cálculo sigue funcionando si el estudio todavía no tiene grupo asignado."""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.staff,
            nombre_paciente='Legado',
            apellido_paciente='Fallback',
            dni_paciente='88888888',
            fecha_del_informe=date.today(),
            cantidad_regiones=1,
            tipo_obra_social='OTRAS_OS',
            horario='EXTRA'
        )
        registro.estudio.add(self.estudio_legado_sin_grupo)

        monto_calculado = registro.calcular_monto()

        self.assertEqual(monto_calculado, Decimal('23456.00'))


class GrupoTarifarioMappingTest(TestCase):
    def test_inferir_codigo_grupo_tom_con_contraste(self):
        self.assertEqual(
            inferir_codigo_grupo('TOM', 'TC de abdomen con contraste'),
            'TOM_CONTRASTE',
        )

    def test_inferir_codigo_grupo_res_sin_contraste(self):
        self.assertEqual(
            inferir_codigo_grupo('RES', 'RM de rodilla sin contraste'),
            'RES_SIN_CONTRASTE',
        )

    def test_inferir_codigo_grupo_dop_periferico(self):
        self.assertEqual(
            inferir_codigo_grupo('DOP', 'Doppler periférico en lecho'),
            'DOP_PERIFERICO',
        )

    def test_inferir_codigo_grupo_dop_cardiaco(self):
        self.assertEqual(
            inferir_codigo_grupo('DOP', 'Doppler cardíaco transtorácico'),
            'DOP_CARDIACO',
        )

    def test_inferir_codigo_grupo_ecocar_te(self):
        self.assertEqual(
            inferir_codigo_grupo('ECOCAR', 'Ecocardiograma transesofágico (ETE)'),
            'ECO_TE',
        )

    def test_inferir_codigo_grupo_ecocar_stress(self):
        self.assertEqual(
            inferir_codigo_grupo('ECOCAR', 'Eco stress con dobutamina'),
            'ECO_STRESS',
        )

    def test_inferir_codigo_grupo_ecocar_burbuja(self):
        self.assertEqual(
            inferir_codigo_grupo('ECOCAR', 'Ecocardiograma con burbuja de contraste'),
            'ECO_BURBUJA',
        )

    def test_inferir_codigo_grupo_ambiguo_devuelve_none(self):
        self.assertIsNone(
            inferir_codigo_grupo('OTRO', 'Estudio sin modalidad clara'),
        )

class CalculoMontosRegressionTest(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff_regression',
            password='testpass123',
            first_name='Luis',
            last_name='Staff',
            rol='medico_staff',
        )
        self.residente = User.objects.create_user(
            username='residente_regression',
            password='testpass123',
            first_name='Ana',
            last_name='Residente',
            rol='medico_residente',
        )
        self.estudio_doppler = Estudios.objects.create(
            codigo='902228',
            nombre='Doppler Regression',
            tipo='DOP',
            conteo_regiones=1,
            precio_unico=False,
            precio_cober=Decimal('8500.00'),
            precio_otras_os=Decimal('10000.00'),
            conteo_regiones_default=1,
            activo=True,
        )

    def test_desglose_monto_incluye_porcentaje_horario(self):
        """Verificar que get_desglose_monto() muestra correctamente el porcentaje."""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='Test',
            apellido_paciente='Desglose',
            dni_paciente='66666666',
            fecha_del_informe=date.today(),
            cantidad_regiones=1,
            tipo_obra_social='COBER',
            horario='INTRA',
        )
        registro.estudio.add(self.estudio_doppler)

        desglose = registro.get_desglose_monto()

        self.assertEqual(desglose['porcentaje'], '50%')
        self.assertEqual(desglose['horario'], 'Intra Residencia (50%)')

    def test_horario_asignacion_automatica_staff(self):
        """Verificar que el horario se asigna como 'NA' para staff automáticamente."""
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.staff,
            nombre_paciente='Auto',
            apellido_paciente='Horario',
            dni_paciente='77777777',
            fecha_del_informe=date.today(),
            cantidad_regiones=1,
            tipo_obra_social='COBER',
        )
        registro.estudio.add(self.estudio_doppler)

        self.assertEqual(
            registro.horario,
            'NA',
            "❌ FALLA: Staff debe tener horario 'NA' automáticamente",
        )


class ContextoUbicacionTest(TestCase):
    """Tests de resolución contextual de precios (Doppler/ECOCAR en lecho/quirófano)."""

    def setUp(self):
        from decimal import Decimal
        # Grupo base SERVICIO
        self.grupo_base = GrupoTarifario.objects.create(
            codigo='DOP_PERIFERICO',
            nombre='Doppler Periférico (Servicio)',
            modalidad='DOP',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.grupo_base,
            vigencia_desde=date.today(),
            precio_cober=Decimal('9400.00'),
            precio_otras_os=Decimal('11000.00'),
            motivo_actualizacion='Tarifa contexto test',
        )
        # Grupo variante LECHO
        self.grupo_lecho = GrupoTarifario.objects.create(
            codigo='DOP_PERIFERICO_LECHO',
            nombre='Doppler Periférico (Lecho)',
            modalidad='DOP',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.grupo_lecho,
            vigencia_desde=date.today(),
            precio_cober=Decimal('11600.00'),
            precio_otras_os=Decimal('13200.00'),
            motivo_actualizacion='Tarifa lecho test',
        )
        # Estudio con tiene_contexto_ubicacion=True
        self.estudio = Estudios.objects.create(
            codigo='DOP-TEST',
            nombre='Doppler Periférico Test',
            tipo='DOP',
            conteo_regiones=1,
            precio_unico=False,
            precio_cober=Decimal('9400.00'),
            precio_otras_os=Decimal('11000.00'),
            conteo_regiones_default=1,
            activo=True,
            tiene_contexto_ubicacion=True,
        )
        self.estudio.grupo_tarifario = self.grupo_base
        self.estudio.save(update_fields=['grupo_tarifario'])

    def test_precio_para_os_contexto_servicio_usa_grupo_base(self):
        from decimal import Decimal
        self.assertEqual(
            self.estudio.precio_para_os('COBER', fecha=date.today(), contexto='SERVICIO'),
            Decimal('9400.00'),
        )

    def test_precio_para_os_contexto_lecho_usa_grupo_lecho(self):
        from decimal import Decimal
        self.assertEqual(
            self.estudio.precio_para_os('COBER', fecha=date.today(), contexto='LECHO'),
            Decimal('11600.00'),
        )

    def test_precio_para_os_contexto_lecho_otras_os(self):
        from decimal import Decimal
        self.assertEqual(
            self.estudio.precio_para_os('OTRAS_OS', fecha=date.today(), contexto='LECHO'),
            Decimal('13200.00'),
        )

    def test_precio_para_os_contexto_lecho_fallback_si_no_existe_grupo(self):
        """Si no existe DOP_PERIFERICO_LECHO, cae al grupo base."""
        from decimal import Decimal
        self.grupo_lecho.delete()
        # Debe caer al precio del grupo base
        self.assertEqual(
            self.estudio.precio_para_os('COBER', fecha=date.today(), contexto='LECHO'),
            Decimal('9400.00'),
        )

    def test_estudio_sin_tiene_contexto_ignora_contexto(self):
        """Un estudio sin tiene_contexto_ubicacion siempre usa el grupo base."""
        from decimal import Decimal
        self.estudio.tiene_contexto_ubicacion = False
        self.estudio.save(update_fields=['tiene_contexto_ubicacion'])
        self.assertEqual(
            self.estudio.precio_para_os('COBER', fecha=date.today(), contexto='LECHO'),
            Decimal('9400.00'),
        )

