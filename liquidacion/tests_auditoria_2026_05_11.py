"""
NUEVOS TESTS - Auditoría de Liquidación v3.1 (11 mayo 2026)
Validar que los 4 fixes implementados funcionan:
  FIX #1: @transaction.atomic en form_valid
  FIX #2: Migración 0028 con error handling
  FIX #3: DB constraints
  FIX #4: Post_save signals para recálculo automático
"""

from django.test import TestCase, TransactionTestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from datetime import date, datetime
from decimal import Decimal
from .models import (
    RegistroEstudiosPorMedico,
    RegistroEstudio,
    Estudios,
    SesionContable,
    HistorialSesionContable,
    GuardiaPasiva,
    GrupoTarifario,
    TarifaGrupoTarifario,
)
from accounts.context_processors import navbar_links

User = get_user_model()


class TransactionAtomicTest(TransactionTestCase):
    """
    Test para validar que @transaction.atomic funciona (FIX #1)
    Previene que datos parciales se queden en BD si falla en el medio
    """
    
    def setUp(self):
        """Configuración para tests de transacciones"""
        self.medico = User.objects.create_user(
            username='dr_transaction',
            password='testpass123',
            rol='medico_residente'
        )
        
        self.estudio = Estudios.objects.create(
            nombre='Test Ecografía',
            tipo='ECO',
            conteo_regiones=1,
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
            activo=True
        )
        
        self.sesion = SesionContable.objects.create(
            mes=5,
            año=2026,
            estado='ABIERTA'
        )
    
    def test_registro_con_transaccion_atomica_todo_o_nada(self):
        """
        VALIDACIÓN FIX #1: Si algo falla en form_valid,
        TODO se revierte (no queda monto = 0 en BD)
        """
        # Simular lo que pasa en form_valid (@transaction.atomic)
        with transaction.atomic():
            # Paso 1: Guardar registro
            registro = RegistroEstudiosPorMedico.objects.create(
                medico=self.medico,
                nombre_paciente='Test',
                apellido_paciente='Atomic',
                dni_paciente='12345678',
                fecha_del_informe=date.today(),
                sesion_contable=self.sesion,
                cantidad_regiones=1,
                monto_calculado=Decimal('0.00')
            )
            
            # Paso 2: Crear RegistroEstudio
            RegistroEstudio.objects.create(
                registro=registro,
                estudio=self.estudio,
                cantidad=1
            )
            
            # Paso 3: Calcular monto
            nuevo_monto = registro.calcular_monto()
            
            # Paso 4: Actualizar monto
            registro.monto_calculado = nuevo_monto
            registro.save()
        
        # Verificar que TODO se guardó correctamente
        reg_guardado = RegistroEstudiosPorMedico.objects.get(id=registro.id)
        self.assertNotEqual(reg_guardado.monto_calculado, Decimal('0.00'))
        self.assertEqual(reg_guardado.monto_calculado, nuevo_monto)
    
    def test_consistencia_registro_estudios_con_transaccion(self):
        """
        Si se crea registro pero falla al crear estudios,
        transaction.atomic debe rollbackear TODO (incluido el registro)
        """
        count_before = RegistroEstudiosPorMedico.objects.count()
        
        # Simular transacción con error intencional
        try:
            with transaction.atomic():
                registro = RegistroEstudiosPorMedico.objects.create(
                    medico=self.medico,
                    nombre_paciente='Fail',
                    apellido_paciente='Test',
                    dni_paciente='87654321',
                    fecha_del_informe=date.today(),
                    sesion_contable=self.sesion
                )
                
                # Intentar crear RegistroEstudio con FK inválida (debería fallar)
                with self.assertRaises(Exception):
                    RegistroEstudio.objects.create(
                        registro=registro,
                        estudio_id=99999,  # ID no existe
                        cantidad=1
                    )
        except:
            pass
        
        # Verificar que el registro NO se guardó
        # (porque la transacción se revirtió)
        count_after = RegistroEstudiosPorMedico.objects.count()
        self.assertEqual(count_before, count_after, 
            "❌ FALLA: Transacción no fue revertida. Registro quedó inconsistente.")

    def test_select_for_update_serializa_edicion_en_motores_soportados(self):
        """
        En motores con soporte real de locks (ej. PostgreSQL),
        usamos select_for_update para serializar edición de un mismo registro.
        En SQLite se omite porque no soporta el mismo nivel de lock por fila.
        """
        if connection.vendor == 'sqlite':
            self.skipTest('SQLite no soporta lock por fila con SELECT FOR UPDATE')

        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            nombre_paciente='Lock',
            apellido_paciente='Test',
            dni_paciente='10101010',
            fecha_del_informe=date.today(),
            sesion_contable=self.sesion,
            monto_calculado=Decimal('0.00')
        )

        with transaction.atomic():
            bloqueado = RegistroEstudiosPorMedico.objects.select_for_update().get(id=registro.id)
            bloqueado.monto_calculado = Decimal('1234.00')
            bloqueado.save(update_fields=['monto_calculado'])

        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, Decimal('1234.00'))


class SignalRecalculoAutomaticoTest(TestCase):
    """
    Test para validar que post_save signals funcionan (FIX #4)
    Recalculan monto automáticamente cuando se editan estudios
    """
    
    def setUp(self):
        """Configuración para tests de signals"""
        self.medico = User.objects.create_user(
            username='dr_signal',
            password='testpass123',
            rol='medico_staff'
        )
        
        self.estudio1 = Estudios.objects.create(
            nombre='ECO ABD',
            tipo='ECO',
            conteo_regiones=1,
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
            activo=True
        )
        
        self.estudio2 = Estudios.objects.create(
            nombre='ECO GYNE',
            tipo='ECO',
            conteo_regiones=2,
            conteo_regiones_default=2,
            precio_cober=Decimal('8000.00'),
            precio_otras_os=Decimal('10000.00'),
            activo=True
        )
        
        self.sesion = SesionContable.objects.create(
            mes=5,
            año=2026,
            estado='ABIERTA'
        )
    
    def test_signal_recalcula_cantidad_regiones_automaticamente(self):
        """
        VALIDACIÓN FIX #4: Cuando se agrega RegistroEstudio,
        el signal automáticamente recalcula cantidad_regiones
        """
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            nombre_paciente='Signal',
            apellido_paciente='Test',
            dni_paciente='11111111',
            fecha_del_informe=date.today(),
            sesion_contable=self.sesion,
            cantidad_regiones=0  # Empezar en 0
        )
        
        # Sin agregar estudios todavía
        self.assertEqual(registro.cantidad_regiones, 0)
        
        # Agregar primer estudio (1 región)
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio1,
            cantidad=1
        )
        
        # Recargar del DB
        registro.refresh_from_db()
        
        # Signal debe haber recalculado a 1 región
        self.assertEqual(registro.cantidad_regiones, 1,
            "❌ FALLA: Signal no recalculó cantidad_regiones automáticamente")
    
    def test_signal_recalcula_monto_cuando_se_agrega_estudio(self):
        """
        VALIDACIÓN FIX #4: Cuando se agrega RegistroEstudio,
        el signal automáticamente recalcula monto_calculado
        """
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            nombre_paciente='Signal',
            apellido_paciente='Monto',
            dni_paciente='22222222',
            fecha_del_informe=date.today(),
            sesion_contable=self.sesion,
            tipo_obra_social='COBER',
            cantidad_regiones=0,
            monto_calculado=Decimal('0.00')  # Empezar en $0
        )
        
        # Verificar que monto es 0 inicialmente
        self.assertEqual(registro.monto_calculado, Decimal('0.00'))
        
        # Agregar estudio
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio1,  # $5000 para staff
            cantidad=1
        )
        
        # Recargar del DB
        registro.refresh_from_db()
        
        # Signal debe haber recalculado a $5000
        self.assertEqual(registro.monto_calculado, Decimal('5000.00'),
            f"❌ FALLA: Signal no recalculó monto. "
            f"Esperado $5000, pero tiene ${registro.monto_calculado}")
    
    def test_signal_recalcula_con_multiples_estudios(self):
        """
        Cuando hay múltiples estudios, la cantidad de regiones
        es la suma de todos
        """
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            nombre_paciente='Multi',
            apellido_paciente='Estudio',
            dni_paciente='33333333',
            fecha_del_informe=date.today(),
            sesion_contable=self.sesion,
            cantidad_regiones=0
        )
        
        # Agregar dos estudios
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio1,  # 1 región
            cantidad=1
        )
        
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio2,  # 2 regiones
            cantidad=1
        )
        
        registro.refresh_from_db()
        
        # Debe haber 3 regiones totales (1 + 2)
        self.assertEqual(registro.cantidad_regiones, 3,
            f"❌ FALLA: Signal no sumó regiones correctamente. "
            f"Esperado 3, pero tiene {registro.cantidad_regiones}")


