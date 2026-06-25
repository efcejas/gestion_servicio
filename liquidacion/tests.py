from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, datetime
from decimal import Decimal

from control_guardias.models import Feriado

from .forms import PracticaForm
from .models import (
    DiaSinPacientes,
    Estudios,
    GrupoTarifario,
    GuardiaPasiva,
    ConfiguracionGuardiaPasiva,
    RegistroEstudiosPorMedico,
    RegistroEstudio,
    SesionContable,
    TarifaGrupoTarifario,
)
from .grupo_tarifario_mapping import inferir_codigo_grupo
from .services import clasificar_horario_residencia_por_proxy
from .services_auditoria import auditar_residentes_eco_por_sesion

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


class GuardiaPasivaConfiguracionTest(TestCase):
    """Pruebas para la configuración y registro de guardias pasivas."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='drguardias',
            password='testpass123',
            first_name='Guardia',
            last_name='Test'
        )

    def test_guardia_pasiva_toma_monto_vigente_desde_backend(self):
        ConfiguracionGuardiaPasiva.objects.create(
            monto_vigente=Decimal('41000.00'),
            vigente_desde=date.today(),
            motivo_actualizacion='Ajuste de prueba',
        )

        guardia = GuardiaPasiva.objects.create(
            medico=self.user,
            fecha_guardia=date.today(),
        )

        self.assertEqual(guardia.monto, Decimal('41000.00'))

    def test_configuracion_guardia_pasiva_genera_historial_al_cambiar_monto(self):
        config = ConfiguracionGuardiaPasiva.objects.create(
            monto_vigente=Decimal('36500.00'),
            vigente_desde=date.today(),
            motivo_actualizacion='Valor inicial',
        )

        config.monto_vigente = Decimal('42000.00')
        config.motivo_actualizacion = 'Aumento por actualización arancelaria'
        config.save()

        historial = config.historial_cambios.first()
        self.assertIsNotNone(historial)
        self.assertEqual(historial.monto_anterior, Decimal('36500.00'))
        self.assertEqual(historial.monto_nuevo, Decimal('42000.00'))


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
        Residente + DOP + INTRA: DOP no recibe descuento (100%).
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
        
        # Esperado: $8.500 (COBER) × 1 región = $8.500
        esperado = Decimal('8500.00')
        
        self.assertEqual(
            monto_calculado, 
            esperado,
            f"❌ FALLA: Residente + DOP + INTRA debe cobrar $8.500 (sin descuento), pero cobra ${monto_calculado}"
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
        Residente + DOP + INTRA con OTRAS OS: DOP no recibe descuento (100%).
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
        
        # Esperado: $10.000 (OTRAS_OS) × 1 región = $10.000
        esperado = Decimal('10000.00')
        
        self.assertEqual(
            monto_calculado,
            esperado,
            f"❌ FALLA: Residente + DOP + INTRA con OTRAS OS debe cobrar $10.000, pero cobra ${monto_calculado}"
        )
    
    def test_jefe_residentes_dop_intra_sin_descuento(self):
        """
        Jefe de Residentes + DOP + INTRA: NO aplica descuento (100%).
        Regla v3.2: solo ECO general recibe INTRA 50% para jefe/instructor.
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
        esperado = Decimal('8500.00')  # DOP sin descuento INTRA para jefe
        
        self.assertEqual(
            monto_calculado,
            esperado,
            f"FALLA: Jefe Residentes + DOP + INTRA debe cobrar $8.500 (sin descuento), pero cobra ${monto_calculado}"
        )
    
    def test_instructor_dop_intra_sin_descuento(self):
        """
        Instructor + DOP + INTRA: NO aplica descuento (100%).
        Regla v3.2: solo ECO general recibe INTRA 50% para jefe/instructor.
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
        esperado = Decimal('8500.00')  # DOP sin descuento INTRA para instructor
        
        self.assertEqual(
            monto_calculado,
            esperado,
            f"FALLA: Instructor + DOP + INTRA debe cobrar $8.500 (sin descuento), pero cobra ${monto_calculado}"
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
        Residente + DOP múltiple + INTRA: DOP no recibe descuento.
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
        
        # Esperado: ($8.500 + $8.500) = $17.000
        esperado = Decimal('17000.00')
        
        self.assertEqual(
            monto_calculado,
            esperado,
            f"❌ FALLA: Residente + 2 DOP + INTRA debe cobrar $17.000, pero cobra ${monto_calculado}"
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


class PermisosDesgloseTest(TestCase):
    """Tests para Fase 1: helpers de permisos y métodos de desglose por rol (v3.2 - Mayo 2026)"""

    def setUp(self):
        """Preparar usuarios con diferentes roles y registros de prueba."""
        from decimal import Decimal
        
        # Crear usuarios con distintos roles
        self.medico = User.objects.create_user(
            username='medico_test',
            email='medico@test.com',
            password='testpass123',
            rol='medico_staff'
        )
        self.residente = User.objects.create_user(
            username='residente_test',
            email='residente@test.com',
            password='testpass123',
            rol='medico_residente'
        )
        self.administrativo = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='testpass123',
            rol='administrativo'
        )
        self.jefe = User.objects.create_user(
            username='jefe_test',
            email='jefe@test.com',
            password='testpass123',
            rol='jefe_servicio'
        )
        self.superuser = User.objects.create_superuser(
            username='super_test',
            email='super@test.com',
            password='testpass123'
        )
        
        # Crear grupo tarifario con tarifa vigente
        self.grupo = GrupoTarifario.objects.create(
            codigo='RM_CONTRASTE_TEST',
            nombre='RM con Contraste - Test',
            modalidad='RM',
            activo=True
        )
        today = date.today()
        self.tarifa = TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.grupo,
            vigencia_desde=today,
            vigencia_hasta=date(2099, 12, 31),
            precio_cober=Decimal('5500.00'),
            precio_otras_os=Decimal('6200.00'),
            motivo_actualizacion='Test Fase 1'
        )
        
        # Crear estudio vinculado al grupo
        self.estudio = Estudios.objects.create(
            codigo='RM-ABDOMEN-TEST',
            nombre='RM Abdomen con Contraste',
            tipo='RM',
            conteo_regiones=1,
            precio_unico=False,
            precio_cober=Decimal('5500.00'),
            precio_otras_os=Decimal('6200.00'),
            conteo_regiones_default=1,
            activo=True,
            grupo_tarifario=self.grupo
        )
        
        # Crear registro de estudios para test
        self.registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            tipo_obra_social='COBER',
            horario='INTRA',
            cantidad_regiones=1,
            monto_calculado=Decimal('2750.00'),  # 5500 * 0.5 (INTRA)
            fecha_del_informe=today
        )
        
        # Vincular estudio al registro
        from liquidacion.models import RegistroEstudio
        RegistroEstudio.objects.create(
            registro=self.registro,
            estudio=self.estudio,
            cantidad=1,
            contexto='SERVICIO'
        )

    def test_puede_ver_desglose_administrativo_medico_retorna_false(self):
        """Helper: médico no puede ver desglose administrativo."""
        from liquidacion.permisos import puede_ver_desglose_administrativo
        
        self.assertFalse(
            puede_ver_desglose_administrativo(self.medico),
            "❌ FALLA: Médico no debe poder ver desglose administrativo"
        )

    def test_puede_ver_desglose_administrativo_residente_retorna_false(self):
        """Helper: residente no puede ver desglose administrativo."""
        from liquidacion.permisos import puede_ver_desglose_administrativo
        
        self.assertFalse(
            puede_ver_desglose_administrativo(self.residente),
            "❌ FALLA: Residente no debe poder ver desglose administrativo"
        )

    def test_puede_ver_desglose_administrativo_administrativo_retorna_true(self):
        """Helper: administrativo SÍ puede ver desglose administrativo."""
        from liquidacion.permisos import puede_ver_desglose_administrativo
        
        self.assertTrue(
            puede_ver_desglose_administrativo(self.administrativo),
            "❌ FALLA: Administrativo debe poder ver desglose administrativo"
        )

    def test_puede_ver_desglose_administrativo_jefe_retorna_true(self):
        """Helper: jefe_servicio SÍ puede ver desglose administrativo."""
        from liquidacion.permisos import puede_ver_desglose_administrativo
        
        self.assertTrue(
            puede_ver_desglose_administrativo(self.jefe),
            "❌ FALLA: Jefe servicio debe poder ver desglose administrativo"
        )

    def test_puede_ver_desglose_administrativo_superuser_retorna_true(self):
        """Helper: superuser SÍ puede ver desglose administrativo."""
        from liquidacion.permisos import puede_ver_desglose_administrativo
        
        self.assertTrue(
            puede_ver_desglose_administrativo(self.superuser),
            "❌ FALLA: Superuser debe poder ver desglose administrativo"
        )

    def test_get_desglose_monto_simple_no_incluye_grupo_tarifario(self):
        """get_desglose_monto_simple(): NO incluye grupo_tarifario_codigo."""
        desglose = self.registro.get_desglose_monto_simple()
        
        self.assertNotIn(
            'grupo_tarifario_codigo',
            desglose,
            "❌ FALLA: Desglose simple no debe incluir grupo_tarifario_codigo"
        )

    def test_get_desglose_monto_simple_no_incluye_tarifa_vigencia(self):
        """get_desglose_monto_simple(): NO incluye tarifa_vigencia_desde."""
        desglose = self.registro.get_desglose_monto_simple()
        
        self.assertNotIn(
            'tarifa_vigencia_desde',
            desglose,
            "❌ FALLA: Desglose simple no debe incluye tarifa_vigencia_desde"
        )

    def test_get_desglose_monto_simple_incluye_estudios_regiones_monto(self):
        """get_desglose_monto_simple(): SÍ incluye estudios, regiones, monto_final."""
        desglose = self.registro.get_desglose_monto_simple()
        
        self.assertIn('estudios', desglose)
        self.assertIn('regiones', desglose)
        self.assertIn('monto_final', desglose)
        self.assertEqual(desglose['regiones'], 1)
        self.assertEqual(desglose['monto_final'], Decimal('2750.00'))

    def test_get_desglose_monto_administrativo_incluye_grupo_tarifario(self):
        """get_desglose_monto_administrativo(): SÍ incluye grupo_tarifario_codigo."""
        desglose = self.registro.get_desglose_monto_administrativo()
        
        self.assertIn(
            'grupo_tarifario_codigo',
            desglose,
            "❌ FALLA: Desglose administrativo debe incluir grupo_tarifario_codigo"
        )
        self.assertEqual(desglose['grupo_tarifario_codigo'], 'RM_CONTRASTE_TEST')

    def test_get_desglose_monto_administrativo_incluye_tarifa_vigencia(self):
        """get_desglose_monto_administrativo(): SÍ incluye tarifa_vigencia_desde."""
        desglose = self.registro.get_desglose_monto_administrativo()
        
        self.assertIn(
            'tarifa_vigencia_desde',
            desglose,
            "❌ FALLA: Desglose administrativo debe incluir tarifa_vigencia_desde"
        )
        self.assertEqual(desglose['tarifa_vigencia_desde'], date.today())

    def test_get_desglose_monto_administrativo_incluye_precio_tarifa(self):
        """get_desglose_monto_administrativo(): SÍ incluye tarifa_precio_cober."""
        desglose = self.registro.get_desglose_monto_administrativo()
        
        self.assertIn(
            'tarifa_precio_cober',
            desglose,
            "❌ FALLA: Desglose administrativo debe incluir tarifa_precio_cober"
        )
        self.assertEqual(desglose['tarifa_precio_cober'], Decimal('5500.00'))

    def test_calcular_monto_sin_cambios(self):
        """Validar que calcular_monto() NO cambio: sigue retornando lo esperado."""
        # Recrear calculo esperado
        from decimal import Decimal
        precio_total = Decimal('5500.00') * 1  # 1 estudio
        # medico_staff cobra siempre 100% (el 50% INTRA solo aplica a residentes)
        esperado = precio_total  # sin descuento de horario
        
        resultado = self.registro.calcular_monto()
        
        self.assertEqual(
            resultado,
            esperado,
            f"FALLA: calcular_monto() cambio. Esperado {esperado}, obtuvo {resultado}"
        )


class FactorIntraRolTipoEstudioTest(TestCase):
    """
    Tests para regla INTRA diferenciada por rol y tipo de estudio (v3.2 - Mayo 2026).

    Regla:
            - medico_residente: INTRA (50%) aplica SOLO a ECO general real.
      - jefe_residentes / instructor_residentes: INTRA (50%) solo a ECO general.
        Doppler (DOP) y otros siempre al 100% para estos roles.
      - medico_staff: sin factor horario, siempre 100%.
    """

    def setUp(self):
        from liquidacion.models import RegistroEstudio
        
        self.jefe = User.objects.create_user(
            username='jefe_intra_test', email='jefe@test.com',
            password='x', rol='jefe_residentes'
        )
        self.instructor = User.objects.create_user(
            username='instructor_intra_test', email='instructor@test.com',
            password='x', rol='instructor_residentes'
        )
        self.residente = User.objects.create_user(
            username='residente_intra_test', email='residente@test.com',
            password='x', rol='medico_residente'
        )
        
        today = date.today()
        
        # Grupo y tarifa para ECO general
        grupo_eco = GrupoTarifario.objects.create(
            codigo='ECO_ABDOMEN_TEST', nombre='Eco Abdominal Test', modalidad='ECO', activo=True
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=grupo_eco, vigencia_desde=today,
            precio_cober=Decimal('4000.00'), precio_otras_os=Decimal('5000.00'),
            motivo_actualizacion='Test INTRA'
        )
        self.estudio_eco = Estudios.objects.create(
            codigo='ECO-TEST', nombre='Eco Abdominal Test', tipo='ECO',
            conteo_regiones=1, precio_unico=False,
            precio_cober=Decimal('4000.00'), precio_otras_os=Decimal('5000.00'),
            conteo_regiones_default=1, activo=True, grupo_tarifario=grupo_eco
        )
        
        # Grupo y tarifa para Doppler
        grupo_dop = GrupoTarifario.objects.create(
            codigo='DOP_TEST', nombre='Doppler Test', modalidad='DOP', activo=True
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=grupo_dop, vigencia_desde=today,
            precio_cober=Decimal('6000.00'), precio_otras_os=Decimal('7000.00'),
            motivo_actualizacion='Test INTRA DOP'
        )
        self.estudio_dop = Estudios.objects.create(
            codigo='DOP-TEST', nombre='Doppler Periferico Test', tipo='DOP',
            conteo_regiones=1, precio_unico=False,
            precio_cober=Decimal('6000.00'), precio_otras_os=Decimal('7000.00'),
            conteo_regiones_default=1, activo=True, grupo_tarifario=grupo_dop
        )
        
        self.RegistroEstudio = RegistroEstudio
        self.today = today

    def _crear_registro(self, medico, estudio, horario='INTRA'):
        """Helper: crea un RegistroEstudiosPorMedico con un estudio vinculado."""
        reg = RegistroEstudiosPorMedico.objects.create(
            medico=medico,
            tipo_obra_social='COBER',
            horario=horario,
            cantidad_regiones=1,
            monto_calculado=Decimal('0.00'),
            fecha_del_informe=self.today
        )
        self.RegistroEstudio.objects.create(registro=reg, estudio=estudio, cantidad=1, contexto='SERVICIO')
        return reg

    def test_jefe_eco_intra_aplica_50_porciento(self):
        """Jefe residente + ECO + INTRA: monto = 4000 * 0.5 = 2000."""
        reg = self._crear_registro(self.jefe, self.estudio_eco, horario='INTRA')
        self.assertEqual(reg.calcular_monto(), Decimal('2000.00'))

    def test_jefe_dop_intra_no_aplica_factor(self):
        """Jefe residente + DOP + INTRA: monto = 6000 (sin descuento)."""
        reg = self._crear_registro(self.jefe, self.estudio_dop, horario='INTRA')
        self.assertEqual(reg.calcular_monto(), Decimal('6000.00'))

    def test_instructor_eco_intra_aplica_50_porciento(self):
        """Instructor residente + ECO + INTRA: monto = 4000 * 0.5 = 2000."""
        reg = self._crear_registro(self.instructor, self.estudio_eco, horario='INTRA')
        self.assertEqual(reg.calcular_monto(), Decimal('2000.00'))

    def test_instructor_dop_intra_no_aplica_factor(self):
        """Instructor residente + DOP + INTRA: monto = 6000 (sin descuento)."""
        reg = self._crear_registro(self.instructor, self.estudio_dop, horario='INTRA')
        self.assertEqual(reg.calcular_monto(), Decimal('6000.00'))

    def test_residente_eco_intra_aplica_50_porciento(self):
        """Residente + ECO + INTRA: monto = 4000 * 0.5 = 2000 (sin cambio)."""
        reg = self._crear_registro(self.residente, self.estudio_eco, horario='INTRA')
        self.assertEqual(reg.calcular_monto(), Decimal('2000.00'))

    def test_residente_dop_intra_no_aplica_factor(self):
        """Residente + DOP + INTRA: monto = 6000 (sin descuento)."""
        reg = self._crear_registro(self.residente, self.estudio_dop, horario='INTRA')
        self.assertEqual(reg.calcular_monto(), Decimal('6000.00'))

    def test_jefe_eco_extra_sin_descuento(self):
        """Jefe residente + ECO + EXTRA: monto = 4000 (EXTRA nunca descuenta)."""
        reg = self._crear_registro(self.jefe, self.estudio_eco, horario='EXTRA')
        self.assertEqual(reg.calcular_monto(), Decimal('4000.00'))

    def test_jefe_mix_eco_dop_intra_aplica_solo_a_eco(self):
        """
        Jefe + registro mixto (ECO 4000 + DOP 6000) + INTRA:
        monto = (4000 * 0.5) + 6000 = 2000 + 6000 = 8000.
        """
        reg = RegistroEstudiosPorMedico.objects.create(
            medico=self.jefe,
            tipo_obra_social='COBER',
            horario='INTRA',
            cantidad_regiones=2,
            monto_calculado=Decimal('0.00'),
            fecha_del_informe=self.today
        )
        self.RegistroEstudio.objects.create(registro=reg, estudio=self.estudio_eco, cantidad=1, contexto='SERVICIO')
        self.RegistroEstudio.objects.create(registro=reg, estudio=self.estudio_dop, cantidad=1, contexto='SERVICIO')
        self.assertEqual(reg.calcular_monto(), Decimal('8000.00'))

    def test_residente_mix_eco_dop_intra_aplica_solo_a_eco(self):
        """Residente + (ECO 4000 + DOP 6000) + INTRA => 2000 + 6000 = 8000."""
        reg = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            tipo_obra_social='COBER',
            horario='INTRA',
            cantidad_regiones=2,
            monto_calculado=Decimal('0.00'),
            fecha_del_informe=self.today,
        )
        self.RegistroEstudio.objects.create(registro=reg, estudio=self.estudio_eco, cantidad=1, contexto='SERVICIO')
        self.RegistroEstudio.objects.create(registro=reg, estudio=self.estudio_dop, cantidad=1, contexto='SERVICIO')
        self.assertEqual(reg.calcular_monto(), Decimal('8000.00'))


class ClasificacionHorarioResidenciaProxyTest(TestCase):
    def setUp(self):
        from liquidacion.models import RegistroEstudio

        self.client = Client()
        self.residente = User.objects.create_user(
            username='residente_proxy',
            password='testpass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.jefe_residentes = User.objects.create_user(
            username='jefe_proxy',
            password='testpass123',
            rol='jefe_residentes',
            perfil_completo=True,
        )
        self.instructor_residentes = User.objects.create_user(
            username='instructor_proxy',
            password='testpass123',
            rol='instructor_residentes',
            perfil_completo=True,
        )
        self.staff = User.objects.create_user(
            username='staff_proxy',
            password='testpass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.estudio_eco = Estudios.objects.create(
            nombre='Eco Proxy',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        self.estudio_no_eco = Estudios.objects.create(
            nombre='Doppler Proxy',
            tipo='DOP',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        self.estudio_doppler_mal_tipado_eco = Estudios.objects.create(
            nombre='ECODOPPLER Mal Tipado',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        self.estudio_ecocar = Estudios.objects.create(
            nombre='Ecocardiograma Test',
            tipo='ECOCAR',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        self.RegistroEstudio = RegistroEstudio

    def _aware(self, year, month, day, hour, minute=0):
        return timezone.make_aware(datetime(year, month, day, hour, minute))

    def test_habil_1030_intra(self):
        resultado = clasificar_horario_residencia_por_proxy(
            rol='medico_residente',
            fecha_registro=self._aware(2026, 5, 27, 10, 30),  # miércoles
            tiene_eco_general=True,
        )
        self.assertEqual(resultado, 'INTRA')

    def test_habil_1700_extra(self):
        resultado = clasificar_horario_residencia_por_proxy(
            rol='medico_residente',
            fecha_registro=self._aware(2026, 5, 27, 17, 0),
            tiene_eco_general=True,
        )
        self.assertEqual(resultado, 'EXTRA')

    def test_sabado_extra(self):
        resultado = clasificar_horario_residencia_por_proxy(
            rol='medico_residente',
            fecha_registro=self._aware(2026, 5, 30, 10, 0),  # sábado
            tiene_eco_general=True,
        )
        self.assertEqual(resultado, 'EXTRA')

    def test_domingo_extra(self):
        resultado = clasificar_horario_residencia_por_proxy(
            rol='medico_residente',
            fecha_registro=self._aware(2026, 5, 31, 10, 0),  # domingo
            tiene_eco_general=True,
        )
        self.assertEqual(resultado, 'EXTRA')

    def test_feriado_extra(self):
        fecha = self._aware(2026, 5, 29, 10, 0)
        Feriado.objects.create(fecha=fecha.date(), descripcion='Feriado test')

        resultado = clasificar_horario_residencia_por_proxy(
            rol='medico_residente',
            fecha_registro=fecha,
            tiene_eco_general=True,
        )
        self.assertEqual(resultado, 'EXTRA')

    def test_no_aplica_si_no_hay_eco(self):
        resultado = clasificar_horario_residencia_por_proxy(
            rol='medico_residente',
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            tiene_eco_general=False,
        )
        self.assertIsNone(resultado)

    def test_no_aplica_a_staff(self):
        resultado = clasificar_horario_residencia_por_proxy(
            rol='medico_staff',
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            tiene_eco_general=True,
        )
        self.assertIsNone(resultado)

    def test_no_pisa_horario_ya_definido_en_fallback_save(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='No',
            apellido_paciente='Pisa',
            dni_paciente='90000001',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            horario='EXTRA',
            tipo_obra_social='COBER',
        )
        registro.save()
        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'EXTRA')

    def test_integracion_create_post_m2m_aplica_clasificacion(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='Ana',
            apellido_paciente='CreateFlow',
            dni_paciente='90000002',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 17, 10),
            tipo_obra_social='COBER',
            horario='NA',
        )

        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_eco,
            cantidad=1,
            contexto='SERVICIO',
        )
        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'EXTRA')

    def test_integracion_create_post_m2m_dop_only_queda_na(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='Ana',
            apellido_paciente='CreateDop',
            dni_paciente='90000012',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 30),
            tipo_obra_social='COBER',
            horario='INTRA',
        )

        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_no_eco,
            cantidad=1,
            contexto='SERVICIO',
        )
        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'NA')

    def test_integracion_update_post_m2m_aplica_clasificacion(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='Ana',
            apellido_paciente='UpdateFlow',
            dni_paciente='90000003',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 30),
            tipo_obra_social='COBER',
            horario='NA',
        )

        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_no_eco,
            cantidad=1,
            contexto='SERVICIO',
        )

        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'NA')

        # Simula edición: cambia M2M a ECO y dispara reclasificación post-M2M.
        registro.registroestudio_set.all().delete()
        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_eco,
            cantidad=1,
            contexto='SERVICIO',
        )
        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'INTRA')

    def test_signal_clasifica_cuando_se_crea_registroestudio(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='Signal',
            apellido_paciente='Eco',
            dni_paciente='90000004',
            fecha_del_informe=date(2026, 5, 30),
            fecha_registro=self._aware(2026, 5, 30, 10, 0),  # sábado
            tipo_obra_social='COBER',
            horario='NA',
        )

        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_eco,
            cantidad=1,
            contexto='SERVICIO',
        )
        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'EXTRA')

    def test_estudio_doppler_mal_tipado_como_eco_no_activa_intra(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='Signal',
            apellido_paciente='DopplerNombre',
            dni_paciente='90000013',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            tipo_obra_social='COBER',
            horario='INTRA',
        )

        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_doppler_mal_tipado_eco,
            cantidad=1,
            contexto='SERVICIO',
        )
        registro.refresh_from_db()
        self.assertEqual(registro.horario, 'NA')

    def test_estudio_ecocar_only_no_descuenta_intra_y_queda_na(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='Signal',
            apellido_paciente='EcocarOnly',
            dni_paciente='90000014',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            tipo_obra_social='COBER',
            horario='INTRA',
        )

        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_ecocar,
            cantidad=1,
            contexto='SERVICIO',
        )
        registro.refresh_from_db()

        self.assertNotEqual(registro.horario, 'INTRA')
        self.assertEqual(registro.horario, 'NA')
        self.assertEqual(registro.calcular_monto(), Decimal('1000.00'))

    def test_form_muestra_extra_residencia_solo_para_jefe_e_instructor(self):
        self.assertIn(
            'liquidar_como_extra_residencia',
            PracticaForm(user=self.jefe_residentes).fields,
        )
        self.assertIn(
            'liquidar_como_extra_residencia',
            PracticaForm(user=self.instructor_residentes).fields,
        )
        self.assertNotIn(
            'liquidar_como_extra_residencia',
            PracticaForm(user=self.residente).fields,
        )
        self.assertNotIn(
            'liquidar_como_extra_residencia',
            PracticaForm(user=self.staff).fields,
        )

    def test_post_manipulado_residente_no_puede_usar_extra_residencia(self):
        form = PracticaForm(
            data={
                'tipo_estudio': 'ECO',
                'fecha_del_informe': '2026-05-27',
                'nombre_paciente': 'Post',
                'apellido_paciente': 'Manipulado',
                'dni_paciente': '90000020',
                'estudio': [str(self.estudio_eco.id)],
                'cantidad_regiones': '1',
                'tipo_obra_social': 'COBER',
                'liquidar_como_extra_residencia': 'on',
            },
            user=self.residente,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn('liquidar_como_extra_residencia', form.cleaned_data)

    def test_signal_respeta_extra_residencia_jefe_eco_intra_y_monto_100(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.jefe_residentes,
            nombre_paciente='Jefe',
            apellido_paciente='Extra',
            dni_paciente='90000021',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            tipo_obra_social='COBER',
            horario='INTRA',
            liquidar_como_extra_residencia=True,
        )

        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_eco,
            cantidad=1,
            contexto='SERVICIO',
        )
        registro.refresh_from_db()

        self.assertEqual(registro.horario, 'EXTRA')
        self.assertEqual(registro.monto_calculado, Decimal('1000.00'))

    def test_signal_respeta_extra_residencia_instructor_eco_y_monto_100(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.instructor_residentes,
            nombre_paciente='Instructor',
            apellido_paciente='Extra',
            dni_paciente='90000022',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            tipo_obra_social='COBER',
            horario='INTRA',
            liquidar_como_extra_residencia=True,
        )

        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_eco,
            cantidad=1,
            contexto='SERVICIO',
        )
        registro.refresh_from_db()

        self.assertEqual(registro.horario, 'EXTRA')
        self.assertEqual(registro.monto_calculado, Decimal('1000.00'))

    def test_jefe_sin_flag_mantiene_clasificacion_actual(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.jefe_residentes,
            nombre_paciente='Jefe',
            apellido_paciente='Intra',
            dni_paciente='90000023',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            tipo_obra_social='COBER',
            horario='NA',
            liquidar_como_extra_residencia=False,
        )

        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_eco,
            cantidad=1,
            contexto='SERVICIO',
        )
        registro.refresh_from_db()

        self.assertEqual(registro.horario, 'INTRA')
        self.assertEqual(registro.monto_calculado, Decimal('500.00'))

    def test_doppler_jefe_con_flag_queda_extra(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.jefe_residentes,
            nombre_paciente='Jefe',
            apellido_paciente='Doppler',
            dni_paciente='90000024',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            tipo_obra_social='COBER',
            horario='INTRA',
            liquidar_como_extra_residencia=True,
        )

        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_no_eco,
            cantidad=1,
            contexto='SERVICIO',
        )
        registro.refresh_from_db()

        self.assertEqual(registro.horario, 'EXTRA')
        self.assertEqual(registro.monto_calculado, Decimal('1000.00'))

    def _post_update_registro_extra_residencia(self, registro, marcado):
        data = {
            'tipo_estudio': 'ECO',
            'fecha_del_informe': registro.fecha_del_informe.strftime('%Y-%m-%d'),
            'nombre_paciente': registro.nombre_paciente,
            'apellido_paciente': registro.apellido_paciente,
            'dni_paciente': registro.dni_paciente,
            'estudio': [str(self.estudio_eco.id)],
            'cantidad_regiones': '1',
            'tipo_obra_social': 'COBER',
            f'cantidad_estudio_{self.estudio_eco.id}': '1',
            f'contexto_estudio_{self.estudio_eco.id}': 'SERVICIO',
        }
        if marcado:
            data['liquidar_como_extra_residencia'] = 'on'

        self.client.force_login(self.jefe_residentes)
        return self.client.post(
            reverse('liquidacion:registroestudios_edit', args=[registro.pk]),
            data,
            secure=True,
        )

    def _post_create_registro_extra_residencia(self, user, marcado, dni):
        data = {
            'tipo_estudio': 'ECO',
            'fecha_del_informe': '2026-05-27',
            'nombre_paciente': 'Create',
            'apellido_paciente': 'Sesion',
            'dni_paciente': dni,
            'estudio': [str(self.estudio_eco.id)],
            'cantidad_regiones': '1',
            'tipo_obra_social': 'COBER',
            f'cantidad_estudio_{self.estudio_eco.id}': '1',
            f'contexto_estudio_{self.estudio_eco.id}': 'SERVICIO',
        }
        if marcado:
            data['liquidar_como_extra_residencia'] = 'on'

        self.client.force_login(user)
        return self.client.post(
            reverse('liquidacion:registroestudios_nuevo'),
            data,
            secure=True,
        )

    def _get_create_form(self, user):
        self.client.force_login(user)
        response = self.client.get(
            reverse('liquidacion:registroestudios_nuevo'),
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        return response.context['form']

    def test_create_jefe_recuerda_checkbox_tildado_en_sesion(self):
        response = self._post_create_registro_extra_residencia(
            self.jefe_residentes,
            marcado=True,
            dni='90000030',
        )
        self.assertEqual(response.status_code, 302)

        form = self._get_create_form(self.jefe_residentes)
        self.assertTrue(form.initial.get('liquidar_como_extra_residencia'))

    def test_create_jefe_recuerda_checkbox_destildado_en_sesion(self):
        session = self.client.session
        session['liquidacion_liquidar_como_extra_residencia_default'] = True
        session.save()

        response = self._post_create_registro_extra_residencia(
            self.jefe_residentes,
            marcado=False,
            dni='90000031',
        )
        self.assertEqual(response.status_code, 302)

        form = self._get_create_form(self.jefe_residentes)
        self.assertFalse(form.initial.get('liquidar_como_extra_residencia'))

    def test_create_instructor_recuerda_checkbox_en_sesion(self):
        response = self._post_create_registro_extra_residencia(
            self.instructor_residentes,
            marcado=True,
            dni='90000032',
        )
        self.assertEqual(response.status_code, 302)

        form = self._get_create_form(self.instructor_residentes)
        self.assertTrue(form.initial.get('liquidar_como_extra_residencia'))

    def test_create_instructor_recuerda_checkbox_destildado_en_sesion(self):
        session = self.client.session
        session['liquidacion_liquidar_como_extra_residencia_default'] = True
        session.save()

        response = self._post_create_registro_extra_residencia(
            self.instructor_residentes,
            marcado=False,
            dni='90000035',
        )
        self.assertEqual(response.status_code, 302)

        form = self._get_create_form(self.instructor_residentes)
        self.assertFalse(form.initial.get('liquidar_como_extra_residencia'))

    def test_create_residente_no_lee_ni_escribe_default_de_sesion(self):
        session = self.client.session
        session['liquidacion_liquidar_como_extra_residencia_default'] = False
        session.save()

        form = self._get_create_form(self.residente)
        self.assertNotIn('liquidar_como_extra_residencia', form.fields)

        response = self._post_create_registro_extra_residencia(
            self.residente,
            marcado=True,
            dni='90000033',
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            self.client.session['liquidacion_liquidar_como_extra_residencia_default']
        )

    def test_update_usa_valor_del_registro_no_default_de_sesion(self):
        session = self.client.session
        session['liquidacion_liquidar_como_extra_residencia_default'] = True
        session.save()

        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.jefe_residentes,
            nombre_paciente='Update',
            apellido_paciente='Sesion',
            dni_paciente='90000034',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            tipo_obra_social='COBER',
            horario='INTRA',
            monto_calculado=Decimal('500.00'),
            liquidar_como_extra_residencia=False,
        )
        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_eco,
            cantidad=1,
            contexto='SERVICIO',
        )

        self.client.force_login(self.jefe_residentes)
        response = self.client.get(
            reverse('liquidacion:registroestudios_edit', args=[registro.pk]),
            secure=True,
        )
        self.assertEqual(response.status_code, 200)
        form = response.context['form']

        self.assertFalse(form['liquidar_como_extra_residencia'].value())

    def test_update_activar_flag_cambia_a_extra(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.jefe_residentes,
            nombre_paciente='Update',
            apellido_paciente='Activa',
            dni_paciente='90000025',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            tipo_obra_social='COBER',
            horario='INTRA',
            monto_calculado=Decimal('500.00'),
            liquidar_como_extra_residencia=False,
        )
        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_eco,
            cantidad=1,
            contexto='SERVICIO',
        )

        response = self._post_update_registro_extra_residencia(registro, marcado=True)
        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()

        self.assertTrue(registro.liquidar_como_extra_residencia)
        self.assertEqual(registro.horario, 'EXTRA')
        self.assertEqual(registro.monto_calculado, Decimal('1000.00'))

    def test_update_desactivar_flag_vuelve_a_clasificacion_automatica(self):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.jefe_residentes,
            nombre_paciente='Update',
            apellido_paciente='Desactiva',
            dni_paciente='90000026',
            fecha_del_informe=date(2026, 5, 27),
            fecha_registro=self._aware(2026, 5, 27, 10, 0),
            tipo_obra_social='COBER',
            horario='EXTRA',
            monto_calculado=Decimal('1000.00'),
            liquidar_como_extra_residencia=True,
        )
        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_eco,
            cantidad=1,
            contexto='SERVICIO',
        )

        response = self._post_update_registro_extra_residencia(registro, marcado=False)
        self.assertEqual(response.status_code, 302)
        registro.refresh_from_db()

        self.assertFalse(registro.liquidar_como_extra_residencia)
        self.assertEqual(registro.horario, 'INTRA')
        self.assertEqual(registro.monto_calculado, Decimal('500.00'))

    def test_form_no_expone_horario(self):
        form = PracticaForm(user=self.residente)
        self.assertNotIn('horario', form.fields)


class AuditoriaResidentesEcoServiceTest(TestCase):
    def setUp(self):
        from liquidacion.models import RegistroEstudio

        self.residente = User.objects.create_user(
            username='res_audit',
            password='testpass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.jefe_residentes = User.objects.create_user(
            username='jefe_audit',
            password='testpass123',
            rol='jefe_residentes',
            perfil_completo=True,
        )
        self.instructor = User.objects.create_user(
            username='inst_audit',
            password='testpass123',
            rol='instructor_residentes',
            perfil_completo=True,
        )
        self.staff = User.objects.create_user(
            username='staff_audit',
            password='testpass123',
            rol='medico_staff',
            perfil_completo=True,
        )

        self.sesion = SesionContable.objects.create(mes=5, año=2026, estado='ABIERTA')
        self.sesion_otra = SesionContable.objects.create(mes=6, año=2026, estado='ABIERTA')

        self.estudio_eco = Estudios.objects.create(
            nombre='ECO Audit',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        self.estudio_dop = Estudios.objects.create(
            nombre='DOP Audit',
            tipo='DOP',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        self.RegistroEstudio = RegistroEstudio

    def _aware(self, y, m, d, h, minute=0):
        return timezone.make_aware(datetime(y, m, d, h, minute))

    def _crear_registro(self, medico, sesion, dt, horario='EXTRA', estudio=None, monto='1000.00'):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=medico,
            sesion_contable=sesion,
            nombre_paciente='Paciente',
            apellido_paciente='Audit',
            dni_paciente=f"{medico.id}{dt.day:02d}{dt.hour:02d}"[:8],
            fecha_del_informe=dt.date(),
            fecha_registro=dt,
            tipo_obra_social='COBER',
            horario=horario,
            monto_calculado=Decimal(monto),
        )
        self.RegistroEstudio.objects.create(
            registro=registro,
            estudio=estudio or self.estudio_eco,
            cantidad=1,
            contexto='SERVICIO',
        )
        return registro

    def test_servicio_filtra_por_sesion(self):
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 12, 10), horario='INTRA')
        self._crear_registro(self.residente, self.sesion_otra, self._aware(2026, 6, 12, 10), horario='EXTRA')

        data = auditar_residentes_eco_por_sesion(self.sesion)
        item = data['items'][0]
        self.assertEqual(data['sesion_id'], self.sesion.id)
        self.assertEqual(item['total_eco'], 1)

    def test_servicio_filtra_roles_permitidos(self):
        self._crear_registro(self.staff, self.sesion, self._aware(2026, 5, 12, 10), horario='EXTRA')
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 12, 10), horario='INTRA')

        data = auditar_residentes_eco_por_sesion(self.sesion)
        self.assertEqual(data['total_residentes'], 1)
        self.assertEqual(data['items'][0]['medico_id'], self.residente.id)

    def test_servicio_filtra_solo_eco(self):
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 12, 10), horario='EXTRA', estudio=self.estudio_dop)

        data = auditar_residentes_eco_por_sesion(self.sesion)
        self.assertEqual(data['total_residentes'], 0)
        self.assertEqual(data['items'], [])

    def test_calcula_intra_extra_proporcion(self):
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 12, 10), horario='INTRA')
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 12, 17), horario='EXTRA')
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 13, 17), horario='EXTRA')

        data = auditar_residentes_eco_por_sesion(self.sesion)
        item = data['items'][0]
        self.assertEqual(item['intra'], 1)
        self.assertEqual(item['extra'], 2)
        self.assertAlmostEqual(item['proporcion_extra'], 2 / 3, places=6)

    def test_detecta_nocturnos(self):
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 12, 23), horario='EXTRA')
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 13, 5), horario='EXTRA')

        data = auditar_residentes_eco_por_sesion(self.sesion)
        self.assertEqual(data['items'][0]['nocturnos'], 2)

    def test_detecta_finde_y_feriado(self):
        Feriado.objects.create(fecha=date(2026, 5, 13), descripcion='Feriado audit')
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 30, 10), horario='EXTRA')  # sábado
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 13, 10), horario='EXTRA')  # feriado

        data = auditar_residentes_eco_por_sesion(self.sesion)
        self.assertEqual(data['items'][0]['finde_feriado'], 2)

    def test_detecta_max_eco_dia_y_dias_pico(self):
        for i in range(14):
            self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 12, 10, i % 59), horario='INTRA')

        data = auditar_residentes_eco_por_sesion(self.sesion)
        item = data['items'][0]
        self.assertEqual(item['max_eco_dia'], 14)
        self.assertIn('2026-05-12', item['dias_pico'])

    def test_severidad_roja(self):
        for i in range(50):
            self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 12, 17, i % 59), horario='EXTRA')

        data = auditar_residentes_eco_por_sesion(self.sesion)
        item = data['items'][0]
        self.assertEqual(item['severidad'], 'roja')
        self.assertTrue(any(a['severidad'] == 'roja' for a in item['alertas']))

    def test_severidad_amarilla(self):
        for i in range(7):
            self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 12, 17, i % 59), horario='EXTRA')
        for i in range(13):
            self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 13, 10, i % 59), horario='INTRA')

        data = auditar_residentes_eco_por_sesion(self.sesion)
        self.assertEqual(data['items'][0]['severidad'], 'amarilla')

    def test_severidad_ok(self):
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 12, 10), horario='INTRA')
        self._crear_registro(self.residente, self.sesion, self._aware(2026, 5, 12, 11), horario='INTRA')

        data = auditar_residentes_eco_por_sesion(self.sesion)
        self.assertEqual(data['items'][0]['severidad'], 'ok')

    def test_no_modifica_monto_ni_horario(self):
        registro = self._crear_registro(
            self.residente,
            self.sesion,
            self._aware(2026, 5, 12, 17),
            horario='EXTRA',
            monto='4321.00',
        )
        registro.refresh_from_db()

        monto_antes = registro.monto_calculado
        horario_antes = registro.horario

        auditar_residentes_eco_por_sesion(self.sesion)
        registro.refresh_from_db()
        self.assertEqual(registro.horario, horario_antes)
        self.assertEqual(registro.monto_calculado, monto_antes)

