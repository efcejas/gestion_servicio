import hashlib
from datetime import date, time
from unittest.mock import patch
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import ConciliacionRevision, EgesRow, ImportBatch, NettermFila, NettermLote
from .services_produccion import construir_preview_produccion
from .services_estadisticas import construir_estadisticas_fuentes
from .services_conciliacion import (
    construir_preview_conciliacion, construir_preview_conteo_consolidado,
    registrar_revision_conciliacion,
)


class UnificacionMedicosEstadisticasTest(SimpleTestCase):
    def test_variantes_abreviadas_confirmadas_por_usuario_se_unifican(self):
        from .services_estadisticas import _nombre_medico_estadistica
        pares = [
            ('HERNANDEZ MOJICA MAIRA ALEJAND', 'HERNÁNDEZ MOJICA MAIRA ALEJANDRA'),
            ('BALCAZAR PINEDA NICOLE STEPHAN', 'BALCÁZAR PINEDA NICOLE STEPHANIE'),
            ('SALINAS HERRERA YEFFERSON DAVI', 'SALINAS HERRERA YEFFERSON DAVID'),
        ]
        for abreviado, completo in pares:
            with self.subTest(abreviado=abreviado):
                self.assertEqual(_nombre_medico_estadistica(abreviado), _nombre_medico_estadistica(completo))

    def aliases(self, correspondencias):
        from .services_estadisticas import _aliases_medicos_por_estudios
        practicas, eges, netterm = [], {}, {}
        for indice, (nombre_eges, nombre_netterm, paciente) in enumerate(correspondencias):
            practicas.append({'fila': {'id': indice, 'fecha_turno': date(2026, 10, 10),
                                       'paciente_clave': paciente}, 'netterm': {'id': indice}})
            eges[indice] = SimpleNamespace(medico_informante=nombre_eges)
            netterm[indice] = {'informante': nombre_netterm}
        return _aliases_medicos_por_estudios(practicas, eges, netterm)

    def test_nombre_incompleto_reiterado_se_agrupa_con_su_nombre_completo(self):
        aliases = self.aliases([
            ('TOLEDO GUILLERMO', 'TOLEDO GUILLERMO CARLOS', 'paciente1'),
            ('TOLEDO GUILLERMO', 'TOLEDO GUILLERMO CARLOS', 'paciente2'),
        ])
        self.assertEqual(aliases['GUILLERMO TOLEDO'], 'CARLOS GUILLERMO TOLEDO')

    def test_estudios_del_mismo_paciente_no_bastan_para_aprender_equivalencia(self):
        self.assertEqual(self.aliases([
            ('TOLEDO GUILLERMO', 'TOLEDO GUILLERMO CARLOS', 'paciente1'),
            ('TOLEDO GUILLERMO', 'TOLEDO GUILLERMO CARLOS', 'paciente1'),
        ]), {})

    def test_discrepancia_de_informante_no_agrupa_medicos_diferentes(self):
        self.assertEqual(self.aliases([
            ('MENINI ALBERTO ENRIQUE', 'PUENTE JIMENEZ CARLOS ALBERTO', 'paciente1'),
            ('MENINI ALBERTO ENRIQUE', 'PUENTE JIMENEZ CARLOS ALBERTO', 'paciente2'),
        ]), {})

    def test_nombre_corto_con_dos_profesionales_posibles_conserva_identidades(self):
        self.assertEqual(self.aliases([
            ('TOLEDO GUILLERMO', 'TOLEDO GUILLERMO CARLOS', 'paciente1'),
            ('TOLEDO GUILLERMO', 'TOLEDO GUILLERMO CARLOS', 'paciente2'),
            ('TOLEDO GUILLERMO', 'TOLEDO GUILLERMO JOSE', 'paciente3'),
            ('TOLEDO GUILLERMO', 'TOLEDO GUILLERMO JOSE', 'paciente4'),
        ]), {})