class SesionContableConstraintTest(TestCase):
    """
    Test para validar que la validación en puede_registrar_practicas funciona (FIX #3)
    Aunque el DB constraint solo se applica en PostgreSQL,
    la lógica Python debe prevenir inserciones en sesiones cerradas
    """
    
    def setUp(self):
        """Configuración para tests de permisos"""
        self.medico = User.objects.create_user(
            username='dr_permisos',
            password='testpass123',
            rol='medico_residente'
        )
        
        self.sesion_abierta = SesionContable.objects.create(
            mes=5,
            año=2026,
            estado='ABIERTA'
        )
        
        self.sesion_cerrada = SesionContable.objects.create(
            mes=4,
            año=2026,
            estado='CERRADA'
        )
    
    def test_puede_registrar_practicas_sesion_abierta(self):
        """Médico residente CAN registrar en sesión ABIERTA"""
        puede = self.sesion_abierta.puede_registrar_practicas(self.medico)
        self.assertTrue(puede,
            "❌ FALLA: Residente debe poder registrar en sesión ABIERTA")
    
    def test_puede_registrar_practicas_sesion_cerrada(self):
        """Médico residente CANNOT registrar en sesión CERRADA"""
        puede = self.sesion_cerrada.puede_registrar_practicas(self.medico)
        self.assertFalse(puede,
            "❌ FALLA: Residente NO debe poder registrar en sesión CERRADA")
    
    def test_admin_puede_registrar_en_cerrada(self):
        """Admin CAN registrar incluso en sesión CERRADA"""
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        
        puede = self.sesion_cerrada.puede_registrar_practicas(admin)
        self.assertTrue(puede,
            "❌ FALLA: Admin debe poder registrar en sesión CERRADA")


