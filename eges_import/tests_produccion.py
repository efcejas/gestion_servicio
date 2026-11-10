import hashlib
from datetime import date, time

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import EgesRow, ImportBatch, NettermFila, NettermLote
from .services_produccion import construir_preview_produccion
from .services_conciliacion import construir_preview_conteo_consolidado


class FuentesSinteticasMixin:
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(username='produccion_admin', is_superuser=True, perfil_completo=True)
        self.batch = ImportBatch.objects.create(usuario=self.usuario, archivo_nombre='eges_sintetico.xls')
        self.lote = NettermLote.objects.create(archivo_nombre='netterm_sintetico.xlsx', archivo_sha256='a'*64,
                                             importado_por=self.usuario, version_parser='QA', motivo='Prueba sintetica')

    def eges(self, **cambios):
        datos = dict(batch=self.batch, dni_paciente='12345678', fecha_turno=date(2026, 10, 10),
                     hora_turno=time(10), practica='ECOGRAFIA COMPLETA DE ABDOMEN', codigo_practica='180112',
                     estado_turno='Informado', medico_informante='PUENTE CARLOS')
        return EgesRow.objects.create(**{**datos, **cambios})

    def netterm(self, pedido='1', codigo='180112', practica='ECOGRAFIA COMPLETA DE ABDOMEN',
                estado='DEFINITIVO', realizada=True, documento='12345678', informante='PUENTE CARLOS',
                pendiente_realizar=False):
        clave = hashlib.sha256(f'{pedido}:1:{codigo}'.encode()).hexdigest()
        normales = dict(pedido=pedido, documento=documento, tipo_documento='D.N.I.', practica=practica,
                        codigo_nomenclador=codigo, tipo_nomenclador='1', informante=informante,
                        servicio='', modalidad='ECO_GENERAL',
                        estado_realizacion='PENDIENTE' if pendiente_realizar else 'CON_FECHA' if realizada else 'DESCONOCIDO')
        return NettermFila.objects.create(
            lote=self.lote, hoja='QA', numero_fila=NettermFila.objects.count()+2,
            clave_candidata_sha256=clave, contenido_sha256=hashlib.sha256(str(normales).encode()).hexdigest(),
            originales_json=[], normalizados_json=normales, fecha_pedido=date(2026, 10, 10),
            fecha_realizacion=date(2026, 10, 11) if realizada else None,
            estado_informe=estado, anulado=estado == 'ANULADO', modalidad='ECO_GENERAL',
        )


