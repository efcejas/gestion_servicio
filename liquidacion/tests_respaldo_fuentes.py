from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from eges_import.tests_produccion import FuentesSinteticasMixin
from .models import (Estudios, RegistroEstudio, RegistroEstudiosPorMedico, SesionContable,
                     ResultadoControlEgesRegistro, RevisionCruceEgesRegistro)
from .services_respaldo_fuentes import construir_preview_respaldo_fuentes


class RespaldoFuentesTest(FuentesSinteticasMixin, TestCase):
    # Se reutilizan factories sinteticas, no archivos reales ni bases clinicas.
    def setUp(self):
        super().setUp()
        self.medico = get_user_model().objects.create_user(username='medico_respaldo', first_name='Carlos',
                                                          last_name='Puente', rol='medico_residente', perfil_completo=True)
        self.sesion = SesionContable.objects.create(mes=10, año=2026, estado='REVISION')
        self.estudio = Estudios.objects.create(nombre='ECOGRAFIA COMPLETA DE ABDOMEN', codigo='180112',
                                               tipo='ECO', conteo_regiones=1, precio_cober=Decimal('1000'), precio_otras_os=Decimal('1000'))

    def registro(self, estudio=None, medico=None, cantidad=1, documento='12345678'):
        registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=self.sesion, medico=medico or self.medico, nombre_paciente='SINTETICO', apellido_paciente='QA',
            dni_paciente=documento, fecha_del_informe=date(2026, 10, 10), horario='EXTRA', monto_calculado=Decimal('1234.56'),
        )
        RegistroEstudio.objects.create(registro=registro, estudio=estudio or self.estudio, cantidad=cantidad)
        return registro

    def respaldo(self, **filtros):
        return construir_preview_respaldo_fuentes(sesion=self.sesion, batch_eges_ids=[self.batch.pk],
                                                  lote_netterm_ids=[self.lote.pk], filtros=filtros)

    def test_faltante_eges_tiene_respaldo_netterm_sin_certificar_cantidad_o_monto(self):
        registro = self.registro(cantidad=3)
        # Simula un monto historico ya fijado; crear la relacion dispara el
        # calculo normal del modelo, que no forma parte del servicio de respaldo.
        RegistroEstudiosPorMedico.objects.filter(pk=registro.pk).update(monto_calculado=Decimal('1234.56'))
        self.netterm(estado='PENDIENTE')
        antes = (list(RegistroEstudiosPorMedico.objects.values()), list(RegistroEstudio.objects.values()))
        with CaptureQueriesContext(connection) as consultas:
            resultado = self.respaldo()
        linea = resultado['resultados'][0]['lineas'][0]
        self.assertEqual(resultado['resultados'][0]['estado_respaldo'], 'OK_RESPALDO')
        self.assertEqual(linea['estado'], 'OK_NETTERM')
        self.assertEqual(linea['cantidad_declarada'], 3)
        self.assertFalse(linea['cantidad_economica_validada'])
        self.assertFalse(linea['horario_economico_validado'])
        self.assertEqual(antes, (list(RegistroEstudiosPorMedico.objects.values()), list(RegistroEstudio.objects.values())))
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for q in consultas))
        self.assertFalse(ResultadoControlEgesRegistro.objects.exists())
        self.assertFalse(RevisionCruceEgesRegistro.objects.exists())
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, Decimal('1234.56'))

    def test_eges_tiene_prioridad_y_otro_informante_netterm_no_lo_quita(self):
        self.registro()
        self.eges(estado_turno='Fin Practica')
        self.netterm(informante='OTRO PROFESIONAL')
        linea = self.respaldo()['resultados'][0]['lineas'][0]
        self.assertEqual(linea['estado'], 'OK_EGES')
        self.assertTrue(linea['reafirmado_netterm'])
        self.assertTrue(any('conserva el respaldo EGES' in m for m in linea['motivos']))

    def test_tomografia_sin_eges_puede_respaldarse_con_netterm(self):
        estudio = Estudios.objects.create(nombre='TOMOGRAFIA DE TORAX', codigo='340101', tipo='TOM', conteo_regiones=1)
        self.registro(estudio)
        self.netterm(codigo='340101', practica='TOMOGRAFIA DE TORAX', estado='NO_DEFINITIVO')
        self.assertEqual(self.respaldo()['resultados'][0]['lineas'][0]['estado'], 'OK_NETTERM')

    def test_informante_netterm_distinto_sin_eges_queda_para_revisar(self):
        self.registro()
        self.netterm(informante='OTRO PROFESIONAL')
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'REVISAR')

    def test_dos_pedidos_no_se_resuelven_por_primera_fila(self):
        self.registro()
        self.netterm()
        self.netterm(pedido='2')
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'REVISAR')

    def test_filtrar_profesional_no_permite_reusar_una_evidencia(self):
        self.registro()
        otro = get_user_model().objects.create_user(username='otro', first_name='Otro', last_name='Profesional')
        self.registro(medico=otro)
        self.netterm()
        resultado = self.respaldo(profesional=self.medico.pk)
        self.assertEqual(resultado['total'], 1)
        self.assertEqual(resultado['resultados'][0]['estado_respaldo'], 'REVISAR')
        self.assertTrue(any('más de una línea' in m for m in resultado['resultados'][0]['lineas'][0]['motivos']))

    def test_eges_cancelado_no_se_elude_con_netterm(self):
        self.registro()
        self.eges(estado_turno='Cancelado')
        self.netterm()
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'REVISAR')

    def test_netterm_puede_confirmar_realizacion_de_eges_recepcionado(self):
        self.registro()
        self.eges(estado_turno='Recepcionado')
        self.netterm()
        self.assertEqual(self.respaldo()['resultados'][0]['lineas'][0]['estado'], 'OK_NETTERM')

    def test_codigo_diferente_no_se_tapa_con_nombre_igual(self):
        self.registro()
        self.netterm(codigo='999')
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'SIN_RESPALDO')

    def test_nombre_exacto_o_alias_explicitado_sirve_si_no_hay_codigo_numerico(self):
        self.estudio.codigo = None
        self.estudio.nombre = 'ECO ABDOMINAL'
        self.estudio.save()
        self.registro()
        self.netterm()
        linea = self.respaldo()['resultados'][0]['lineas'][0]
        self.assertEqual(linea['estado'], 'OK_NETTERM')
        self.assertEqual(linea['evidencia'][0]['metodo'], 'NOMBRE_EQUIVALENTE')

    def test_pendiente_realizacion_no_da_ok(self):
        self.registro()
        self.netterm(estado='PENDIENTE', realizada=False)
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'REVISAR')

    def test_varias_practicas_combinan_fuentes_y_muestran_respaldo_parcial(self):
        registro = self.registro()
        renal = Estudios.objects.create(nombre='ECOGRAFIA RENAL', codigo='180113', tipo='ECO', conteo_regiones=1)
        RegistroEstudio.objects.create(registro=registro, estudio=renal, cantidad=1)
        self.eges()
        self.assertEqual(self.respaldo()['resultados'][0]['estado_respaldo'], 'PARCIAL')
        self.netterm(codigo='180113', practica='ECOGRAFIA RENAL')
        resultado = self.respaldo()['resultados'][0]
        self.assertEqual(resultado['estado_respaldo'], 'OK_RESPALDO')
        self.assertCountEqual([l['estado'] for l in resultado['lineas']], ['OK_EGES', 'OK_NETTERM'])

    @override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_vista_restringida_renderiza_respaldo_y_no_admite_escrituras(self):
        registro = self.registro()
        self.netterm()
        url = reverse('liquidacion:respaldo_fuentes_preview', kwargs={'pk': self.sesion.pk})
        self.client.force_login(self.medico)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.usuario)
        with CaptureQueriesContext(connection) as consultas:
            response = self.client.get(url, {'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OK de respaldo Netterm')
        self.assertContains(response, 'no modifica montos')
        self.assertEqual(response.context['pagina'][0]['registro'].pk, registro.pk)
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for q in consultas))
        self.assertEqual(self.client.post(url).status_code, 405)