class PermisosYTrazabilidadViewTest(TestCase):
    """Tests de regresión para permisos de vistas y operaciones sensibles."""

    def setUp(self):
        self.password = 'testpass123'
        self.superuser = User.objects.create_superuser(
            username='root_liq',
            email='root_liq@test.com',
            password=self.password,
        )
        self.admin = User.objects.create_user(
            username='admin_liq',
            password=self.password,
            rol='administrativo',
            perfil_completo=True,
        )
        self.jefe_servicio = User.objects.create_user(
            username='jefe_servicio_liq',
            password=self.password,
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.jefe_residentes = User.objects.create_user(
            username='jefe_res_liq',
            password=self.password,
            rol='jefe_residentes',
            perfil_completo=True,
        )
        self.instructor = User.objects.create_user(
            username='inst_liq',
            password=self.password,
            rol='instructor_residentes',
            perfil_completo=True,
        )
        self.medico = User.objects.create_user(
            username='medico_liq',
            password=self.password,
            rol='medico_staff',
            perfil_completo=True,
        )
        self.residente = User.objects.create_user(
            username='residente_liq',
            password=self.password,
            rol='medico_residente',
            perfil_completo=True,
        )

    def test_liquidacion_mensual_permite_admin_y_jefe_servicio(self):
        self.client.login(username='admin_liq', password='testpass123')
        response_admin = self.client.get(reverse('liquidacion:liquidacion_mensual'))
        self.assertEqual(response_admin.status_code, 200)

        self.client.logout()
        self.client.login(username='jefe_servicio_liq', password='testpass123')
        response_jefe_servicio = self.client.get(reverse('liquidacion:liquidacion_mensual'))
        self.assertEqual(response_jefe_servicio.status_code, 200)

    def test_liquidacion_mensual_deniega_jefe_residentes_e_instructor(self):
        self.client.login(username='jefe_res_liq', password='testpass123')
        response_jefe = self.client.get(reverse('liquidacion:liquidacion_mensual'))
        self.assertEqual(response_jefe.status_code, 302)

        self.client.logout()
        self.client.login(username='inst_liq', password='testpass123')
        response_instructor = self.client.get(reverse('liquidacion:liquidacion_mensual'))
        self.assertEqual(response_instructor.status_code, 302)

    def test_delete_registro_bloqueado_en_sesion_cerrada_para_medico(self):
        sesion_cerrada = SesionContable.objects.create(mes=4, año=2026, estado='CERRADA')
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            nombre_paciente='Bloqueo',
            apellido_paciente='Cerrada',
            dni_paciente='90909090',
            fecha_del_informe=date.today(),
            sesion_contable=sesion_cerrada,
        )

        self.client.login(username='medico_liq', password='testpass123')
        response = self.client.post(reverse('liquidacion:registroestudios_delete', kwargs={'pk': registro.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).exists(),
            '❌ FALLA: Un médico pudo eliminar registro en sesión cerrada.'
        )

    def test_estudios_list_permite_admin_jefe_y_superuser(self):
        self.client.force_login(self.superuser)
        response_super = self.client.get(reverse('liquidacion:estudios_list'))
        self.assertEqual(response_super.status_code, 200)

        self.client.force_login(self.admin)
        response_admin = self.client.get(reverse('liquidacion:estudios_list'))
        self.assertEqual(response_admin.status_code, 200)

        self.client.force_login(self.jefe_servicio)
        response_jefe = self.client.get(reverse('liquidacion:estudios_list'))
        self.assertEqual(response_jefe.status_code, 200)

    def test_estudios_list_deniega_medico_y_residente(self):
        self.client.force_login(self.medico)
        response_medico = self.client.get(reverse('liquidacion:estudios_list'))
        self.assertIn(response_medico.status_code, [302, 403])

        self.client.force_login(self.residente)
        response_residente = self.client.get(reverse('liquidacion:estudios_list'))
        self.assertIn(response_residente.status_code, [302, 403])

    def test_estudios_list_renderiza_sin_noreversematch_y_con_namespace(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('liquidacion:estudios_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('liquidacion:estudios_nuevo'))

    def test_estudios_form_renderiza_sin_noreversematch_y_con_namespace(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('liquidacion:estudios_nuevo'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('liquidacion:estudios_list'))

    def test_portal_inicio_muestra_tarjeta_estudios_activa(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('liquidacion:portal_inicio'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gestión de estudios')
        self.assertContains(response, reverse('liquidacion:estudios_list'))

    def test_grupos_tarifarios_list_permite_super_admin_y_jefe_servicio(self):
        self.client.force_login(self.superuser)
        response_super = self.client.get(reverse('liquidacion:grupos_tarifarios_list'))
        self.assertEqual(response_super.status_code, 200)

        self.client.force_login(self.admin)
        response_admin = self.client.get(reverse('liquidacion:grupos_tarifarios_list'))
        self.assertEqual(response_admin.status_code, 200)

        self.client.force_login(self.jefe_servicio)
        response_jefe = self.client.get(reverse('liquidacion:grupos_tarifarios_list'))
        self.assertEqual(response_jefe.status_code, 200)

    def test_grupos_tarifarios_list_deniega_medico_y_residente(self):
        self.client.force_login(self.medico)
        response_medico = self.client.get(reverse('liquidacion:grupos_tarifarios_list'))
        self.assertIn(response_medico.status_code, [302, 403])

        self.client.force_login(self.residente)
        response_residente = self.client.get(reverse('liquidacion:grupos_tarifarios_list'))
        self.assertIn(response_residente.status_code, [302, 403])

    def test_grupos_tarifarios_list_renderiza_grupo_con_tarifa_y_sin_tarifa(self):
        grupo_con_tarifa = GrupoTarifario.objects.create(
            codigo='ECO_AUDIT_1',
            nombre='Grupo con tarifa vigente',
            modalidad='ECO',
            activo=True,
        )
        grupo_sin_tarifa = GrupoTarifario.objects.create(
            codigo='RAD_AUDIT_2',
            nombre='Grupo sin tarifa vigente',
            modalidad='RAD',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=grupo_con_tarifa,
            vigencia_desde=date(2026, 1, 1),
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1200.00'),
        )
        Estudios.objects.create(
            nombre='ESTUDIO AUDIT 1',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1200.00'),
            grupo_tarifario=grupo_con_tarifa,
            activo=True,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse('liquidacion:grupos_tarifarios_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, grupo_con_tarifa.codigo)
        self.assertContains(response, grupo_sin_tarifa.codigo)
        self.assertContains(response, 'Con tarifa vigente')
        self.assertContains(response, 'Sin tarifa vigente')

    def test_portal_inicio_muestra_tarjeta_tarifas_activa(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('liquidacion:portal_inicio'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Configuración económica / tarifas')
        self.assertContains(response, reverse('liquidacion:grupos_tarifarios_list'))

    def test_grupo_tarifario_detalle_permite_super_admin_y_jefe_servicio(self):
        grupo = GrupoTarifario.objects.create(
            codigo='DET_ALLOW_1',
            nombre='Grupo detalle acceso',
            modalidad='ECO',
            activo=True,
        )

        self.client.force_login(self.superuser)
        response_super = self.client.get(
            reverse('liquidacion:grupo_tarifario_detalle', kwargs={'pk': grupo.pk})
        )
        self.assertEqual(response_super.status_code, 200)

        self.client.force_login(self.admin)
        response_admin = self.client.get(
            reverse('liquidacion:grupo_tarifario_detalle', kwargs={'pk': grupo.pk})
        )
        self.assertEqual(response_admin.status_code, 200)

        self.client.force_login(self.jefe_servicio)
        response_jefe = self.client.get(
            reverse('liquidacion:grupo_tarifario_detalle', kwargs={'pk': grupo.pk})
        )
        self.assertEqual(response_jefe.status_code, 200)

    def test_grupo_tarifario_detalle_deniega_medico_y_residente(self):
        grupo = GrupoTarifario.objects.create(
            codigo='DET_DENY_1',
            nombre='Grupo detalle denegado',
            modalidad='RAD',
            activo=True,
        )

        self.client.force_login(self.medico)
        response_medico = self.client.get(
            reverse('liquidacion:grupo_tarifario_detalle', kwargs={'pk': grupo.pk})
        )
        self.assertIn(response_medico.status_code, [302, 403])

        self.client.force_login(self.residente)
        response_residente = self.client.get(
            reverse('liquidacion:grupo_tarifario_detalle', kwargs={'pk': grupo.pk})
        )
        self.assertIn(response_residente.status_code, [302, 403])

    def test_grupo_tarifario_detalle_renderiza_con_tarifa_vigente(self):
        grupo = GrupoTarifario.objects.create(
            codigo='DET_VIG_1',
            nombre='Grupo con vigente',
            modalidad='ECO',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=grupo,
            vigencia_desde=date(2026, 1, 1),
            precio_cober=Decimal('2200.00'),
            precio_otras_os=Decimal('2500.00'),
        )

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('liquidacion:grupo_tarifario_detalle', kwargs={'pk': grupo.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, grupo.codigo)
        self.assertContains(response, 'Con tarifa vigente')

    def test_grupo_tarifario_detalle_renderiza_sin_tarifa_vigente_con_advertencia(self):
        grupo = GrupoTarifario.objects.create(
            codigo='DET_SIN_1',
            nombre='Grupo sin vigente',
            modalidad='RAD',
            activo=True,
        )

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('liquidacion:grupo_tarifario_detalle', kwargs={'pk': grupo.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Advertencia: este grupo no tiene tarifa vigente activa.')

    def test_grupo_tarifario_detalle_muestra_estudios_asociados(self):
        grupo = GrupoTarifario.objects.create(
            codigo='DET_EST_1',
            nombre='Grupo con estudios',
            modalidad='ECO',
            activo=True,
        )
        estudio = Estudios.objects.create(
            nombre='Estudio detalle asociado',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('3000.00'),
            precio_otras_os=Decimal('3500.00'),
            grupo_tarifario=grupo,
            activo=True,
        )

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('liquidacion:grupo_tarifario_detalle', kwargs={'pk': grupo.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, estudio.nombre)
        self.assertContains(response, 'Total: 1 estudio(s).')

    def test_grupos_tarifarios_list_contiene_link_a_detalle(self):
        grupo = GrupoTarifario.objects.create(
            codigo='LIST_DET_1',
            nombre='Grupo link detalle',
            modalidad='ECO',
            activo=True,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse('liquidacion:grupos_tarifarios_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('liquidacion:grupo_tarifario_detalle', kwargs={'pk': grupo.pk}),
        )

    def test_grupo_tarifario_tarifa_nueva_permite_super_admin_y_jefe_servicio(self):
        grupo = GrupoTarifario.objects.create(
            codigo='TAR_NEW_ALLOW',
            nombre='Grupo alta permitida',
            modalidad='ECO',
            activo=True,
        )
        url = reverse('liquidacion:grupo_tarifario_tarifa_nueva', kwargs={'grupo_pk': grupo.pk})

        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.jefe_servicio)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_grupo_tarifario_tarifa_nueva_deniega_medico_y_residente(self):
        grupo = GrupoTarifario.objects.create(
            codigo='TAR_NEW_DENY',
            nombre='Grupo alta denegada',
            modalidad='RAD',
            activo=True,
        )
        url = reverse('liquidacion:grupo_tarifario_tarifa_nueva', kwargs={'grupo_pk': grupo.pk})

        self.client.force_login(self.medico)
        self.assertIn(self.client.get(url).status_code, [302, 403])

        self.client.force_login(self.residente)
        self.assertIn(self.client.get(url).status_code, [302, 403])

    def test_grupo_tarifario_tarifa_nueva_crea_tarifa_valida(self):
        grupo = GrupoTarifario.objects.create(
            codigo='TAR_NEW_OK_1',
            nombre='Grupo alta valida',
            modalidad='ECO',
            activo=True,
        )
        url = reverse('liquidacion:grupo_tarifario_tarifa_nueva', kwargs={'grupo_pk': grupo.pk})

        self.client.force_login(self.admin)
        response = self.client.post(
            url,
            data={
                'vigencia_desde': '2027-01-01',
                'vigencia_hasta': '2027-12-31',
                'precio_cober': '2000.00',
                'precio_otras_os': '2500.00',
                'motivo_actualizacion': 'Ajuste anual',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            TarifaGrupoTarifario.objects.filter(
                grupo_tarifario=grupo,
                vigencia_desde=date(2027, 1, 1),
            ).exists()
        )

    def test_grupo_tarifario_tarifa_nueva_setea_actualizado_por(self):
        grupo = GrupoTarifario.objects.create(
            codigo='TAR_NEW_OK_2',
            nombre='Grupo audit user',
            modalidad='TOM',
            activo=True,
        )
        url = reverse('liquidacion:grupo_tarifario_tarifa_nueva', kwargs={'grupo_pk': grupo.pk})

        self.client.force_login(self.admin)
        self.client.post(
            url,
            data={
                'vigencia_desde': '2028-01-01',
                'vigencia_hasta': '',
                'precio_cober': '3000.00',
                'precio_otras_os': '3500.00',
                'motivo_actualizacion': 'Ajuste por convenio',
            },
        )
        tarifa = TarifaGrupoTarifario.objects.get(grupo_tarifario=grupo, vigencia_desde=date(2028, 1, 1))
        self.assertEqual(tarifa.actualizado_por, self.admin)

    def test_grupo_tarifario_tarifa_nueva_rechaza_precio_cober_menor_igual_cero(self):
        grupo = GrupoTarifario.objects.create(
            codigo='TAR_VAL_COBER',
            nombre='Grupo valida cober',
            modalidad='ECO',
            activo=True,
        )
        url = reverse('liquidacion:grupo_tarifario_tarifa_nueva', kwargs={'grupo_pk': grupo.pk})

        self.client.force_login(self.admin)
        response = self.client.post(
            url,
            data={
                'vigencia_desde': '2029-01-01',
                'vigencia_hasta': '',
                'precio_cober': '0',
                'precio_otras_os': '2200.00',
                'motivo_actualizacion': 'Test inválido',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'El precio COBER debe ser mayor a 0.')

    def test_grupo_tarifario_tarifa_nueva_rechaza_precio_otras_os_menor_igual_cero(self):
        grupo = GrupoTarifario.objects.create(
            codigo='TAR_VAL_OTRAS',
            nombre='Grupo valida otras',
            modalidad='RAD',
            activo=True,
        )
        url = reverse('liquidacion:grupo_tarifario_tarifa_nueva', kwargs={'grupo_pk': grupo.pk})

        self.client.force_login(self.admin)
        response = self.client.post(
            url,
            data={
                'vigencia_desde': '2029-02-01',
                'vigencia_hasta': '',
                'precio_cober': '2200.00',
                'precio_otras_os': '0',
                'motivo_actualizacion': 'Test inválido',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'El precio OTRAS OS debe ser mayor a 0.')

    def test_grupo_tarifario_tarifa_nueva_rechaza_vigencia_hasta_anterior(self):
        grupo = GrupoTarifario.objects.create(
            codigo='TAR_VAL_FECHA',
            nombre='Grupo valida fechas',
            modalidad='RES',
            activo=True,
        )
        url = reverse('liquidacion:grupo_tarifario_tarifa_nueva', kwargs={'grupo_pk': grupo.pk})

        self.client.force_login(self.admin)
        response = self.client.post(
            url,
            data={
                'vigencia_desde': '2029-03-10',
                'vigencia_hasta': '2029-03-01',
                'precio_cober': '3000.00',
                'precio_otras_os': '3200.00',
                'motivo_actualizacion': 'Test fechas',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'La vigencia hasta no puede ser anterior a vigencia desde.')

    def test_grupo_tarifario_tarifa_nueva_rechaza_solapamiento_vigencias(self):
        grupo = GrupoTarifario.objects.create(
            codigo='TAR_VAL_SOLAP',
            nombre='Grupo valida solap',
            modalidad='DOP',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=grupo,
            vigencia_desde=date(2029, 1, 1),
            vigencia_hasta=None,
            precio_cober=Decimal('2500.00'),
            precio_otras_os=Decimal('2700.00'),
        )
        url = reverse('liquidacion:grupo_tarifario_tarifa_nueva', kwargs={'grupo_pk': grupo.pk})

        self.client.force_login(self.admin)
        response = self.client.post(
            url,
            data={
                'vigencia_desde': '2029-06-01',
                'vigencia_hasta': '',
                'precio_cober': '2800.00',
                'precio_otras_os': '3000.00',
                'motivo_actualizacion': 'Intento solapado',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe una tarifa con vigencia que se solapa para este grupo tarifario.')

    def test_grupo_tarifario_tarifa_nueva_permite_tarifa_futura_no_solapada(self):
        grupo = GrupoTarifario.objects.create(
            codigo='TAR_VAL_FUTURA',
            nombre='Grupo valida futura',
            modalidad='ECOCAR',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=grupo,
            vigencia_desde=date(2029, 1, 1),
            vigencia_hasta=date(2029, 12, 31),
            precio_cober=Decimal('4000.00'),
            precio_otras_os=Decimal('4300.00'),
        )
        url = reverse('liquidacion:grupo_tarifario_tarifa_nueva', kwargs={'grupo_pk': grupo.pk})

        self.client.force_login(self.admin)
        response = self.client.post(
            url,
            data={
                'vigencia_desde': '2030-01-01',
                'vigencia_hasta': '',
                'precio_cober': '4500.00',
                'precio_otras_os': '4700.00',
                'motivo_actualizacion': 'Nueva vigencia anual',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            TarifaGrupoTarifario.objects.filter(
                grupo_tarifario=grupo,
                vigencia_desde=date(2030, 1, 1),
            ).exists()
        )

    def test_grupo_tarifario_detalle_muestra_boton_nueva_tarifa(self):
        grupo = GrupoTarifario.objects.create(
            codigo='DET_BTN_TAR',
            nombre='Grupo botón tarifa',
            modalidad='ECO',
            activo=True,
        )

        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('liquidacion:grupo_tarifario_detalle', kwargs={'pk': grupo.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nueva tarifa')
        self.assertContains(
            response,
            reverse('liquidacion:grupo_tarifario_tarifa_nueva', kwargs={'grupo_pk': grupo.pk}),
        )


class SesionContableWorkflowPermissionsTest(TestCase):
    """Blindaje de permisos y flujo de transiciones de SesionContable."""

    def setUp(self):
        self.password = 'testpass123'
        self._mes_seq = 1
        self.superuser = User.objects.create_superuser(
            username='root_sesiones',
            email='root_sesiones@test.com',
            password=self.password,
        )
        self.admin = User.objects.create_user(
            username='admin_sesiones',
            password=self.password,
            rol='administrativo',
            perfil_completo=True,
        )
        self.jefe_servicio = User.objects.create_user(
            username='jefe_servicio_sesiones',
            password=self.password,
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.medico_staff = User.objects.create_user(
            username='staff_sesiones',
            password=self.password,
            rol='medico_staff',
            perfil_completo=True,
        )
        self.medico_residente = User.objects.create_user(
            username='residente_sesiones',
            password=self.password,
            rol='medico_residente',
            perfil_completo=True,
        )
        self.jefe_residentes = User.objects.create_user(
            username='jefe_res_sesiones',
            password=self.password,
            rol='jefe_residentes',
            perfil_completo=True,
        )
        self.instructor = User.objects.create_user(
            username='instructor_sesiones',
            password=self.password,
            rol='instructor_residentes',
            perfil_completo=True,
        )

    def _login(self, user):
        self.client.force_login(user)

    def _crear_sesion(self, estado):
        sesion = SesionContable.objects.create(mes=self._mes_seq, año=2026, estado=estado)
        self._mes_seq += 1
        return sesion

    def test_portal_inicio_requiere_login(self):
        response = self.client.get(reverse('liquidacion:portal_inicio'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/'))

    def test_portal_inicio_permite_super_admin_y_jefe_servicio(self):
        for user in [self.superuser, self.admin, self.jefe_servicio]:
            self.client.logout()
            self._login(user)
            response = self.client.get(reverse('liquidacion:portal_inicio'))
            self.assertEqual(
                response.status_code,
                200,
                f"❌ FALLA: {user.username} debería acceder al portal administrativo",
            )

    def test_portal_inicio_deniega_roles_no_administrativos(self):
        for user in [self.medico_staff, self.medico_residente, self.jefe_residentes, self.instructor]:
            self.client.logout()
            self._login(user)
            response = self.client.get(reverse('liquidacion:portal_inicio'))
            self.assertEqual(
                response.status_code,
                302,
                f"❌ FALLA: {user.username} NO debería acceder al portal administrativo",
            )

    def test_sesiones_list_requiere_login(self):
        response = self.client.get(reverse('liquidacion:sesiones_list'))
        self.assertEqual(response.status_code, 302)
        # En este proyecto el middleware global puede redirigir anónimos a '/'.
        self.assertTrue(response.url.startswith('/'))

    def test_sesiones_list_permite_super_admin_y_jefe_servicio(self):
        for user in [self.superuser, self.admin, self.jefe_servicio]:
            self.client.logout()
            self._login(user)
            response = self.client.get(reverse('liquidacion:sesiones_list'))
            self.assertEqual(
                response.status_code,
                200,
                f"❌ FALLA: {user.username} debería acceder a sesiones_list",
            )

    def test_sesiones_list_deniega_roles_medicos_y_docencia(self):
        for user in [self.medico_staff, self.medico_residente, self.jefe_residentes, self.instructor]:
            self.client.logout()
            self._login(user)
            response = self.client.get(reverse('liquidacion:sesiones_list'))
            self.assertEqual(
                response.status_code,
                302,
                f"❌ FALLA: {user.username} NO debería acceder a sesiones_list",
            )

    def test_transicion_get_no_modifica_estado(self):
        sesion = self._crear_sesion('ABIERTA')
        self._login(self.admin)

        response = self.client.get(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
        self.assertEqual(response.status_code, 302)

        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'ABIERTA')

    def test_transicion_put_no_modifica_estado(self):
        sesion = self._crear_sesion('ABIERTA')
        self._login(self.admin)

        response = self.client.generic('PUT', reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
        self.assertEqual(response.status_code, 302)

        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'ABIERTA')

    def test_transicion_abierta_a_revision_permitida_para_admin_y_jefe_servicio(self):
        for user in [self.admin, self.jefe_servicio, self.superuser]:
            sesion = self._crear_sesion('ABIERTA')
            self.client.logout()
            self._login(user)
            response = self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
            self.assertEqual(response.status_code, 302)
            sesion.refresh_from_db()
            self.assertEqual(sesion.estado, 'REVISION')

    def test_transicion_revision_a_cerrada_permitida_para_admin_y_jefe_servicio(self):
        for user in [self.admin, self.jefe_servicio, self.superuser]:
            sesion = self._crear_sesion('REVISION')
            self.client.logout()
            self._login(user)
            response = self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
            self.assertEqual(response.status_code, 302)
            sesion.refresh_from_db()
            self.assertEqual(sesion.estado, 'CERRADA')

    def test_transicion_financiera_denegada_para_jefe_servicio(self):
        sesion = self._crear_sesion('CERRADA')
        self._login(self.jefe_servicio)

        response = self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
        self.assertEqual(response.status_code, 302)

        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'CERRADA')

    def test_transicion_financiera_permitida_para_admin_y_superuser(self):
        for user in [self.admin, self.superuser]:
            sesion = self._crear_sesion('CERRADA')
            grupo = GrupoTarifario.objects.create(
                codigo=f'ECO_FACT_{sesion.pk}_{user.pk}',
                nombre='Grupo facturacion valida',
                modalidad='ECO',
                activo=True,
            )
            TarifaGrupoTarifario.objects.create(
                grupo_tarifario=grupo,
                vigencia_desde=date(2026, 1, 1),
                precio_cober=Decimal('5000.00'),
                precio_otras_os=Decimal('7000.00'),
            )
            estudio = Estudios.objects.create(
                nombre=f'ECO FACT {sesion.pk}_{user.pk}',
                tipo='ECO',
                conteo_regiones=1,
                conteo_regiones_default=1,
                precio_cober=Decimal('5000.00'),
                precio_otras_os=Decimal('7000.00'),
                grupo_tarifario=grupo,
                activo=True,
            )
            registro = RegistroEstudiosPorMedico.objects.create(
                medico=self.medico_staff,
                nombre_paciente='Facturacion',
                apellido_paciente='Valida',
                dni_paciente='55443322',
                fecha_del_informe=date(2026, sesion.mes, 10),
                sesion_contable=sesion,
                tipo_obra_social='COBER',
                horario='NA',
                monto_calculado=Decimal('5000.00'),
            )
            RegistroEstudio.objects.create(
                registro=registro,
                estudio=estudio,
                cantidad=1,
                contexto='SERVICIO',
            )

            self.client.logout()
            self._login(user)
            response = self.client.post(
                reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}),
                data={'motivo': 'Cierre de facturacion del periodo'},
            )
            self.assertEqual(response.status_code, 302)
            sesion.refresh_from_db()
            self.assertEqual(sesion.estado, 'FACTURADA')

    def test_transicion_denegada_para_roles_no_administrativos(self):
        sesion = self._crear_sesion('ABIERTA')
        self._login(self.medico_staff)

        response = self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
        self.assertEqual(response.status_code, 302)

        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'ABIERTA')

    def test_sesion_pagada_no_transiciona_ni_con_admin_ni_superuser(self):
        for user in [self.admin, self.superuser]:
            sesion = self._crear_sesion('PAGADA')
            self.client.logout()
            self._login(user)
            response = self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
            self.assertEqual(response.status_code, 302)
            sesion.refresh_from_db()
            self.assertEqual(sesion.estado, 'PAGADA')

    def test_flujo_valido_completo_abierta_a_pagada(self):
        sesion = self._crear_sesion('ABIERTA')
        grupo = GrupoTarifario.objects.create(
            codigo=f'ECO_FLUJO_{sesion.pk}',
            nombre='Grupo flujo valido',
            modalidad='ECO',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=grupo,
            vigencia_desde=date(2026, 1, 1),
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
        )
        estudio = Estudios.objects.create(
            nombre=f'ECO FLUJO {sesion.pk}',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
            grupo_tarifario=grupo,
            activo=True,
        )
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico_staff,
            nombre_paciente='Flujo',
            apellido_paciente='Valido',
            dni_paciente='99887766',
            fecha_del_informe=date(2026, sesion.mes, 10),
            sesion_contable=sesion,
            tipo_obra_social='COBER',
            horario='NA',
            monto_calculado=Decimal('5000.00'),
        )
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=estudio,
            cantidad=1,
            contexto='SERVICIO',
        )

        self._login(self.admin)

        r1 = self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
        self.assertEqual(r1.status_code, 302)
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'REVISION')

        r2 = self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
        self.assertEqual(r2.status_code, 302)
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'CERRADA')

        r3 = self.client.post(
            reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}),
            data={'motivo': 'Facturacion validada por administracion'},
        )
        self.assertEqual(r3.status_code, 302)
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'FACTURADA')

        r4 = self.client.post(
            reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}),
            data={'motivo': 'Pago confirmado por tesoreria'},
        )
        self.assertEqual(r4.status_code, 302)
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'PAGADA')


class SesionContableAdminGovernanceTest(TestCase):
    """Fase 1: blindaje de bypass de estado desde Django admin."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin_governance',
            password='testpass123',
            rol='administrativo',
            perfil_completo=True,
            is_staff=True,
        )
        self.rf = RequestFactory()
        self.site = AdminSite()

    def test_admin_estado_es_readonly(self):
        from liquidacion.admin import SesionContableAdmin

        model_admin = SesionContableAdmin(SesionContable, self.site)
        request = self.rf.get('/admin/liquidacion/sesioncontable/1/change/')
        request.user = self.admin_user

        readonly = model_admin.get_readonly_fields(request)
        self.assertIn('estado', readonly)

    def test_admin_action_no_permite_salto_abierta_a_pagada(self):
        from liquidacion.admin import SesionContableAdmin

        sesion = SesionContable.objects.create(mes=10, año=2026, estado='ABIERTA')
        model_admin = SesionContableAdmin(SesionContable, self.site)
        model_admin.message_user = lambda *args, **kwargs: None
        request = self.rf.post('/admin/liquidacion/sesioncontable/')
        request.user = self.admin_user

        model_admin.marcar_pagada(request, SesionContable.objects.filter(pk=sesion.pk))
        sesion.refresh_from_db()

        self.assertEqual(
            sesion.estado,
            'ABIERTA',
            '❌ FALLA: se permitió salto arbitrario de ABIERTA a PAGADA desde admin action.',
        )


class SesionContableConsistencyGateTest(TestCase):
    """Fase 2: Gate de consistencia pre-cierre/pre-facturacion."""

    def setUp(self):
        self.password = 'testpass123'
        self.admin = User.objects.create_user(
            username='admin_gate',
            password=self.password,
            rol='administrativo',
            perfil_completo=True,
            is_staff=True,
        )
        self.medico = User.objects.create_user(
            username='medico_gate',
            password=self.password,
            rol='medico_staff',
            perfil_completo=True,
        )

        self.grupo = GrupoTarifario.objects.create(
            codigo='ECO_GATE',
            nombre='Ecografia Gate',
            modalidad='ECO',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.grupo,
            vigencia_desde=date(2026, 1, 1),
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
        )

        self.estudio_con_grupo = Estudios.objects.create(
            nombre='ECO GATE OK',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
            grupo_tarifario=self.grupo,
            activo=True,
        )

        self.estudio_sin_grupo_legacy = Estudios.objects.create(
            nombre='ECO LEGACY OK',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('4000.00'),
            precio_otras_os=Decimal('6000.00'),
            activo=True,
        )

        self.estudio_grupo_sin_tarifa = Estudios.objects.create(
            nombre='ECO SIN TARIFA VIGENTE',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('4000.00'),
            precio_otras_os=Decimal('6000.00'),
            grupo_tarifario=GrupoTarifario.objects.create(
                codigo='ECO_SIN_TARIFA',
                nombre='Grupo sin tarifa',
                modalidad='ECO',
                activo=True,
            ),
            activo=True,
        )

        self.estudio_contextual = Estudios.objects.create(
            nombre='DOP CONTEXTUAL',
            tipo='DOP',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('11000.00'),
            precio_otras_os=Decimal('12000.00'),
            grupo_tarifario=GrupoTarifario.objects.create(
                codigo='DOP_CTX',
                nombre='Doppler Contextual Base',
                modalidad='DOP',
                activo=True,
            ),
            tiene_contexto_ubicacion=True,
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.estudio_contextual.grupo_tarifario,
            vigencia_desde=date(2026, 1, 1),
            precio_cober=Decimal('11000.00'),
            precio_otras_os=Decimal('12000.00'),
        )

    def _login_admin(self):
        self.client.force_login(self.admin)

    def _crear_registro(self, sesion, estudio, monto=Decimal('5000.00')):
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            nombre_paciente='Paciente',
            apellido_paciente='Gate',
            dni_paciente=f'{sesion.pk:02}123456',
            fecha_del_informe=date(2026, sesion.mes, 10),
            sesion_contable=sesion,
            tipo_obra_social='COBER',
            horario='NA',
            monto_calculado=monto,
        )
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=estudio,
            cantidad=1,
            contexto='SERVICIO',
        )
        return registro

    def test_bloquea_revision_a_cerrada_si_registro_sin_registroestudio(self):
        sesion = SesionContable.objects.create(mes=8, año=2026, estado='REVISION')
        RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            nombre_paciente='Sin',
            apellido_paciente='Estudio',
            dni_paciente='80808080',
            fecha_del_informe=date(2026, 8, 10),
            sesion_contable=sesion,
            tipo_obra_social='COBER',
            horario='NA',
            monto_calculado=Decimal('5000.00'),
        )

        self._login_admin()
        self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'REVISION')

    def test_bloquea_revision_a_cerrada_si_monto_cero_con_estudios(self):
        sesion = SesionContable.objects.create(mes=9, año=2026, estado='REVISION')
        registro = self._crear_registro(sesion, self.estudio_con_grupo, monto=Decimal('5000.00'))
        registro.monto_calculado = Decimal('0.00')
        registro.save(update_fields=['monto_calculado'])

        self._login_admin()
        self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'REVISION')

    def test_bloquea_revision_a_cerrada_si_guardia_monto_invalido(self):
        sesion = SesionContable.objects.create(mes=10, año=2026, estado='REVISION')
        guardia = GuardiaPasiva.objects.create(
            sesion_contable=sesion,
            medico=self.medico,
            fecha_guardia=date(2026, 10, 10),
            tipo_guardia='COBER',
        )
        guardia.monto = Decimal('0.00')
        guardia.save(update_fields=['monto'])

        self._login_admin()
        self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'REVISION')

    def test_bloquea_cerrada_a_facturada_si_sesion_vacia(self):
        sesion = SesionContable.objects.create(mes=11, año=2026, estado='CERRADA')

        self._login_admin()
        self.client.post(
            reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}),
            data={'motivo': 'Intento de facturacion vacia'},
        )
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'CERRADA')

    def test_bloquea_facturada_a_pagada_si_sesion_vacia(self):
        sesion = SesionContable.objects.create(mes=12, año=2026, estado='FACTURADA')

        self._login_admin()
        self.client.post(
            reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}),
            data={'motivo': 'Intento de pago sin contenido'},
        )
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'FACTURADA')

    def test_bloquea_cerrada_a_facturada_si_grupo_sin_tarifa_vigente(self):
        sesion = SesionContable.objects.create(mes=1, año=2027, estado='CERRADA')
        self._crear_registro(sesion, self.estudio_grupo_sin_tarifa, monto=Decimal('4000.00'))

        self._login_admin()
        self.client.post(
            reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}),
            data={'motivo': 'Facturacion con tarifa ausente'},
        )
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'CERRADA')

    def test_bloquea_cerrada_a_facturada_si_contexto_lecho_sin_tarifa_contextual(self):
        sesion = SesionContable.objects.create(mes=2, año=2027, estado='CERRADA')
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            nombre_paciente='Paciente',
            apellido_paciente='Contexto',
            dni_paciente='22222222',
            fecha_del_informe=date(2027, 2, 10),
            sesion_contable=sesion,
            tipo_obra_social='COBER',
            horario='NA',
            monto_calculado=Decimal('11000.00'),
        )
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio_contextual,
            cantidad=1,
            contexto='LECHO',
        )

        self._login_admin()
        self.client.post(
            reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}),
            data={'motivo': 'Facturacion sin tarifa contextual'},
        )
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'CERRADA')

    def test_advertencia_no_bloquea_sin_grupo_con_fallback_legacy_valido(self):
        sesion = SesionContable.objects.create(mes=3, año=2027, estado='CERRADA')
        self._crear_registro(sesion, self.estudio_sin_grupo_legacy, monto=Decimal('4000.00'))

        self._login_admin()
        self.client.post(
            reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}),
            data={'motivo': 'Facturacion legacy con fallback'},
            follow=True,
        )
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'FACTURADA')

    def test_flujo_sano_completo_permite_cerrar_facturar_pagar(self):
        sesion = SesionContable.objects.create(mes=4, año=2027, estado='REVISION')
        self._crear_registro(sesion, self.estudio_con_grupo, monto=Decimal('5000.00'))

        self._login_admin()

        self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'CERRADA')

        self.client.post(
            reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}),
            data={'motivo': 'Facturacion de cierre mensual'},
        )
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'FACTURADA')

        self.client.post(
            reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}),
            data={'motivo': 'Pago acreditado'},
        )
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'PAGADA')

    def test_admin_actions_respetan_gate_que_bloquea_facturacion(self):
        from liquidacion.admin import SesionContableAdmin

        sesion = SesionContable.objects.create(mes=5, año=2027, estado='CERRADA')
        self._crear_registro(sesion, self.estudio_grupo_sin_tarifa, monto=Decimal('4000.00'))

        model_admin = SesionContableAdmin(SesionContable, AdminSite())
        model_admin.message_user = lambda *args, **kwargs: None
        request = RequestFactory().post('/admin/liquidacion/sesioncontable/')
        request.user = self.admin

        model_admin.marcar_facturada(request, SesionContable.objects.filter(pk=sesion.pk))
        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'CERRADA')


class SesionContableFinalStateLockTest(TestCase):
    """Bloqueos operativos en estados FACTURADA/PAGADA para prácticas y guardias."""

    def setUp(self):
        self.password = 'testpass123'
        self.medico = User.objects.create_user(
            username='medico_lock',
            password=self.password,
            rol='medico_staff',
            perfil_completo=True,
        )

        self.sesion_facturada = SesionContable.objects.create(mes=6, año=2026, estado='FACTURADA')
        self.sesion_pagada = SesionContable.objects.create(mes=7, año=2026, estado='PAGADA')

        self.registro_facturado = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            nombre_paciente='Paciente',
            apellido_paciente='Facturado',
            dni_paciente='12121212',
            fecha_del_informe=date(2026, 6, 10),
            sesion_contable=self.sesion_facturada,
            tipo_obra_social='COBER',
            horario='NA',
            monto_calculado=Decimal('1000.00'),
        )

        self.registro_pagado = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            nombre_paciente='Paciente',
            apellido_paciente='Pagado',
            dni_paciente='34343434',
            fecha_del_informe=date(2026, 7, 10),
            sesion_contable=self.sesion_pagada,
            tipo_obra_social='COBER',
            horario='NA',
            monto_calculado=Decimal('1000.00'),
        )

        self.guardia_facturada = GuardiaPasiva.objects.create(
            sesion_contable=self.sesion_facturada,
            medico=self.medico,
            fecha_guardia=date(2026, 6, 11),
            tipo_guardia='COBER',
            monto=Decimal('36500.00'),
        )

        self.guardia_pagada = GuardiaPasiva.objects.create(
            sesion_contable=self.sesion_pagada,
            medico=self.medico,
            fecha_guardia=date(2026, 7, 11),
            tipo_guardia='COBER',
            monto=Decimal('36500.00'),
        )

        self.client.force_login(self.medico)

    def test_delete_practica_bloqueado_en_facturada(self):
        response = self.client.post(
            reverse('liquidacion:registroestudios_delete', kwargs={'pk': self.registro_facturado.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            RegistroEstudiosPorMedico.objects.filter(pk=self.registro_facturado.pk).exists(),
            '❌ FALLA: se eliminó una práctica en FACTURADA.',
        )

    def test_delete_practica_bloqueado_en_pagada(self):
        response = self.client.post(
            reverse('liquidacion:registroestudios_delete', kwargs={'pk': self.registro_pagado.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            RegistroEstudiosPorMedico.objects.filter(pk=self.registro_pagado.pk).exists(),
            '❌ FALLA: se eliminó una práctica en PAGADA.',
        )

    def test_delete_guardia_bloqueado_en_facturada(self):
        response = self.client.post(
            reverse('liquidacion:eliminar_guardia_pasiva', kwargs={'pk': self.guardia_facturada.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            GuardiaPasiva.objects.filter(pk=self.guardia_facturada.pk).exists(),
            '❌ FALLA: se eliminó una guardia en FACTURADA.',
        )

    def test_delete_guardia_bloqueado_en_pagada(self):
        response = self.client.post(
            reverse('liquidacion:eliminar_guardia_pasiva', kwargs={'pk': self.guardia_pagada.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            GuardiaPasiva.objects.filter(pk=self.guardia_pagada.pk).exists(),
            '❌ FALLA: se eliminó una guardia en PAGADA.',
        )

    def test_update_guardia_bloqueado_en_facturada(self):
        response = self.client.post(
            reverse('liquidacion:editar_guardia_pasiva', kwargs={'pk': self.guardia_facturada.pk}),
            data={
                'fecha_guardia': '2026-06-11',
                'tipo_guardia': 'COBER',
                'observaciones': 'Intento de edición bloqueada',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.guardia_facturada.refresh_from_db()
        self.assertEqual(self.guardia_facturada.observaciones, '')


class SesionContableFase3TrazabilidadYExportTest(TestCase):
    """Fase 3: trazabilidad de transiciones y política de exportación."""

    def setUp(self):
        self.password = 'testpass123'
        self.admin = User.objects.create_user(
            username='admin_fase3',
            password=self.password,
            rol='administrativo',
            perfil_completo=True,
            is_staff=True,
        )
        self.medico = User.objects.create_user(
            username='medico_fase3',
            password=self.password,
            rol='medico_staff',
            perfil_completo=True,
        )

        self.grupo = GrupoTarifario.objects.create(
            codigo='ECO_FASE3',
            nombre='Ecografia fase 3',
            modalidad='ECO',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.grupo,
            vigencia_desde=date(2026, 1, 1),
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
        )
        self.estudio = Estudios.objects.create(
            nombre='ECO FASE 3',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
            grupo_tarifario=self.grupo,
            activo=True,
        )

    def _crear_sesion_con_datos(self, estado, mes):
        sesion = SesionContable.objects.create(mes=mes, año=2027, estado=estado)
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            nombre_paciente='Paciente',
            apellido_paciente='Fase3',
            dni_paciente=f'77{mes:02}1234',
            fecha_del_informe=date(2027, mes, 10),
            sesion_contable=sesion,
            tipo_obra_social='COBER',
            horario='NA',
            monto_calculado=Decimal('5000.00'),
        )
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.estudio,
            cantidad=1,
            contexto='SERVICIO',
        )
        return sesion

    def test_motivo_obligatorio_en_cerrada_a_facturada(self):
        sesion = self._crear_sesion_con_datos('CERRADA', 5)
        self.client.force_login(self.admin)

        self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))

        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'CERRADA')
        self.assertFalse(HistorialSesionContable.objects.filter(sesion_contable=sesion).exists())

    def test_historial_web_guarda_usuario_origen_y_motivo(self):
        sesion = self._crear_sesion_con_datos('CERRADA', 6)
        self.client.force_login(self.admin)

        self.client.post(
            reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}),
            data={'motivo': 'Facturacion mensual aprobada'},
        )

        sesion.refresh_from_db()
        self.assertEqual(sesion.estado, 'FACTURADA')

        historial = HistorialSesionContable.objects.get(sesion_contable=sesion)
        self.assertEqual(historial.estado_anterior, 'CERRADA')
        self.assertEqual(historial.estado_nuevo, 'FACTURADA')
        self.assertEqual(historial.usuario, self.admin)
        self.assertEqual(historial.origen, HistorialSesionContable.ORIGEN_WEB)
        self.assertEqual(historial.motivo, 'Facturacion mensual aprobada')

    def test_export_definitiva_bloqueada_en_cerrada(self):
        sesion = self._crear_sesion_con_datos('CERRADA', 7)
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:exportar_excel_liquidacion_definitiva'),
            data={'mes': sesion.mes, 'año': sesion.año},
        )

        self.assertEqual(response.status_code, 302)

    def test_export_definitiva_permitida_en_facturada(self):
        sesion = self._crear_sesion_con_datos('FACTURADA', 8)
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:exportar_excel_liquidacion_definitiva'),
            data={'mes': sesion.mes, 'año': sesion.año},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('DEFINITIVA', response['Content-Disposition'])

    def test_export_preliminar_permitida_en_cualquier_estado_para_admin(self):
        sesion = self._crear_sesion_con_datos('ABIERTA', 9)
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse('liquidacion:exportar_excel_liquidacion'),
            data={'mes': sesion.mes, 'año': sesion.año},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('PRELIMINAR', response['Content-Disposition'])

    def test_exportes_denegadas_para_medico(self):
        sesion = self._crear_sesion_con_datos('PAGADA', 10)
        self.client.force_login(self.medico)

        response_pre = self.client.get(
            reverse('liquidacion:exportar_excel_liquidacion'),
            data={'mes': sesion.mes, 'año': sesion.año},
        )
        response_def = self.client.get(
            reverse('liquidacion:exportar_excel_liquidacion_definitiva'),
            data={'mes': sesion.mes, 'año': sesion.año},
        )

        self.assertEqual(response_pre.status_code, 302)
        self.assertEqual(response_def.status_code, 302)

    def test_sesiones_list_muestra_motivo_requerido_en_cerrada_y_facturada(self):
        sesion_cerrada = self._crear_sesion_con_datos('CERRADA', 11)
        sesion_facturada = self._crear_sesion_con_datos('FACTURADA', 12)
        self.client.force_login(self.admin)

        response = self.client.get(reverse('liquidacion:sesiones_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="motivo_sesion_{sesion_cerrada.pk}"')
        self.assertContains(response, f'id="motivo_sesion_{sesion_facturada.pk}"')
        self.assertContains(response, 'name="motivo"', count=2)

    def test_sesiones_list_no_muestra_motivo_en_abierta_y_revision(self):
        sesion_abierta = self._crear_sesion_con_datos('ABIERTA', 1)
        sesion_revision = self._crear_sesion_con_datos('REVISION', 2)
        self.client.force_login(self.admin)

        response = self.client.get(reverse('liquidacion:sesiones_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'id="motivo_sesion_{sesion_abierta.pk}"')
        self.assertNotContains(response, f'id="motivo_sesion_{sesion_revision.pk}"')

    def test_sesiones_list_muestra_historial_si_existe(self):
        sesion = self._crear_sesion_con_datos('CERRADA', 3)
        HistorialSesionContable.objects.create(
            sesion_contable=sesion,
            estado_anterior='REVISION',
            estado_nuevo='CERRADA',
            usuario=self.admin,
            origen=HistorialSesionContable.ORIGEN_WEB,
            motivo='Cierre operativo',
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse('liquidacion:sesiones_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'REVISION → CERRADA')
        self.assertContains(response, 'Motivo: Cierre operativo')

    def test_sesiones_list_muestra_exportacion_preliminar(self):
        sesion = self._crear_sesion_con_datos('ABIERTA', 4)
        self.client.force_login(self.admin)

        response = self.client.get(reverse('liquidacion:sesiones_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '{}?mes={}&año={}'.format(
                reverse('liquidacion:exportar_excel_liquidacion'),
                sesion.mes,
                sesion.año,
            ),
            html=False,
        )
        self.assertContains(response, 'Exportar PRELIMINAR')

    def test_sesiones_list_exportacion_definitiva_habilitada_solo_facturada_pagada(self):
        sesion_abierta = self._crear_sesion_con_datos('ABIERTA', 5)
        sesion_facturada = self._crear_sesion_con_datos('FACTURADA', 6)
        self.client.force_login(self.admin)

        response = self.client.get(reverse('liquidacion:sesiones_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Definitiva habilitada solo en FACTURADA/PAGADA.')
        self.assertContains(
            response,
            '{}?mes={}&año={}'.format(
                reverse('liquidacion:exportar_excel_liquidacion_definitiva'),
                sesion_facturada.mes,
                sesion_facturada.año,
            ),
            html=False,
        )
        self.assertNotContains(
            response,
            '{}?mes={}&año={}'.format(
                reverse('liquidacion:exportar_excel_liquidacion_definitiva'),
                sesion_abierta.mes,
                sesion_abierta.año,
            ),
            html=False,
        )

    def test_sesiones_list_restringida_para_medico_residente(self):
        self._crear_sesion_con_datos('ABIERTA', 7)
        medico_residente = User.objects.create_user(
            username='residente_fase3',
            password=self.password,
            rol='medico_residente',
            perfil_completo=True,
        )
        self.client.force_login(medico_residente)

        response = self.client.get(reverse('liquidacion:sesiones_list'))

        self.assertEqual(response.status_code, 302)

    def test_sesiones_list_incluye_resumen_auditoria_residentes_eco_para_admin(self):
        sesion = self._crear_sesion_con_datos('ABIERTA', 8)
        residente = User.objects.create_user(
            username='residente_auditoria_sesion',
            password=self.password,
            rol='medico_residente',
            perfil_completo=True,
        )
        estudio_eco = Estudios.objects.create(
            nombre='ECO Auditoria Sesion',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
            activo=True,
        )
        for i in range(35):
            registro = RegistroEstudiosPorMedico.objects.create(
                medico=residente,
                nombre_paciente='Audit',
                apellido_paciente='Sesion',
                dni_paciente=f"77{i:06d}"[:8],
                fecha_del_informe=date(2026, 8, 12),
                fecha_registro=timezone.make_aware(datetime(2026, 8, 12, 17, i % 59)),
                sesion_contable=sesion,
                tipo_obra_social='COBER',
                horario='EXTRA',
                monto_calculado=Decimal('5000.00'),
                cantidad_regiones=1,
            )
            RegistroEstudio.objects.create(
                registro=registro,
                estudio=estudio_eco,
                cantidad=1,
                contexto='SERVICIO',
            )

        self.client.force_login(self.admin)
        response = self.client.get(reverse('liquidacion:sesiones_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Auditoría residentes ECO')
        self.assertContains(response, 'Detalle próximamente.')


class NavegacionLiquidacionResidentesTest(TestCase):
    """Valida acceso visible a Registrar estudios para perfiles de residencia."""

    def setUp(self):
        self.password = 'testpass123'
        self.request_factory = RequestFactory()
        self.registro_url = reverse('liquidacion:registroestudios_nuevo')

        self.medico_residente = User.objects.create_user(
            username='residente_nav',
            password=self.password,
            rol='medico_residente',
            perfil_completo=True,
        )
        self.jefe_residentes = User.objects.create_user(
            username='jefe_nav',
            password=self.password,
            rol='jefe_residentes',
            perfil_completo=True,
        )
        self.instructor_residentes = User.objects.create_user(
            username='instructor_nav',
            password=self.password,
            rol='instructor_residentes',
            perfil_completo=True,
        )

    def _labels_nav(self, user):
        request = self.request_factory.get(reverse('home'))
        request.user = user
        grupos = navbar_links(request)['nav_groups']
        return [item['label'] for grupo in grupos for item in grupo['items']]

    def test_navbar_medico_residente_incluye_registrar_estudios(self):
        labels = self._labels_nav(self.medico_residente)
        self.assertIn('Registrar Estudios', labels)

    def test_navbar_residencia_no_pierde_registrar_estudios_jefe_e_instructor(self):
        labels_jefe = self._labels_nav(self.jefe_residentes)
        labels_instructor = self._labels_nav(self.instructor_residentes)

        self.assertIn('Registrar Estudios', labels_jefe)
        self.assertIn('Registrar Estudios', labels_instructor)

    def test_home_medico_residente_muestra_cta_registrar_estudios(self):
        self.client.force_login(self.medico_residente)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registrar estudios')
        self.assertContains(response, 'Carga los estudios informados del dia.')
        self.assertContains(response, f'href="{self.registro_url}"', html=False)

    def test_link_registrar_estudios_apunta_a_url_correcta_para_roles_residencia(self):
        for user in [self.medico_residente, self.jefe_residentes, self.instructor_residentes]:
            self.client.force_login(user)
            response = self.client.get(reverse('home'))

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f'href="{self.registro_url}"', html=False)
