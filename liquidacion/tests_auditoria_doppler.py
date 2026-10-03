from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from .models import (
    Estudios,
    GrupoTarifario,
    HistorialRevisionAuditoriaDopplerMMII,
    RegistroEstudio,
    RegistroEstudiosPorMedico,
    RevisionAuditoriaDopplerMMII,
    SesionContable,
)
from .services_auditoria import (
    auditar_cantidad_doppler_mmii,
    crear_casos_auditoria_doppler_mmii,
    resolver_caso_auditoria_doppler_mmii,
)


User = get_user_model()


class AuditoriaCantidadDopplerMMIITest(TestCase):
    def setUp(self):
        self.medico = User.objects.create_user(
            username='jefe_doppler_auditoria',
            first_name='Angel',
            last_name='Gavilanes Ibarra',
            rol='jefe_residentes',
            perfil_completo=True,
        )
        self.sesion = SesionContable.objects.create(
            mes=6,
            año=2026,
            estado='CERRADA',
        )
        self.grupo = GrupoTarifario.objects.create(
            codigo='DOP_MMII_AUDIT',
            nombre='Doppler MMII auditoria',
            modalidad='DOP',
            activo=True,
        )
        self.arterial = Estudios.objects.create(
            codigo='900046/0',
            nombre='Ecodoppler arterial MM inferiores',
            tipo='DOP',
            grupo_tarifario=self.grupo,
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('24200.00'),
            precio_otras_os=Decimal('24200.00'),
            activo=True,
        )
        self.venoso = Estudios.objects.create(
            codigo='DOP-VEN-MMII',
            nombre='Doppler venoso de miembros inferiores',
            tipo='DOP',
            grupo_tarifario=self.grupo,
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('24200.00'),
            precio_otras_os=Decimal('24200.00'),
            activo=True,
        )

    def _crear_registro(self, *, rol='jefe_residentes'):
        if rol != self.medico.rol:
            self.medico.rol = rol
            self.medico.save(update_fields=['rol'])
        return RegistroEstudiosPorMedico.objects.create(
            sesion_contable=self.sesion,
            medico=self.medico,
            nombre_paciente='Claudia Vanesa',
            apellido_paciente='Sanchez Barrios',
            dni_paciente='95951354',
            fecha_del_informe=date(2026, 6, 10),
            tipo_obra_social='COBER',
            horario='EXTRA',
            cantidad_regiones=4,
            monto_calculado=Decimal('48400.00'),
        )

    def test_normaliza_arterial_y_venoso_sin_modificar_datos_originales(self):
        registro = self._crear_registro()
        relacion_arterial = RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.arterial,
            cantidad=2,
            contexto='SERVICIO',
        )
        relacion_venoso = RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.venoso,
            cantidad=2,
            contexto='SERVICIO',
        )
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(
            cantidad_regiones=4,
            monto_calculado=Decimal('48400.00'),
        )

        resultado = auditar_cantidad_doppler_mmii(
            fecha_desde=date(2026, 6, 1),
            fecha_hasta=date(2026, 9, 30),
        )

        fila = resultado['resultados'][0]
        self.assertEqual(fila['cantidad_regiones_declarada'], 4)
        self.assertEqual(fila['cantidad_regiones_esperada'], 2)
        self.assertEqual(fila['monto_registrado'], Decimal('48400.00'))
        self.assertEqual(fila['diferencia_cantidad'], 2)
        self.assertEqual(
            [item['cantidad_esperada'] for item in fila['estudios']],
            [1, 1],
        )
        self.assertEqual(
            [item['registro_estudio_id'] for item in fila['estudios']],
            [relacion_arterial.pk, relacion_venoso.pk],
        )
        self.assertEqual(fila['tratamiento_economico'], 'IMPACTO_POTENCIAL_NO_APLICADO')

        relacion_arterial.refresh_from_db()
        relacion_venoso.refresh_from_db()
        registro.refresh_from_db()
        self.assertEqual(relacion_arterial.cantidad, 2)
        self.assertEqual(relacion_venoso.cantidad, 2)
        self.assertEqual(registro.cantidad_regiones, 4)
        self.assertEqual(registro.monto_calculado, Decimal('48400.00'))

    def test_residente_solo_recibe_informe_sin_propuesta_de_debito(self):
        registro = self._crear_registro(rol='medico_residente')
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.arterial,
            cantidad=2,
            contexto='SERVICIO',
        )
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(cantidad_regiones=2)

        resultado = auditar_cantidad_doppler_mmii(
            fecha_desde=date(2026, 6, 1),
            fecha_hasta=date(2026, 9, 30),
        )

        self.assertEqual(
            resultado['resultados'][0]['tratamiento_economico'],
            'INFORMATIVO_SIN_DEBITO',
        )

    def test_no_clasifica_doppler_sin_referencia_a_mmii(self):
        registro = self._crear_registro()
        estudio_carotideo = Estudios.objects.create(
            codigo='DOP-CAROTIDEO',
            nombre='Doppler arterial carotideo',
            tipo='DOP',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=estudio_carotideo,
            cantidad=2,
        )

        resultado = auditar_cantidad_doppler_mmii(
            fecha_desde=date(2026, 6, 1),
            fecha_hasta=date(2026, 9, 30),
        )

        self.assertEqual(resultado['total_registros'], 0)

    def test_un_estudio_combinado_arterial_y_venoso_equivale_a_dos_practicas(self):
        registro = self._crear_registro()
        estudio_combinado = Estudios.objects.create(
            codigo='DOP-ART-VEN-MMII',
            nombre='Ecodoppler arterial y venoso MMII',
            tipo='DOP',
            grupo_tarifario=self.grupo,
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('48400.00'),
            precio_otras_os=Decimal('48400.00'),
            activo=True,
        )
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=estudio_combinado,
            cantidad=1,
        )

        resultado = auditar_cantidad_doppler_mmii(
            fecha_desde=date(2026, 6, 1),
            fecha_hasta=date(2026, 9, 30),
        )

        estudio_auditado = resultado['resultados'][0]['estudios'][0]
        self.assertEqual(estudio_auditado['clasificacion'], 'ARTERIAL_Y_VENOSO_MMII')
        self.assertEqual(estudio_auditado['cantidad_esperada'], 2)

    def test_marca_posible_duplicado_sin_fusionar_registros(self):
        primer_registro = self._crear_registro()
        RegistroEstudio.objects.create(
            registro=primer_registro,
            estudio=self.arterial,
            cantidad=1,
        )
        segundo_registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=self.sesion,
            medico=self.medico,
            nombre_paciente='Claudia Vanesa',
            apellido_paciente='Sanchez Barrios',
            dni_paciente='95.951.354',
            fecha_del_informe=primer_registro.fecha_del_informe,
            tipo_obra_social='COBER',
            horario='EXTRA',
            cantidad_regiones=1,
            monto_calculado=Decimal('24200.00'),
        )
        RegistroEstudio.objects.create(
            registro=segundo_registro,
            estudio=self.arterial,
            cantidad=1,
        )

        resultado = auditar_cantidad_doppler_mmii(
            fecha_desde=date(2026, 6, 1),
            fecha_hasta=date(2026, 9, 30),
        )

        self.assertEqual(resultado['grupos_posible_duplicado'], 1)
        self.assertEqual(len(resultado['resultados']), 2)
        for registro in resultado['resultados']:
            estudio = registro['estudios'][0]
            self.assertTrue(estudio['posible_duplicado'])
            self.assertEqual(estudio['cantidad_en_grupo_duplicado'], 2)
        self.assertEqual(RegistroEstudiosPorMedico.objects.count(), 2)
        self.assertEqual(RegistroEstudio.objects.count(), 2)

    def test_no_marca_art_and_venous_as_duplicate_together(self):
        registro_arterial = self._crear_registro()
        RegistroEstudio.objects.create(
            registro=registro_arterial,
            estudio=self.arterial,
            cantidad=1,
        )
        registro_venoso = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=self.sesion,
            medico=self.medico,
            nombre_paciente='Claudia Vanesa',
            apellido_paciente='Sanchez Barrios',
            dni_paciente='95951354',
            fecha_del_informe=registro_arterial.fecha_del_informe,
            tipo_obra_social='COBER',
            horario='EXTRA',
            cantidad_regiones=1,
            monto_calculado=Decimal('24200.00'),
        )
        RegistroEstudio.objects.create(
            registro=registro_venoso,
            estudio=self.venoso,
            cantidad=1,
        )

        resultado = auditar_cantidad_doppler_mmii(
            fecha_desde=date(2026, 6, 1),
            fecha_hasta=date(2026, 9, 30),
        )

        self.assertEqual(resultado['grupos_posible_duplicado'], 0)
        self.assertFalse(any(
            estudio.get('posible_duplicado')
            for registro in resultado['resultados']
            for estudio in registro['estudios']
        ))

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_pantalla_solo_lectura_permite_jefatura_y_no_residentes(self):
        registro = self._crear_registro()
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.arterial,
            cantidad=2,
            contexto='SERVICIO',
        )
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(
            cantidad_regiones=2,
            monto_calculado=Decimal('48400.00'),
        )
        url = reverse('liquidacion:auditoria_doppler_mmii')

        self.client.force_login(self.medico)
        response_residente = self.client.get(url)
        self.assertNotEqual(response_residente.status_code, 200)

        jefe = User.objects.create_user(
            username='jefatura_auditoria_doppler',
            first_name='Jefe',
            last_name='Servicio',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.client.force_login(jefe)
        response_jefatura = self.client.get(url)

        self.assertEqual(response_jefatura.status_code, 200)
        self.assertContains(response_jefatura, 'Revisión sin ajustes económicos')
        self.assertContains(response_jefatura, 'Cantidad declarada')
        self.assertContains(response_jefatura, 'Impacto potencial')
        self.assertContains(response_jefatura, self.medico.get_full_name())

        response_filtrada = self.client.get(
            url,
            {'profesional': self.medico.pk},
        )
        self.assertEqual(response_filtrada.status_code, 200)
        self.assertContains(response_filtrada, 'Registros candidatos:')
        self.assertContains(response_filtrada, 'Ecodoppler arterial MM inferiores')

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_pantalla_muestra_posible_duplicado_y_referencias(self):
        primero = self._crear_registro()
        RegistroEstudio.objects.create(registro=primero, estudio=self.arterial, cantidad=1)
        segundo = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=self.sesion,
            medico=self.medico,
            nombre_paciente=primero.nombre_paciente,
            apellido_paciente=primero.apellido_paciente,
            dni_paciente=primero.dni_paciente,
            fecha_del_informe=primero.fecha_del_informe,
            tipo_obra_social='COBER',
            horario='EXTRA',
            cantidad_regiones=1,
            monto_calculado=Decimal('24200.00'),
        )
        RegistroEstudio.objects.create(registro=segundo, estudio=self.arterial, cantidad=1)
        jefe = User.objects.create_user(
            username='jefatura_auditoria_duplicados',
            first_name='Jefe',
            last_name='Servicio',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.client.force_login(jefe)

        response = self.client.get(reverse('liquidacion:auditoria_doppler_mmii'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Posible duplicado')
        self.assertContains(response, f'#{primero.pk}')
        self.assertContains(response, f'#{segundo.pk}')

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_pantalla_agrupa_art_y_venoso_en_un_registro_con_totales_separados(self):
        registro = self._crear_registro()
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.arterial,
            cantidad=2,
            contexto='SERVICIO',
        )
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.venoso,
            cantidad=2,
            contexto='SERVICIO',
        )
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(
            cantidad_regiones=4,
            monto_calculado=Decimal('48400.00'),
        )
        jefe = User.objects.create_user(
            username='jefatura_auditoria_doppler_agrupada',
            first_name='Jefe',
            last_name='Servicio',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.client.force_login(jefe)

        response = self.client.get(reverse('liquidacion:auditoria_doppler_mmii'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Registro #{registro.pk}', count=1)
        self.assertContains(response, '4 declaradas')
        self.assertContains(response, '2 según regla')
        self.assertContains(response, '4 → 2')
        self.assertContains(response, 'Ecodoppler arterial MM inferiores')
        self.assertContains(response, 'Doppler venoso de miembros inferiores')
        self.assertContains(response, 'Cantidad declarada: <strong>2</strong>', count=2)

    def test_persistencia_es_idempotente_y_no_modifica_fuentes_economicas(self):
        registro = self._crear_registro()
        relacion = RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.arterial,
            cantidad=2,
            contexto='SERVICIO',
        )
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(
            cantidad_regiones=4,
            monto_calculado=Decimal('48400.00'),
        )
        auditoria = auditar_cantidad_doppler_mmii(
            fecha_desde=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
        )

        primera_generacion = crear_casos_auditoria_doppler_mmii(auditoria, self.medico)
        segunda_generacion = crear_casos_auditoria_doppler_mmii(auditoria, self.medico)

        self.assertEqual(primera_generacion, {'detectados': 1, 'creados': 1, 'existentes': 0})
        self.assertEqual(segunda_generacion, {'detectados': 1, 'creados': 0, 'existentes': 1})
        self.assertEqual(RevisionAuditoriaDopplerMMII.objects.count(), 1)
        caso = RevisionAuditoriaDopplerMMII.objects.get()
        self.assertEqual(caso.datos_originales_json['cantidad_declarada'], 2)
        self.assertEqual(caso.datos_originales_json['cantidad_esperada'], 1)
        self.assertEqual(caso.datos_originales_json['monto_registrado'], '48400.00')

        registro.refresh_from_db()
        relacion.refresh_from_db()
        self.assertEqual(registro.cantidad_regiones, 4)
        self.assertEqual(registro.monto_calculado, Decimal('48400.00'))
        self.assertEqual(relacion.cantidad, 2)

    def test_confirmacion_exige_evidencia_y_cada_decision_agrega_historial(self):
        registro = self._crear_registro()
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.arterial,
            cantidad=2,
            contexto='SERVICIO',
        )
        auditoria = auditar_cantidad_doppler_mmii(
            fecha_desde=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
        )
        crear_casos_auditoria_doppler_mmii(auditoria, self.medico)
        caso = RevisionAuditoriaDopplerMMII.objects.get()

        with self.assertRaises(ValidationError):
            resolver_caso_auditoria_doppler_mmii(
                caso_id=caso.pk,
                decision=RevisionAuditoriaDopplerMMII.ESTADO_CONFIRMADO,
                evidencias={},
                observacion='Sin evidencia documental',
                usuario=self.medico,
            )

        resolver_caso_auditoria_doppler_mmii(
            caso_id=caso.pk,
            decision=RevisionAuditoriaDopplerMMII.ESTADO_CONFIRMADO,
            evidencias={'orden_medica_verificada': True},
            observacion='Orden médica revisada',
            usuario=self.medico,
        )
        resolver_caso_auditoria_doppler_mmii(
            caso_id=caso.pk,
            decision=RevisionAuditoriaDopplerMMII.ESTADO_DESCARTADO,
            evidencias={'eges_verificado': True},
            observacion='Se descarta tras revisión complementaria',
            usuario=self.medico,
        )

        caso.refresh_from_db()
        self.assertEqual(caso.estado, RevisionAuditoriaDopplerMMII.ESTADO_DESCARTADO)
        self.assertEqual(caso.observacion, 'Se descarta tras revisión complementaria')
        self.assertEqual(HistorialRevisionAuditoriaDopplerMMII.objects.count(), 2)
        self.assertEqual(
            list(caso.historial.order_by('pk').values_list('estado_anterior', 'estado_nuevo')),
            [
                (RevisionAuditoriaDopplerMMII.ESTADO_PENDIENTE, RevisionAuditoriaDopplerMMII.ESTADO_CONFIRMADO),
                (RevisionAuditoriaDopplerMMII.ESTADO_CONFIRMADO, RevisionAuditoriaDopplerMMII.ESTADO_DESCARTADO),
            ],
        )
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, Decimal('48400.00'))

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_endpoints_persisten_casos_y_restringen_acceso_a_jefatura(self):
        registro = self._crear_registro()
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=self.arterial,
            cantidad=2,
            contexto='SERVICIO',
        )
        generar_url = reverse('liquidacion:auditoria_doppler_mmii_generar_casos')
        datos = {
            'fecha_desde': '2026-06-01',
            'fecha_hasta': '2026-06-30',
            'profesional': '',
            'solo_diferencias': '1',
        }

        self.client.force_login(self.medico)
        respuesta_no_autorizada = self.client.post(generar_url, datos)
        self.assertEqual(respuesta_no_autorizada.status_code, 302)
        self.assertEqual(RevisionAuditoriaDopplerMMII.objects.count(), 0)

        jefe = User.objects.create_user(
            username='jefatura_generacion_doppler',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.client.force_login(jefe)
        respuesta_fecha_invalida = self.client.post(generar_url, {
            **datos,
            'fecha_desde': '2026-02-31',
        })
        self.assertEqual(respuesta_fecha_invalida.status_code, 302)
        self.assertEqual(RevisionAuditoriaDopplerMMII.objects.count(), 0)
        respuesta = self.client.post(generar_url, datos)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(RevisionAuditoriaDopplerMMII.objects.count(), 1)

        caso = RevisionAuditoriaDopplerMMII.objects.get()
        resolver_url = reverse(
            'liquidacion:auditoria_doppler_mmii_resolver',
            args=[caso.pk],
        )
        self.client.force_login(self.medico)
        self.client.post(resolver_url, {
            **datos,
            'decision': RevisionAuditoriaDopplerMMII.ESTADO_DESCARTADO,
            'observacion': 'Intento sin permisos',
        })
        self.assertEqual(HistorialRevisionAuditoriaDopplerMMII.objects.count(), 0)
        self.client.force_login(jefe)
        self.client.post(resolver_url, {
            **datos,
            'decision': RevisionAuditoriaDopplerMMII.ESTADO_CONFIRMADO,
            'eges_verificado': 'on',
            'observacion': 'EGES solo no confirma',
        })
        self.assertEqual(HistorialRevisionAuditoriaDopplerMMII.objects.count(), 0)
        respuesta_revision = self.client.post(resolver_url, {
            **datos,
            'decision': RevisionAuditoriaDopplerMMII.ESTADO_CONFIRMADO,
            'orden_medica_verificada': 'on',
            'observacion': 'Orden verificada en prueba',
        })
        self.assertEqual(respuesta_revision.status_code, 302)
        self.assertEqual(HistorialRevisionAuditoriaDopplerMMII.objects.count(), 1)

    @override_settings(SECURE_SSL_REDIRECT=False)
    def test_mis_registros_solo_muestra_auditorias_del_profesional_autenticado(self):
        registro_propio = self._crear_registro()
        relacion_propia = RegistroEstudio.objects.create(
            registro=registro_propio,
            estudio=self.arterial,
            cantidad=2,
            contexto='SERVICIO',
        )
        otro_medico = User.objects.create_user(
            username='otro_medico_auditoria',
            rol='jefe_residentes',
        )
        otro_registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=self.sesion,
            medico=otro_medico,
            nombre_paciente='Paciente',
            apellido_paciente='Reservado',
            dni_paciente='12345678',
            fecha_del_informe=date(2026, 6, 11),
            tipo_obra_social='COBER',
            horario='EXTRA',
            cantidad_regiones=2,
            monto_calculado=Decimal('24200.00'),
        )
        relacion_ajena = RegistroEstudio.objects.create(
            registro=otro_registro,
            estudio=self.arterial,
            cantidad=2,
            contexto='SERVICIO',
        )
        auditoria = auditar_cantidad_doppler_mmii(
            fecha_desde=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
        )
        crear_casos_auditoria_doppler_mmii(auditoria, self.medico)
        casos = {
            caso.registro_estudio_id_origen: caso
            for caso in RevisionAuditoriaDopplerMMII.objects.all()
        }
        resolver_caso_auditoria_doppler_mmii(
            caso_id=casos[relacion_propia.pk].pk,
            decision=RevisionAuditoriaDopplerMMII.ESTADO_DESCARTADO,
            evidencias={},
            observacion='OBSERVACION_PROPIA_UNICA',
            usuario=self.medico,
        )
        resolver_caso_auditoria_doppler_mmii(
            caso_id=casos[relacion_ajena.pk].pk,
            decision=RevisionAuditoriaDopplerMMII.ESTADO_DESCARTADO,
            evidencias={},
            observacion='OBSERVACION_AJENA_NO_VISIBLE',
            usuario=self.medico,
        )

        self.client.force_login(self.medico)
        response = self.client.get(
            reverse('liquidacion:registroestudios_list'),
            {'mes': 6, 'año': 2026},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OBSERVACION_PROPIA_UNICA')
        self.assertNotContains(response, 'OBSERVACION_AJENA_NO_VISIBLE')
        self.assertNotContains(response, 'Paciente Reservado')