class GraficosPDFProduccionTest(SimpleTestCase):
    def test_grafico_medico_horizontal_apila_todas_las_modalidades(self):
        from matplotlib.axes import Axes
        from .views import _imagen_grafico_estadistico
        original = Axes.barh
        with patch.object(Axes, 'barh', autospec=True, side_effect=original) as barras:
            _imagen_grafico_estadistico(['MEDICO A', 'MEDICO B'], [
                {'label': 'ECO', 'data': [2, 1], 'backgroundColor': '#eab308'},
                {'label': 'TC', 'data': [3, 4], 'backgroundColor': '#3b82f6'},
            ], horizontal=True)
        self.assertEqual(barras.call_count, 2)
        self.assertEqual(list(barras.call_args_list[1].kwargs['left']), [2, 1])
        self.assertEqual(list(barras.call_args_list[1].args[2]), [3, 4])


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
                pendiente_realizar=False, fecha_realizacion=None, tipo_documento='D.N.I.',
                modalidad_original='ECO_GENERAL', originales=None, hora_realizacion=None,
                modalidad_modelo='ECO_GENERAL', fecha_pedido=None, servicio=''):
        clave = hashlib.sha256(f'{pedido}:1:{codigo}'.encode()).hexdigest()
        normales = dict(pedido=pedido, documento=documento, tipo_documento=tipo_documento, practica=practica,
                        codigo_nomenclador=codigo, tipo_nomenclador='1', informante=informante,
                        hora_realizacion=hora_realizacion,
                        servicio=servicio, modalidad=modalidad_original,
                        estado_realizacion='PENDIENTE' if pendiente_realizar else 'CON_FECHA' if realizada else 'DESCONOCIDO')
        return NettermFila.objects.create(
            lote=self.lote, hoja='QA', numero_fila=NettermFila.objects.count()+2,
            clave_candidata_sha256=clave, contenido_sha256=hashlib.sha256(str(normales).encode()).hexdigest(),
            originales_json=originales or [], normalizados_json=normales, fecha_pedido=fecha_pedido or date(2026, 10, 10),
            fecha_realizacion=(fecha_realizacion or date(2026, 10, 10)) if realizada else None,
            estado_informe=estado, anulado=estado == 'ANULADO', modalidad=modalidad_modelo,
        )


