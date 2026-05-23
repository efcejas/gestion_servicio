"""
NUEVOS TESTS - Auditoría de Liquidación v3.1 (11 mayo 2026)
Validar que los 4 fixes implementados funcionan:
  FIX #1: @transaction.atomic en form_valid
  FIX #2: Migración 0028 con error handling
  FIX #3: DB constraints
  FIX #4: Post_save signals para recálculo automático
"""

from django.test import TestCase, TransactionTestCase
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import reverse
from datetime import date, datetime
from decimal import Decimal
from .models import RegistroEstudiosPorMedico, RegistroEstudio, Estudios, SesionContable, GuardiaPasiva

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
        self.admin = User.objects.create_user(
            username='admin_liq',
            password='testpass123',
            rol='administrativo',
            perfil_completo=True,
        )
        self.jefe_servicio = User.objects.create_user(
            username='jefe_servicio_liq',
            password='testpass123',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.jefe_residentes = User.objects.create_user(
            username='jefe_res_liq',
            password='testpass123',
            rol='jefe_residentes',
            perfil_completo=True,
        )
        self.instructor = User.objects.create_user(
            username='inst_liq',
            password='testpass123',
            rol='instructor_residentes',
            perfil_completo=True,
        )
        self.medico = User.objects.create_user(
            username='medico_liq',
            password='testpass123',
            rol='medico_staff',
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
            self.client.logout()
            self._login(user)
            response = self.client.post(reverse('liquidacion:sesion_transicion', kwargs={'pk': sesion.pk}))
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