class ProduccionFuentesTest(FuentesSinteticasMixin, TestCase):
    def produccion(self):
        return construir_preview_produccion(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk])

    def test_produccion_no_exige_informe_y_no_suma_cantidades(self):
        self.eges(estado_turno='Fin Practica', cantidad=3)
        self.netterm(estado='PENDIENTE')
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 1)
        self.assertEqual(resultado['base_eges'], 1)
        self.assertEqual(resultado['aporte_netterm'], 0)
        self.assertEqual(resultado['informadas_confirmadas'], 0)
        self.assertEqual(resultado['tasa_finalizacion'], 0)

    def test_netterm_reafirma_informe_sin_exigir_igualdad_de_estado(self):
        self.eges(estado_turno='Entregado Sin Informe')
        self.netterm()
        with CaptureQueriesContext(connection) as consultas:
            resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 1)
        self.assertEqual(resultado['informadas_confirmadas'], 1)
        self.assertEqual(resultado['tasa_finalizacion'], 100)
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for q in consultas))

    def test_netterm_suple_realizacion_no_confirmada_en_eges(self):
        self.eges(estado_turno='Recepcionado')
        self.netterm(estado='PENDIENTE')
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 1)
        self.assertEqual(resultado['base_eges'], 0)
        self.assertEqual(resultado['aporte_netterm'], 1)
        self.assertEqual(resultado['pendientes'], {})
        self.assertEqual(resultado['informadas_confirmadas'], 0)

    def test_internacion_exclusiva_realizada_pendiente_de_informe_se_incluye(self):
        self.netterm(estado='PENDIENTE')
        resultado = self.produccion()
        self.assertEqual(resultado['aporte_netterm'], 1)
        self.assertEqual(resultado['sin_informe_confirmado'], 1)
        self.assertEqual(resultado['pacientes_unicos_identificables'], 1)

    def test_pendiente_realizar_y_estado_sin_evidencia_no_se_inventan(self):
        self.netterm(pedido='1', estado='PENDIENTE', realizada=False)
        self.netterm(pedido='2', codigo='180113', estado='DESCONOCIDO', realizada=True, pendiente_realizar=True)
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 0)
        self.assertIsNone(resultado['tasa_finalizacion'])
        self.assertEqual(resultado['pendientes']['netterm_realizacion_sin_confirmar'], 2)

    def test_anulacion_no_retira_la_base_eges_ni_se_usa_para_agregar(self):
        self.eges()
        self.netterm(estado='ANULADO')
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 1)
        self.assertEqual(resultado['aporte_netterm'], 0)
        self.assertEqual(resultado['excluidos']['netterm_anulado'], 1)

    def test_eges_anulado_no_se_resucita_con_netterm(self):
        self.eges(estado_turno='Cancelado')
        self.netterm()
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 0)
        self.assertEqual(resultado['pendientes']['netterm_anulacion_contradictoria'], 1)

    def test_repeticiones_eges_no_se_fusionan_y_netterm_ambiguo_no_se_agrega(self):
        self.eges()
        self.eges(hora_turno=time(11))
        self.netterm()
        self.netterm(pedido='2')
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 2)
        self.assertEqual(resultado['aporte_netterm'], 0)
        self.assertEqual(resultado['pendientes']['netterm_correspondencia'], 2)

    def test_informe_y_paciente_se_cuentan_una_vez_y_conteo_anterior_se_conserva(self):
        self.eges(estado_turno='Fin Practica')
        self.netterm()
        self.netterm(pedido='2', codigo='180113', practica='ECOGRAFIA RENAL')
        parametros = dict(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk])
        antes = construir_preview_conteo_consolidado(**parametros)
        resultado = self.produccion()
        despues = construir_preview_conteo_consolidado(**parametros)
        self.assertEqual(antes, despues)
        self.assertEqual(resultado['total_produccion'], 2)
        self.assertEqual(resultado['informadas_confirmadas'], 2)
        self.assertEqual(resultado['pacientes_unicos_identificables'], 1)
        self.assertNotIn('12345678', str(resultado))

    def test_dni_con_puntos_y_ceros_no_duplica_la_misma_practica(self):
        self.eges(dni_paciente='00.123.456')
        self.netterm(documento='123456')
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 1)
        self.assertEqual(resultado['aporte_netterm'], 0)
        self.assertEqual(resultado['pacientes_unicos_identificables'], 1)

    def test_documento_cero_no_genera_un_exclusivo_netterm_automatico(self):
        self.netterm(documento='0000')
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 0)
        self.assertEqual(resultado['pendientes']['netterm_correspondencia'], 1)

    @override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_vista_produccion_solo_lectura_y_restringida(self):
        url = reverse('eges_import:produccion_consolidada')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.usuario)
        self.eges(estado_turno='Fin Practica')
        self.netterm()
        with CaptureQueriesContext(connection) as consultas:
            response = self.client.get(url, {'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Producción respaldada')
        self.assertContains(response, 'Tasa de finalización documentada')
        self.assertNotContains(response, '12345678')
        self.assertEqual(response.context['resultado']['total_produccion'], 1)
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for q in consultas))
        self.assertEqual(self.client.post(url).status_code, 405)
        usuario = get_user_model().objects.create_user(username='medico_sin_estadisticas', perfil_completo=True)
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(url).status_code, 302)