class ProduccionFuentesTest(FuentesSinteticasMixin, TestCase):
    def test_pendiente_realizar_sin_fecha_excluye_solo_netterm_sin_retirar_eges(self):
        self.eges()
        pendiente = self.netterm(estado='DESCONOCIDO', realizada=False, pendiente_realizar=True)
        r = construir_preview_produccion(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk])
        self.assertEqual(r['total_produccion'], 1)
        self.assertEqual(r['base_eges'], 1)
        self.assertEqual(r['aporte_netterm'], 0)
        self.assertEqual(r['excluidos']['netterm_pendiente_realizar_sin_fecha'], 1)
        self.assertNotIn('netterm_sin_fecha', r['pendientes'])
        pendiente.refresh_from_db()
        self.assertFalse(pendiente.anulado)
        self.assertIsNone(pendiente.fecha_realizacion)

    def test_provisional_eges_agrupa_ecoguiado_sin_borrar_filas(self):
        for codigo, nombre in [('900079', 'PUNCION BIOPSIA BAJO CTROL.ECOGRAFICO'),
                               ('150101', 'BIOPSIA POR INCISION O PUNCION'),
                               ('150111', 'CITOLOGIA EXFOLIATIVA DE LIQUIDOS')]:
            self.eges(codigo_practica=codigo, practica=nombre, historia_clinica='HC1',
                      centro_atencion='CENTRO', servicio='Ecografia', modalidad='ECO')
        r = construir_preview_produccion(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk])
        self.assertEqual(r['total_produccion'], 1)
        self.assertEqual(r['componentes_ecoguiados_agrupados'], 2)
        self.assertEqual(self.batch.filas.count(), 3)

    def test_agrupacion_netterm_exige_principal_unica_mismo_pedido(self):
        from .services_conciliacion import _datos_netterm
        from .services_procedimientos import agrupar_ecoguiados_provisionales
        principal = self.netterm(codigo='900079', practica='PUNCION BIOPSIA BAJO CTROL.ECOGRAFICO')
        componente = self.netterm(codigo='150101', practica='BIOPSIA POR INCISION O PUNCION')
        otro = self.netterm(pedido='OTRO', codigo='150111', practica='CITOLOGIA EXFOLIATIVA DE LIQUIDOS')
        items = [{'fila': _datos_netterm([fila])} for fila in (principal, componente, otro)]
        conservadas, n = agrupar_ecoguiados_provisionales(items)
        self.assertEqual(n, 1)
        self.assertEqual([x['fila']['id'] for x in conservadas], [principal.pk, otro.pk])
        segunda = self.netterm(codigo='900079/0', practica='PUNCION BIOPSIA BAJO CTROL.ECOGRAFICO B')
        items.append({'fila': _datos_netterm([segunda])})
        conservadas, n = agrupar_ecoguiados_provisionales(items)
        self.assertEqual(n, 0)
        self.assertEqual(len(conservadas), 4)

    def test_componente_sin_modalidad_se_resuelve_solo_con_principal_aceptada(self):
        from .services_conciliacion import _datos_netterm
        from .services_procedimientos import agrupar_ecoguiados_provisionales
        principal = self.netterm(codigo='900079', practica='PUNCION BIOPSIA BAJO CTROL.ECOGRAFICO')
        componente = self.netterm(codigo='150101', practica='BIOPSIA POR INCISION O PUNCION')
        otro = self.netterm(pedido='OTRO', codigo='150111', practica='CITOLOGIA EXFOLIATIVA DE LIQUIDOS')
        resueltos = set()
        conservadas, n = agrupar_ecoguiados_provisionales(
            [{'fila': _datos_netterm([principal])}],
            componentes_sin_modalidad=[_datos_netterm([componente]), _datos_netterm([otro])],
            resueltos=resueltos,
        )
        self.assertEqual(resueltos, {componente.pk})
        self.assertEqual(len(conservadas), 1)
        self.assertEqual(n, 0)

    def test_contexto_actual_evitar_cargar_filas_originales_completas(self):
        self.eges()
        fila = self.netterm()
        normalizados = {**fila.normalizados_json, 'cobertura': 'COBERTURA ACTUAL'}
        NettermFila.objects.filter(pk=fila.pk).update(normalizados_json=normalizados)
        with CaptureQueriesContext(connection) as consultas:
            datos = construir_estadisticas_fuentes(batch_eges_ids=[self.batch.pk],
                                                   lote_netterm_ids=[self.lote.pk])
        self.assertEqual(datos['kpis']['practicas_realizadas'], 1)
        self.assertIn('COBERTURA ACTUAL', datos['obras_sociales']['labels'])
        self.assertFalse(any('originales_json' in consulta['sql'] for consulta in consultas))

    def test_top_diez_medicos_y_coberturas_conservan_totales_en_detalle(self):
        for indice in range(12):
            self.eges(dni_paciente=str(10000000 + indice), medico_informante=f'MEDICO PRUEBA {indice}',
                      obra_social=f'COBERTURA {indice}', codigo_obra_social=str(100 + indice))
        self.eges(dni_paciente='99999999', medico_informante=None, obra_social=None)
        datos = construir_estadisticas_fuentes(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[])
        for clave in ('medicos', 'obras_sociales'):
            grafico = datos[clave]
            self.assertEqual(len(grafico['labels']), 10)
            self.assertNotIn('Resto fuera del top 10', grafico['labels'])
            self.assertNotIn('Sin dato', grafico['labels'])
            self.assertEqual(grafico['total_resto'], 2)
            self.assertEqual(grafico['sin_dato'], 1)
            total = sum(sum(d['data']) for d in grafico['datasets']) + grafico['total_resto'] + grafico['sin_dato']
            self.assertEqual(total, datos['kpis']['practicas_realizadas'])

    def test_unificacion_por_estudios_se_aplica_antes_del_top_y_filtro_modalidad(self):
        for indice, documento in enumerate(('12345678', '87654321')):
            self.eges(dni_paciente=documento, medico_informante='TOLEDO GUILLERMO')
            self.netterm(pedido=str(indice), documento=documento, informante='TOLEDO GUILLERMO CARLOS')
        self.eges(dni_paciente='22222222', codigo_practica='340101', practica='TOMOGRAFIA DE TORAX',
                  medico_informante='TOLEDO GUILLERMO')
        self.netterm(pedido='extra', documento='33333333', informante='TOLEDO GUILLERMO CARLOS')
        seleccion = dict(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk])
        datos = construir_estadisticas_fuentes(**seleccion)
        self.assertEqual(datos['medicos']['labels'], ['CARLOS GUILLERMO TOLEDO'])
        self.assertEqual(sum(sum(d['data']) for d in datos['medicos']['datasets']), 4)
        self.assertEqual(datos['kpis']['practicas_realizadas'], 4)
        self.assertEqual(datos['medicos']['equivalencias'][0]['variantes'],
                         ['CARLOS GUILLERMO TOLEDO', 'GUILLERMO TOLEDO'])
        filtrados = construir_estadisticas_fuentes(**seleccion, modalidades=['TC'])
        self.assertEqual(filtrados['medicos']['labels'], ['CARLOS GUILLERMO TOLEDO'])
        self.assertEqual(filtrados['kpis']['practicas_realizadas'], 1)

    def test_ranking_unifica_variantes_conocidas_del_mismo_medico(self):
        self.eges(medico_informante='GONZALEZ CARRIEL, ARIANNE DENISSE')
        self.netterm(pedido='2', documento='87654321', informante='GONZALEZ CARRIEL ARIANNE DENIS')
        datos = construir_estadisticas_fuentes(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk])
        self.assertEqual(datos['medicos']['labels'], ['ARIANNE CARRIEL DENISSE GONZALEZ'])
        self.assertEqual(sum(sum(d['data']) for d in datos['medicos']['datasets']), 2)
        self.assertEqual(datos['kpis']['practicas_realizadas'], 2)

    def test_alias_ana_belen_y_comas_conservan_personas_distintas(self):
        from .services_estadisticas import _nombre_medico_estadistica
        self.assertEqual(_nombre_medico_estadistica('IZURIETA, ANA BELEN'),
                         _nombre_medico_estadistica('IZURIETA PENAHERRERA ANA BELEN'))
        self.assertEqual(_nombre_medico_estadistica('GONZALEZ CARRIEL, DAYANNE DENIS'),
                         _nombre_medico_estadistica('GONZALEZ CARRIEL DAYANNE DENIS'))
        self.assertNotEqual(_nombre_medico_estadistica('GONZALEZ CARRIEL DAYANNE DENIS'),
                            _nombre_medico_estadistica('GONZALEZ CARRIEL ARIANNE DENIS'))

    def test_franja_netterm_usa_hora_realizacion(self):
        self.netterm(hora_realizacion='14:35:00')
        datos = construir_estadisticas_fuentes(batch_eges_ids=[], lote_netterm_ids=[self.lote.pk])
        self.assertEqual(datos['franja']['datasets'][0]['data'][7], 1)
        self.assertEqual(datos['franja']['datasets'][0]['data'][-1], 0)

    def test_aviso_cobertura_no_depende_del_numero_de_filas(self):
        self.batch.total_filas = 10000
        self.batch.save(update_fields=['total_filas'])
        self.eges()
        datos = construir_estadisticas_fuentes(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[])
        self.assertFalse(datos['metadatos']['advertencia_cobertura'])

    def test_subtipos_netterm_y_cobertura_archivada_se_recuperan_y_ordenan(self):
        for pedido, documento in [('1', '12345678'), ('2', '87654321')]:
            originales = [{'tipo': 'NoneType', 'valor': None} for _ in range(37)]
            originales[13] = {'tipo': 'str', 'valor': 'COBERTURA PRUEBA'}
            self.netterm(pedido=pedido, documento=documento, originales=originales)
        self.eges(practica='ECOGRAFIA TIROIDES', codigo_practica='180115', sub_modalidad='ECO_TIROIDES')
        datos = construir_estadisticas_fuentes(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk])
        self.assertEqual(datos['sub_eco']['datasets'][0]['data'], [2, 1])
        self.assertEqual(datos['sub_eco']['labels'][0], 'Ecografía Abdominal')
        self.assertNotIn('Sin dato', datos['sub_eco']['labels'])
        self.assertIn('COBERTURA PRUEBA', datos['obras_sociales']['labels'])
        self.assertEqual(sum(datos['obras_sociales']['datasets'][0]['data']) + datos['obras_sociales']['sin_dato'], 3)
        self.assertIn('Seleccioná fechas', datos['comparativa']['comparativa']['motivo_sin_comparativa'])

    def test_ranking_muestra_diez_individuales_y_conserva_resto_aparte(self):
        from .services_estadisticas import _ranking, _resto_ranking
        from collections import Counter
        conteo = Counter({f'categoria {i}': i for i in range(1, 13)})
        ranking = _ranking(conteo)
        self.assertEqual(len(ranking), 10)
        resto = _resto_ranking(conteo)
        self.assertEqual(sum(item['total'] for item in resto), 3)
        self.assertEqual(sum(total for _, total in ranking) + sum(item['total'] for item in resto), sum(conteo.values()))

    def confirmar_fuentes(self):
        from .services_validacion_produccion import preparar_validacion_produccion, confirmar_produccion
        seleccion = dict(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk],
                         fecha_desde=date(2026, 10, 10), fecha_hasta=date(2026, 10, 10))
        preparacion = preparar_validacion_produccion(**seleccion)
        return confirmar_produccion(**seleccion, usuario=self.usuario,
                                    firma_esperada=preparacion['firma'], decisiones={})
    @override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_tablero_inicia_con_historico_eges_y_netterm_opcional(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse('eges_import:estadisticas'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form_fuentes']['lotes_eges'].value(), [self.batch.pk])
        self.assertEqual(response.context['form_fuentes']['lotes_netterm'].value(), None)

    @override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_seleccionar_netterm_infiere_periodo_para_comparar_historico_eges(self):
        self.eges()
        self.netterm()
        validacion = self.confirmar_fuentes()
        self.client.force_login(self.usuario)
        with patch('eges_import.views.construir_estadisticas_fuentes',
                   wraps=construir_estadisticas_fuentes) as construir:
            response = self.client.get(reverse('eges_import:estadisticas_fuentes_data'), {
                'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk], 'validacion': validacion.pk,
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['metadatos']['fecha_desde'], '2026-10-10')
        self.assertEqual(response.json()['metadatos']['fecha_hasta'], '2026-10-10')
        self.assertEqual(construir.call_args.kwargs['fecha_desde'], date(2026, 10, 10))
        self.assertEqual(construir.call_args.kwargs['fecha_hasta'], date(2026, 10, 10))

    @override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_tablero_no_duplica_panel_y_conserva_acceso_a_produccion(self):
        self.eges()
        self.netterm()
        self.netterm(pedido='2', documento='87654321')
        self.client.force_login(self.usuario)
        response = self.client.get(reverse('eges_import:estadisticas'), {
            'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="fecha-desde"', count=1)
        self.assertNotContains(response, 'data-lote-picker')
        self.assertNotContains(response, 'Análisis histórico EGES')
        self.assertContains(response, reverse('eges_import:produccion_consolidada'))
        self.assertNotIn('produccion', response.context)
        produccion = self.client.get(reverse('eges_import:produccion_consolidada'), {
            'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk],
        })
        self.assertEqual(produccion.status_code, 200)
        self.assertEqual(produccion.context['resultado']['total_produccion'], 2)
        self.assertEqual(produccion.context['resultado']['aporte_netterm'], 1)

    def produccion(self):
        return construir_preview_produccion(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk])

    def test_practicas_internas_comparten_el_conteo_sin_duplicar(self):
        self.eges()
        self.netterm()
        self.netterm(pedido='2', documento='87654321')
        resultado = construir_preview_produccion(
            batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk], incluir_practicas=True,
        )
        self.assertEqual(len(resultado['practicas']), resultado['total_produccion'])
        self.assertEqual(resultado['total_produccion'], 2)
        self.assertEqual(sum(item['fuente'] == 'NETTERM' for item in resultado['practicas']), 1)
        self.assertNotIn('practicas', self.produccion())

    def test_fuente_unica_estadistica_no_relaja_conciliacion_habitual(self):
        self.eges()
        resultado = construir_preview_produccion(
            batch_eges_ids=[self.batch.pk], lote_netterm_ids=[], permitir_fuente_unica=True,
        )
        self.assertEqual(resultado['total_produccion'], 1)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            construir_preview_produccion(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[])

    def test_estadisticas_comparten_poblacion_y_conservan_sin_dato(self):
        from .services_estadisticas import construir_estadisticas_fuentes

        self.eges()
        self.netterm()
        self.netterm(pedido='2', codigo='180113', practica='ECOGRAFIA RENAL', documento='', estado='PENDIENTE')
        self.eges(dni_paciente='', codigo_practica='180113', practica='ECOGRAFIA RENAL')
        self.netterm(pedido='3', codigo='180114', practica='ECOGRAFIA PELVICA',
                 documento='87654321')
        datos = construir_estadisticas_fuentes(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk])
        self.assertEqual(datos['kpis']['practicas_realizadas'], 3)
        self.assertEqual(datos['kpis']['total_finalizados'], 3)
        self.assertEqual(datos['kpis']['practicas_por_paciente'], 1)
        self.assertTrue(datos['metadatos']['incompleto'])
        for grafico in ('temporal', 'dia_semana', 'franja', 'modalidad', 'medicos', 'obras_sociales'):
            representadas = sum(sum(dataset['data']) for dataset in datos[grafico]['datasets'])
            if grafico in {'medicos', 'obras_sociales'}:
                representadas += datos[grafico]['total_resto'] + datos[grafico]['sin_dato']
            self.assertEqual(representadas, 3, grafico)
        self.assertIn('Sin dato', datos['franja']['labels'])
        self.assertEqual(datos['franja']['datasets'][0]['data'][-1], 1)
        self.assertIsNone(datos['comparativa']['comparativa']['practicas']['anterior'])

    @override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_endpoint_estadistico_no_escribe_ni_expone_documentos(self):
        self.eges()
        self.netterm()
        validacion = self.confirmar_fuentes()
        self.client.force_login(self.usuario)
        with CaptureQueriesContext(connection) as consultas:
            response = self.client.get(reverse('eges_import:estadisticas_fuentes_data'), {
                'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk], 'validacion': validacion.pk,
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['kpis']['practicas_realizadas'], 1)
        self.assertNotContains(response, '12345678')
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for q in consultas))
        self.assertEqual(self.client.get(reverse('eges_import:estadisticas_fuentes_data')).status_code, 400)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('eges_import:estadisticas_fuentes_data')).status_code, 302)

    @override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_pdf_estadistico_usa_la_misma_seleccion_del_tablero(self):
        self.eges()
        self.netterm()
        validacion = self.confirmar_fuentes()
        self.client.force_login(self.usuario)
        parametros = {'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk],
                      'validacion': validacion.pk,
                      'fecha_desde': '2026-10-01', 'fecha_hasta': '2026-10-31',
                      'modalidades[]': ['ECO'], 'agrupacion': 'semana'}
        with patch('eges_import.views.construir_estadisticas_fuentes',
                 wraps=construir_estadisticas_fuentes) as construir:
            response = self.client.get(reverse('eges_import:exportar_pdf_fuentes'), parametros)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        self.assertIn('attachment; filename="estadisticas_fuentes.pdf"', response['Content-Disposition'])
        construir.assert_called_once_with(
            batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk],
            fecha_desde=date(2026, 10, 1), fecha_hasta=date(2026, 10, 31),
            modalidades=['ECO'], agrupacion='semana',
            validacion_id=str(validacion.pk),
        )
        self.assertEqual(self.client.get(reverse('eges_import:exportar_pdf_fuentes')).status_code, 400)

    def registrar_revision(self, eges, decision):
        preview = construir_preview_conciliacion(
            batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk],
        )
        caso = next(
            caso for caso in preview['resultados']
            if caso['netterm'] and any(fila['id'] == eges.pk for fila in caso['eges'])
        )
        return registrar_revision_conciliacion(
            batch_eges_id=self.batch.pk, lote_netterm_ids=[self.lote.pk],
            fila_netterm_id=caso['netterm']['id'], fila_eges_id=eges.pk,
            firma_esperada=preview['firma_snapshot'], decision=decision,
            motivo='Decision de origen para prueba sintetica.', usuario=self.usuario,
        )

    def test_produccion_exige_informe_definitivo(self):
        self.eges(estado_turno='Fin Practica', cantidad=3)
        self.netterm(estado='PENDIENTE')
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 0)
        self.assertEqual(resultado['base_eges'], 0)
        self.assertEqual(resultado['aporte_netterm'], 0)
        self.assertEqual(resultado['informadas_confirmadas'], 0)
        self.assertIsNone(resultado['tasa_finalizacion'])

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
        self.netterm()
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 1)
        self.assertEqual(resultado['base_eges'], 0)
        self.assertEqual(resultado['aporte_netterm'], 1)
        self.assertEqual(resultado['pendientes'], {})
        self.assertEqual(resultado['informadas_confirmadas'], 1)

    def test_recepcionado_queda_en_alerta_separada_sin_personalizar_el_pendiente(self):
        recepcionado = self.eges(estado_turno='Recepcionado')
        resultado = self.produccion()
        alertas = resultado['recepcionados_sin_realizacion']
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]['fila_id'], recepcionado.pk)
        self.assertEqual(alertas[0]['lote_id'], recepcionado.batch_id)
        self.assertEqual(alertas[0]['codigo'], recepcionado.codigo_practica)
        self.assertEqual(alertas[0]['fecha_turno'], recepcionado.fecha_turno)
        self.assertNotIn(recepcionado.dni_paciente, str(alertas))

    def test_internacion_exclusiva_pendiente_de_informe_queda_pendiente(self):
        self.netterm(estado='PENDIENTE')
        resultado = self.produccion()
        self.assertEqual(resultado['aporte_netterm'], 0)
        self.assertEqual(resultado['sin_informe_confirmado'], 0)
        self.assertEqual(resultado['pacientes_unicos_identificables'], 0)
        self.assertEqual(resultado['pendientes']['netterm_informe_sin_confirmar'], 1)

    def test_mes_realizacion_mueve_coincidencia_sin_duplicarla(self):
        self.eges()
        self.netterm(fecha_realizacion=date(2026, 11, 2))
        seleccion = dict(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk])
        octubre = construir_preview_produccion(
            **seleccion, fecha_desde=date(2026, 10, 1), fecha_hasta=date(2026, 10, 31),
        )
        noviembre = construir_preview_produccion(
            **seleccion, fecha_desde=date(2026, 11, 1), fecha_hasta=date(2026, 11, 30),
        )
        self.assertEqual(octubre['total_produccion'], 0)
        self.assertEqual(noviembre['total_produccion'], 1)
        datos = construir_estadisticas_fuentes(
            **seleccion, fecha_desde=date(2026, 11, 1), fecha_hasta=date(2026, 11, 30), agrupacion='dia',
        )
        self.assertEqual(datos['temporal']['labels'], ['02/11/2026'])
        self.assertEqual(datos['kpis']['practicas_realizadas'], 1)

    def test_definitivo_netterm_sin_fecha_realizacion_no_se_inventa(self):
        self.netterm(realizada=False)
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 0)
        self.assertEqual(resultado['pendientes']['netterm_sin_fecha'], 1)

    def test_pendiente_realizar_y_estado_sin_evidencia_no_se_inventan(self):
        self.netterm(pedido='1', estado='PENDIENTE', realizada=False)
        self.netterm(pedido='2', codigo='180113', estado='DESCONOCIDO', realizada=True, pendiente_realizar=True)
        resultado = self.produccion()
        self.assertEqual(resultado['total_produccion'], 0)
        self.assertIsNone(resultado['tasa_finalizacion'])
        self.assertEqual(resultado['pendientes']['netterm_realizacion_sin_confirmar'], 1)
        self.assertEqual(resultado['pendientes']['netterm_sin_fecha'], 1)

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

    def test_vincular_vigente_resuelve_ambiguedad_y_no_duplica(self):
        primera = self.eges(estado_turno='Recepcionado')
        segunda = self.eges(estado_turno='Recepcionado', hora_turno=time(11))
        self.netterm()
        self.registrar_revision(segunda, ConciliacionRevision.DECISION_VINCULAR)

        resultado = self.produccion()

        self.assertEqual(resultado['total_produccion'], 1)
        self.assertEqual(resultado['base_eges'], 0)
        self.assertEqual(resultado['aporte_netterm'], 1)
        self.assertEqual(resultado['informadas_confirmadas'], 1)
        self.assertEqual(resultado['vinculaciones_humanas_consumidas'], 1)
        self.assertEqual(resultado['vinculaciones_rechazadas_consumidas'], 0)

    def test_no_vincular_bloquea_match_automatico_sin_sumar_netterm(self):
        eges = self.eges()
        self.netterm()
        self.registrar_revision(eges, ConciliacionRevision.DECISION_NO_VINCULAR)

        resultado = self.produccion()

        self.assertEqual(resultado['total_produccion'], 1)
        self.assertEqual(resultado['base_eges'], 1)
        self.assertEqual(resultado['aporte_netterm'], 0)
        self.assertEqual(resultado['vinculaciones_humanas_consumidas'], 0)
        self.assertEqual(resultado['vinculaciones_rechazadas_consumidas'], 1)
        self.assertEqual(resultado['pendientes']['netterm_correspondencia'], 1)

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
