from io import BytesIO
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from openpyxl import Workbook

from .forms import ImportarEGESForm
from .models import DirectorToken, EgesRow, ImportBatch, NettermFila, NettermLote
from .services import calcular_sha256_archivo, procesar_excel_eges
from .services_netterm import ENCABEZADOS_NETTERM, guardar_lote_netterm, preparar_preview_netterm


def _fila_netterm(**cambios):
    fila = [None] * 37
    valores = {
        0: 'ECOGRAFIA', 1: '000123', 2: 'ECOGRAFIA COMPLETA DE ABDOMEN',
        3: 'A', 4: '000987', 5: 'PACIENTE FICTICIO', 6: 'DNI', 7: '00123456',
        9: datetime(2026, 10, 31), 10: time(7, 52),
        11: datetime(2026, 11, 1), 12: time(8, 12),
        15: 'SOLICITANTE FICTICIO', 18: 'GUARDIA', 22: 'INFORME DEFINITIVO',
        23: 'TECNICO FICTICIO', 24: 'OPERADOR FICTICIO', 28: 'INFORMANTE FICTICIO',
        29: datetime(2026, 11, 2), 30: time(9, 15), 35: 1, 36: '180112',
    }
    valores.update({int(indice): valor for indice, valor in cambios.items()})
    for indice, valor in valores.items():
        fila[indice] = valor
    return fila


def _archivo_netterm(filas=None, encabezados=None, nombre_hoja='Netterm'):
    libro = Workbook()
    hoja = libro.active
    hoja.title = nombre_hoja
    hoja.append(list(ENCABEZADOS_NETTERM) if encabezados is None else encabezados)
    for fila in filas if filas is not None else [_fila_netterm()]:
        hoja.append(fila)
    libro.create_sheet('Hoja vacia')
    buffer = BytesIO()
    libro.save(buffer)
    libro.close()
    return SimpleUploadedFile('netterm.xlsx', buffer.getvalue())


class PreviewNettermParserTest(SimpleTestCase):
    def test_preserva_fechas_horas_roles_y_ceros_sin_inventar_cantidad(self):
        archivo = _archivo_netterm()
        resultado = preparar_preview_netterm(archivo)
        fila = resultado['filas'][0]
        self.assertEqual(fila['pedido'], '000123')
        self.assertEqual(fila['documento'], '00123456')
        self.assertEqual(fila['historia_clinica'], '000987')
        self.assertEqual(fila['fecha_pedido'], date(2026, 10, 31))
        self.assertEqual(fila['fecha_realizacion'], date(2026, 11, 1))
        self.assertEqual(fila['fecha_informe'], date(2026, 11, 2))
        self.assertEqual([fila[campo] for campo in ('hora_pedido', 'hora_realizacion', 'hora_informe')],
                         [time(7, 52), time(8, 12), time(9, 15)])
        self.assertEqual(fila['informante'], 'INFORMANTE FICTICIO')
        self.assertNotEqual(fila['solicitante'], fila['informante'])
        self.assertIsNone(fila['cantidad'])
        self.assertEqual(len(fila['originales']), 37)
        self.assertEqual(resultado['hojas'], ['Netterm'])
        self.assertEqual(len(resultado['sha256']), 64)
        self.assertEqual(archivo.tell(), 0)

    def test_clasifica_por_practica_no_por_archivo(self):
        filas = [
            _fila_netterm(),
            _fila_netterm(**{'1': '2', '2': 'ECODOPPLER VENOSO MM INF', '36': '900048'}),
            _fila_netterm(**{'1': '3', '2': 'ECODOPPLER CARDIACO', '36': '900009'}),
        ]
        resultado = preparar_preview_netterm(_archivo_netterm(filas))
        self.assertEqual([fila['modalidad'] for fila in resultado['filas']], ['ECO_GENERAL', 'DOP', 'ECOCAR'])

    def test_repetidos_se_marcan_pero_no_se_borran(self):
        resultado = preparar_preview_netterm(_archivo_netterm([_fila_netterm(), _fila_netterm()]))
        self.assertEqual(resultado['resumen']['filas_validas'], 2)
        self.assertEqual(resultado['resumen']['claves_repetidas'], 1)
        self.assertTrue(all(fila['clave_repetida'] for fila in resultado['filas']))

    def test_mismo_paciente_con_pedidos_distintos_no_es_duplicado(self):
        resultado = preparar_preview_netterm(_archivo_netterm([_fila_netterm(), _fila_netterm(**{'1': 'otro'})]))
        self.assertEqual(resultado['resumen']['claves_repetidas'], 0)

    def test_rechaza_columnas_movidas_aunque_los_nombres_sean_validos(self):
        encabezados = list(ENCABEZADOS_NETTERM)
        encabezados[9], encabezados[11] = encabezados[11], encabezados[9]
        with self.assertRaises(ValidationError):
            preparar_preview_netterm(_archivo_netterm(encabezados=encabezados))

    def test_no_evalua_formulas_y_omite_filas_no_identificables(self):
        resultado = preparar_preview_netterm(_archivo_netterm([
            list(ENCABEZADOS_NETTERM), [None] * 37,
            _fila_netterm(**{'2': '=1+1'}), _fila_netterm(**{'1': None}), _fila_netterm(),
        ]))
        self.assertEqual(resultado['resumen']['filas_validas'], 1)
        self.assertEqual(resultado['resumen']['filas_ignoradas'], 4)
        self.assertEqual({aviso['codigo'] for aviso in resultado['advertencias']},
                         {'FORMULA_NO_ADMITIDA', 'FILA_NO_IDENTIFICABLE'})

    def test_datos_invalidos_no_se_sustituyen_y_avisos_no_contienen_phi(self):
        resultado = preparar_preview_netterm(_archivo_netterm([
            _fila_netterm(**{'9': 'fecha secreta invalida', '10': '99:99', '7': None, '28': None}),
        ]))
        fila = resultado['filas'][0]
        self.assertIsNone(fila['fecha_pedido'])
        self.assertIsNone(fila['hora_pedido'])
        self.assertEqual(fila['originales'][9], 'fecha secreta invalida')
        self.assertEqual(resultado['resumen']['advertencias_total'], 4)
        self.assertNotIn('secreta', str(resultado['advertencias']))
        self.assertNotIn('PACIENTE FICTICIO', str(resultado['resumen']))

    def test_rechaza_extension_eges_y_archivo_corrupto(self):
        for archivo in (SimpleUploadedFile('netterm.xls', b'no'), SimpleUploadedFile('netterm.xlsx', b'no')):
            with self.subTest(nombre=archivo.name), self.assertRaises(ValidationError):
                preparar_preview_netterm(archivo)

    def test_estados_clinicos_separados_y_anulacion_sin_activar_cobro(self):
        resultado = preparar_preview_netterm(_archivo_netterm([
            _fila_netterm(**{'22': 'ANULADO'}),
            _fila_netterm(**{'1': '2', '22': 'PENDIENTE REALIZAR', '11': None}),
        ]))
        self.assertTrue(resultado['filas'][0]['anulado'])
        self.assertEqual(resultado['filas'][1]['estado_realizacion'], 'PENDIENTE')
        self.assertEqual(resultado['filas'][1]['estado_informe'], 'DESCONOCIDO')

    def test_limites_de_archivo_y_filas_rechazan_no_recortan(self):
        archivo = _archivo_netterm()
        with patch('eges_import.services_netterm.MAX_BYTES_NETTERM', 10):
            with self.assertRaises(ValidationError):
                preparar_preview_netterm(archivo)
        with patch('eges_import.services_netterm.MAX_FILAS_NETTERM', 1):
            with self.assertRaises(ValidationError):
                preparar_preview_netterm(_archivo_netterm([_fila_netterm(), _fila_netterm(**{'1': '2'})]))

    def test_limita_detalle_de_advertencias_sin_perder_el_total(self):
        filas = [_fila_netterm(**{'1': str(indice), '28': None}) for indice in range(120)]
        resultado = preparar_preview_netterm(_archivo_netterm(filas))
        self.assertEqual(len(resultado['advertencias']), 100)
        self.assertEqual(resultado['resumen']['advertencias_total'], 120)
        self.assertEqual(resultado['resumen']['filas_validas'], 120)


@override_settings(SECURE_SSL_REDIRECT=False)
class PreviewNettermViewTest(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_user(
            username='netterm_admin', is_superuser=True, is_staff=True, perfil_completo=True,
        )
        self.url = reverse('eges_import:preview_netterm')

    def test_preview_anonimo_no_persiste_ni_expone_filas(self):
        from liquidacion.models import RegistroEstudiosPorMedico, SesionContable

        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        modelos = (ImportBatch, EgesRow, RegistroEstudiosPorMedico, SesionContable)
        antes = [modelo.objects.count() for modelo in modelos]
        response = self.client.post(self.url, {'archivo': _archivo_netterm()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['preview']['resumen']['filas_validas'], 1)
        self.assertNotIn('filas', response.context['preview'])
        self.assertFalse(hasattr(response.context['form'], 'resultado_preview'))
        self.assertNotContains(response, 'PACIENTE FICTICIO')
        self.assertNotContains(response, '00123456')
        self.assertNotContains(response, 'INFORMANTE FICTICIO')
        self.assertContains(response, '31/10/2026')
        self.assertContains(response, '02/11/2026')
        self.assertEqual([modelo.objects.count() for modelo in modelos], antes)

    def test_requiere_autenticacion_y_superusuario(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        for rol in ('administrativo', 'jefe_servicio', 'medico_residente'):
            usuario = get_user_model().objects.create_user(
                username=f'netterm_{rol}', rol=rol, perfil_completo=True,
            )
            with self.subTest(rol=rol):
                self.client.force_login(usuario)
                response = self.client.post(self.url, {'archivo': _archivo_netterm()})
                self.assertEqual(response.status_code, 302)
        self.assertFalse(ImportBatch.objects.exists())
        self.assertFalse(EgesRow.objects.exists())

    def test_archivo_eges_se_rechaza_sin_filtrar_contenido_o_crear_lote(self):
        self.client.force_login(self.superuser)
        response = self.client.post(self.url, {
            'archivo': SimpleUploadedFile('eges.xlsx', _archivo_eges_xlsx()),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['preview'])
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(ImportBatch.objects.exists())
        self.assertNotContains(response, 'NIZ MICAELA')

    def test_libro_sin_datos_muestra_estado_vacio(self):
        self.client.force_login(self.superuser)
        response = self.client.post(self.url, {'archivo': _archivo_netterm([])})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No se encontraron estudios identificables')

    def test_acceso_separado_desde_importacion_eges(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('eges_import:importar'))
        self.assertContains(response, self.url)

    def test_post_vacio_exige_archivo(self):
        self.client.force_login(self.superuser)
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertIn('archivo', response.context['form'].errors)
        self.assertIsNone(response.context['preview'])


class AlmacenamientoNettermTest(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='netterm_storage_admin', is_superuser=True, is_staff=True, perfil_completo=True,
        )

    def _guardar(self, archivo):
        preview = preparar_preview_netterm(archivo)
        return guardar_lote_netterm(
            archivo=archivo, usuario=self.usuario, motivo='Carga de origen verificada.',
            sha256_esperado=preview['sha256'], version_parser_esperada=preview['version_parser'],
        )

    def test_archiva_originales_tipados_y_fechas_sin_crear_datos_eges(self):
        resultado = self._guardar(_archivo_netterm())
        self.assertTrue(resultado['creado'])
        fila = NettermFila.objects.get()
        self.assertEqual(fila.originales_json[7], {'tipo': 'str', 'valor': '00123456'})
        self.assertEqual(fila.originales_json[9]['tipo'], 'datetime')
        self.assertEqual(fila.normalizados_json['fecha_pedido'], '2026-10-31')
        self.assertIsNone(fila.normalizados_json['cantidad'])
        self.assertEqual(fila.fecha_realizacion, date(2026, 11, 1))
        self.assertEqual(fila.clase_observacion, 'NUEVA')
        self.assertFalse(ImportBatch.objects.exists())
        self.assertFalse(EgesRow.objects.exists())

    def test_reimportacion_exacta_devuelve_el_lote_sin_duplicar_filas(self):
        archivo = _archivo_netterm()
        primer_lote = self._guardar(archivo)
        segundo_lote = self._guardar(archivo)
        self.assertFalse(segundo_lote['creado'])
        self.assertEqual(primer_lote['lote'].pk, segundo_lote['lote'].pk)
        self.assertEqual(NettermLote.objects.count(), 1)
        self.assertEqual(NettermFila.objects.count(), 1)

    def test_exportacion_posterior_con_estado_nuevo_conserva_version_anterior(self):
        self._guardar(_archivo_netterm([_fila_netterm(**{'22': 'PENDIENTE INFORMAR', '29': None, '30': None})]))
        anterior = NettermFila.objects.get()
        self._guardar(_archivo_netterm())
        nueva = NettermFila.objects.order_by('-pk').first()
        anterior.refresh_from_db()
        self.assertEqual(nueva.clase_observacion, 'ACTUALIZADA')
        self.assertEqual(nueva.referencia_previa_id, anterior.pk)
        self.assertEqual(anterior.estado_informe, 'PENDIENTE')
        self.assertEqual(nueva.estado_informe, 'DEFINITIVO')
        self.assertEqual(NettermLote.objects.count(), 2)

    def test_mismo_contenido_en_otro_libro_archiva_evidencia_reiterada(self):
        self._guardar(_archivo_netterm())
        self._guardar(_archivo_netterm(nombre_hoja='Exportacion posterior'))
        nueva = NettermFila.objects.order_by('-pk').first()
        self.assertEqual(nueva.clase_observacion, 'REITERADA')
        self.assertIsNotNone(nueva.referencia_previa_id)
        self.assertEqual(NettermFila.objects.count(), 2)

    def test_clave_repetida_se_archiva_ambigua_sin_fusion(self):
        self._guardar(_archivo_netterm([_fila_netterm(), _fila_netterm(**{'22': 'PENDIENTE INFORMAR'})]))
        self.assertEqual(NettermFila.objects.filter(clase_observacion='AMBIGUA').count(), 2)
        self.assertFalse(NettermFila.objects.exclude(referencia_previa=None).exists())

    def test_misma_clave_con_otro_documento_no_se_asume_actualizacion(self):
        self._guardar(_archivo_netterm())
        self._guardar(_archivo_netterm([_fila_netterm(**{'7': '99999999'})]))
        nueva = NettermFila.objects.order_by('-pk').first()
        self.assertEqual(nueva.clase_observacion, 'AMBIGUA')
        self.assertIsNone(nueva.referencia_previa_id)

    def test_ambiguedad_no_se_resuelve_al_reimportar_otra_exportacion(self):
        self._guardar(_archivo_netterm([_fila_netterm(), _fila_netterm(**{'22': 'PENDIENTE INFORMAR'})]))
        self._guardar(_archivo_netterm(nombre_hoja='Nueva exportacion'))
        nueva = NettermFila.objects.order_by('-pk').first()
        self.assertEqual(nueva.clase_observacion, 'AMBIGUA')
        self.assertIsNone(nueva.referencia_previa_id)

    def test_fallo_al_insertar_filas_revierte_el_lote_completo(self):
        with patch.object(NettermFila.objects, 'bulk_create', side_effect=RuntimeError('fallo sintetico')):
            with self.assertRaises(RuntimeError):
                self._guardar(_archivo_netterm())
        self.assertFalse(NettermLote.objects.exists())
        self.assertFalse(NettermFila.objects.exists())

    def test_permisos_huella_y_motivo_rechazados_sin_escrituras(self):
        archivo = _archivo_netterm()
        preview = preparar_preview_netterm(archivo)
        administrativo = get_user_model().objects.create_user(username='netterm_storage_denied', rol='administrativo')
        parametros = {
            'archivo': archivo, 'usuario': self.usuario, 'motivo': 'Carga verificada.',
            'sha256_esperado': preview['sha256'], 'version_parser_esperada': preview['version_parser'],
        }
        for cambios in ({'usuario': administrativo}, {'motivo': ''}, {'sha256_esperado': '0' * 64}):
            with self.subTest(cambios=list(cambios)), self.assertRaises(ValidationError):
                guardar_lote_netterm(**{**parametros, **cambios})
        self.assertFalse(NettermLote.objects.exists())

    def test_modelos_no_permiten_sobrescribir_snapshots_por_save(self):
        lote = self._guardar(_archivo_netterm())['lote']
        fila = NettermFila.objects.get()
        with self.assertRaises(ValidationError):
            lote.save()
        with self.assertRaises(ValidationError):
            fila.save()


@override_settings(SECURE_SSL_REDIRECT=False)
class GuardadoNettermViewTest(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='netterm_http_admin', is_superuser=True, is_staff=True, perfil_completo=True,
        )
        self.client.force_login(self.usuario)
        self.preview_url = reverse('eges_import:preview_netterm')
        self.guardar_url = reverse('eges_import:guardar_netterm')
        self.lotes_url = reverse('eges_import:lista_lotes_netterm')
        self.contenido = _archivo_netterm().read()

    def _preview(self):
        response = self.client.post(self.preview_url, {
            'archivo': SimpleUploadedFile('netterm.xlsx', self.contenido),
        })
        self.assertEqual(response.status_code, 200)
        return response.context['guardar_form'].initial['preview_token']

    def _datos(self, token, contenido=None):
        return {
            'guardar-archivo': SimpleUploadedFile('netterm.xlsx', self.contenido if contenido is None else contenido),
            'guardar-preview_token': token,
            'guardar-motivo': 'Carga Netterm de origen confirmada.',
            'guardar-confirmar': 'on',
        }

    def test_preview_confirmacion_guardado_y_reenvio_sin_duplicados(self):
        token = self._preview()
        self.assertFalse(NettermLote.objects.exists())
        response = self.client.post(self.guardar_url, self._datos(token))
        self.assertRedirects(response, self.lotes_url)
        self.assertEqual(NettermLote.objects.count(), 1)
        self.assertEqual(NettermFila.objects.count(), 1)
        lista = self.client.get(self.lotes_url)
        self.assertContains(lista, 'Lotes de origen')
        self.assertNotContains(lista, 'PACIENTE FICTICIO')
        self.assertNotContains(lista, '00123456')
        response = self.client.post(self.guardar_url, self._datos(token))
        self.assertRedirects(response, self.lotes_url)
        self.assertEqual(NettermLote.objects.count(), 1)
        self.assertEqual(NettermFila.objects.count(), 1)
        self.assertFalse(ImportBatch.objects.exists())
        self.assertFalse(EgesRow.objects.exists())

    def test_sin_confirmacion_o_archivo_distinto_no_guarda(self):
        token = self._preview()
        sin_confirmar = self._datos(token)
        del sin_confirmar['guardar-confirmar']
        response = self.client.post(self.guardar_url, sin_confirmar)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['guardar_form'].errors)
        otro_contenido = _archivo_netterm([_fila_netterm(**{'1': 'distinto'})]).read()
        response = self.client.post(self.guardar_url, self._datos(token, otro_contenido))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no coincide con el preview')
        self.assertFalse(NettermLote.objects.exists())

    def test_token_alterado_vencido_o_de_otro_usuario_no_guarda(self):
        import time as reloj

        token = self._preview()
        response = self.client.post(self.guardar_url, self._datos(token + 'alterado'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'vencio o fue alterado')
        vencimiento = reloj.time() + 901
        with patch('django.core.signing.time.time', return_value=vencimiento):
            response = self.client.post(self.guardar_url, self._datos(token))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'vencio o fue alterado')
        otro_usuario = get_user_model().objects.create_user(
            username='netterm_http_otro', is_superuser=True, is_staff=True, perfil_completo=True,
        )
        self.client.force_login(otro_usuario)
        response = self.client.post(self.guardar_url, self._datos(token))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'pertenece a otro usuario')
        self.assertFalse(NettermLote.objects.exists())

    def test_guardado_solo_post_y_listado_restringido(self):
        self.assertEqual(self.client.get(self.guardar_url).status_code, 405)
        self.assertContains(self.client.get(self.lotes_url), 'Todavía no hay lotes Netterm guardados')
        administrativo = get_user_model().objects.create_user(
            username='netterm_http_admin_denegado', rol='administrativo', perfil_completo=True,
        )
        self.client.force_login(administrativo)
        self.assertEqual(self.client.get(self.lotes_url).status_code, 302)
        self.assertEqual(self.client.post(self.guardar_url, {}).status_code, 302)
        self.assertFalse(NettermLote.objects.exists())


def _archivo_eges_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = 'Atendidos'
    ws.append([
        'Dni',
        'Numero  Afiliado',
        'Centro',
        'Fecha Turno',
        'Hora Desde',
        'Hora Hasta',
        'Tipo Atencion',
        'Medico Informante',
        'Medico Actuante',
        'Paciente',
        'Codigo OS',
        'Obra Social',
        'Equipo',
        'Estado Turno',
        'Código Practica',
        'Practica',
        'Cantidad',
        'Servicio',
        'Estado Informe',
        'Tipo de turno',
        'Tipo de paciente',
        'Region del informe',
    ])
    ws.append([
        '37933118',
        '2052113',
        'Sanatorio Colegiales',
        '01/05/2026',
        '09:45',
        '10:00',
        'Ambulatorio',
        'Médico No Especificado',
        'TOMALA BERNABE FABIAN HOLGER',
        'NIZ MICAELA YANINA',
        '1967',
        'SANCOR SALUD (C)',
        'P - Ecografo - AFFINITI 30',
        'Informado',
        '180112/0',
        'ECOGRAFIA COMPLETA DE ABDOMEN',
        1,
        'Ecografia',
        '-',
        'Normal',
        'Adulto',
        '-',
    ])
    ws.append([
        '37933118',
        '2052113',
        'Sanatorio Colegiales',
        '01/05/2026',
        '09:45',
        '10:00',
        'Ambulatorio',
        'Médico No Especificado',
        'TOMALA BERNABE FABIAN HOLGER',
        'NIZ MICAELA YANINA',
        '1967',
        'SANCOR SALUD (C)',
        'P - Ecografo - AFFINITI 30',
        'Informado',
        '3005554/0',
        'CAMISOLIN',
        1,
        'Ecografia',
        '-',
        'Normal',
        'Adulto',
        '-',
    ])
    contenido = BytesIO()
    wb.save(contenido)
    contenido.seek(0)
    return contenido.getvalue()


def _archivo_atendidos_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = 'Turnos'
    ws.append([
        'Fecha', 'Paciente', 'Historia Clinica', 'Protocolo', 'Centro',
        'Servicio', 'Práctica', 'Médico', 'Obra Social', 'Estado',
        'Informante', 'Equipo', 'Duración', 'Contraste', 'Anestesia',
        'Tipo Turno', 'Técnico', 'Tipo Ingreso', 'Aplicación Origen',
    ])
    filas = [
        ('01/05/2026 09:00', 'PROTO-1', 'ACTUANTE UNO', 'INFORMANTE UNO', 'TECNICO UNO'),
        ('01/05/2026 10:00', 'PROTO-2', 'ACTUANTE DOS', 'Médico No Especificado', 'TECNICO DOS'),
        ('01/05/2026 11:00', 'PROTO-3', 'Médico No Especificado', ', Médico No Especificado', 'TECNICO TRES'),
    ]
    for numero, (fecha, protocolo, actuante, informante, tecnico) in enumerate(filas, start=1):
        ws.append([
            fecha, f'PACIENTE {numero}', str(1000 + numero), protocolo,
            'Sanatorio Colegiales', 'Ecografia',
            'ECOGRAFIA COMPLETA DE ABDOMEN', actuante, 'COBERTURA',
            'Informado', informante, 'Ecografo 1', 15, 'No', 'No',
            'Normal', tecnico, 'Ambulatorio', 'Portal',
        ])
    contenido = BytesIO()
    wb.save(contenido)
    contenido.seek(0)
    return contenido.getvalue()


def _archivo_practicas_mismo_protocolo_xlsx(practicas):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Turnos'
    ws.append([
        'Dni', 'Historia Clinica', 'Protocolo', 'Centro', 'Fecha Turno',
        'Hora Desde', 'Servicio', 'Práctica', 'Código Practica',
        'Estado Turno', 'Cantidad',
    ])
    for practica in practicas:
        ws.append([
            '12345678', '12345678', 'PROTO-1', 'Sanatorio Colegiales',
            '01/05/2026', '09:00', 'Ecografia', practica, '900137/0',
            'Informado', 1,
        ])
    contenido = BytesIO()
    wb.save(contenido)
    contenido.seek(0)
    return contenido.getvalue()


class ImportacionEgesAuditoriaPacsTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='admin', password='x')

    def test_importa_campos_operativos_y_descarta_insumos(self):
        archivo = SimpleUploadedFile(
            'Turnos-Mayo-ECO.xlsx',
            _archivo_eges_xlsx(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        batch = ImportBatch.objects.create(usuario=self.user, archivo_nombre=archivo.name)

        resultado = procesar_excel_eges(archivo, batch)

        self.assertEqual(resultado['creadas'], 1)
        self.assertEqual(EgesRow.objects.count(), 1)
        fila = EgesRow.objects.get()
        self.assertEqual(fila.dni_paciente, '37933118')
        self.assertEqual(fila.historia_clinica, '37933118')
        self.assertEqual(fila.numero_afiliado, '2052113')
        self.assertEqual(fila.apellido_nombre, 'NIZ MICAELA YANINA')
        self.assertEqual(fila.tipo_atencion, 'Ambulatorio')
        self.assertEqual(fila.hora_turno.strftime('%H:%M'), '09:45')
        self.assertEqual(fila.hora_hasta.strftime('%H:%M'), '10:00')
        self.assertEqual(fila.codigo_practica, '180112/0')
        self.assertEqual(fila.practica, 'ECOGRAFIA COMPLETA DE ABDOMEN')
        self.assertEqual(fila.medico_informante, 'TOMALA BERNABE FABIAN HOLGER')
        self.assertEqual(fila.medico_actuante, 'TOMALA BERNABE FABIAN HOLGER')
        self.assertEqual(fila.estado_informe, '-')
        self.assertEqual(fila.tipo_turno, 'Normal')
        self.assertEqual(fila.tipo_paciente, 'Adulto')
        self.assertEqual(fila.region_informe, '-')

    def test_aguja_de_biopsia_se_clasifica_como_insumo(self):
        fila = EgesRow(practica='AGUJA DE BIOPSIA', servicio='Ecografia')

        self.assertTrue(fila.clasificar_insumo())

    def test_puncion_biopsia_guiada_se_conserva_como_practica(self):
        fila = EgesRow(
            practica='PUNCION BIOPSIA BAJO CONTROL ECOGRAFICO',
            servicio='Ecografia',
        )

        self.assertFalse(fila.clasificar_insumo())

    def test_formulario_acepta_xlsx_eges_real(self):
        archivo = SimpleUploadedFile(
            'Turnos-Mayo-ECO.xlsx',
            _archivo_eges_xlsx(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        form = ImportarEGESForm(files={'archivo': archivo})

        self.assertTrue(form.is_valid(), form.errors)

    def test_reimportar_archivo_identico_no_crea_otro_lote_ni_duplica_filas(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.client.force_login(self.user)
        contenido = _archivo_eges_xlsx()

        for nombre in ('Turnos-Mayo-ECO.xlsx', 'copia-renombrada.xlsx'):
            response = self.client.post(
                '/eges/importar/',
                {'archivo': SimpleUploadedFile(
                    nombre,
                    contenido,
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                )},
            )
            self.assertEqual(response.status_code, 302)

        self.assertEqual(ImportBatch.objects.count(), 1)
        self.assertEqual(EgesRow.objects.count(), 1)
        self.assertEqual(
            ImportBatch.objects.get().archivo_sha256,
            calcular_sha256_archivo(BytesIO(contenido)),
        )

    def test_reimportar_datos_de_lote_historico_sin_huella_descarta_lote_vacio(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.client.force_login(self.user)
        contenido = _archivo_eges_xlsx()
        historico = ImportBatch.objects.create(
            usuario=self.user,
            archivo_nombre='historico-sin-huella.xlsx',
        )
        procesar_excel_eges(BytesIO(contenido), historico)
        historico.calcular_metricas()

        response = self.client.post(
            '/eges/importar/',
            {'archivo': SimpleUploadedFile(
                'reintento-historico.xlsx',
                contenido,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )},
        )

        self.assertRedirects(response, '/eges/')
        self.assertEqual(ImportBatch.objects.count(), 1)
        self.assertEqual(EgesRow.objects.count(), 1)
        self.assertTrue(ImportBatch.objects.filter(pk=historico.pk).exists())

    def test_importa_formato_atendidos_y_resuelve_profesional_desde_tres_columnas(self):
        contenido = _archivo_atendidos_xlsx()
        archivo = SimpleUploadedFile(
            'Atendidos-mayo-ECO.xlsx',
            contenido,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        form = ImportarEGESForm(files={'archivo': archivo})
        self.assertTrue(form.is_valid(), form.errors)
        batch = ImportBatch.objects.create(usuario=self.user, archivo_nombre=archivo.name)

        resultado = procesar_excel_eges(archivo, batch)

        self.assertEqual(resultado['creadas'], 3)
        filas = {fila.protocolo: fila for fila in EgesRow.objects.all()}
        self.assertEqual(filas['PROTO-1'].medico_informante, 'INFORMANTE UNO')
        self.assertEqual(filas['PROTO-2'].medico_informante, 'ACTUANTE DOS')
        self.assertEqual(filas['PROTO-3'].medico_informante, 'TECNICO TRES')
        self.assertEqual(filas['PROTO-1'].medico_actuante, 'ACTUANTE UNO')
        self.assertEqual(filas['PROTO-1'].tecnico, 'TECNICO UNO')
        self.assertEqual(str(filas['PROTO-1'].duracion_minutos), '15.00')
        self.assertEqual(filas['PROTO-1'].aplicacion_origen, 'Portal')
        self.assertEqual(filas['PROTO-1'].fecha_turno.isoformat(), '2026-05-01')
        self.assertEqual(filas['PROTO-1'].hora_turno.strftime('%H:%M'), '09:00')

    def test_mismo_protocolo_con_tres_practicas_conserva_las_tres(self):
        contenido = _archivo_practicas_mismo_protocolo_xlsx([
            'ECOGRAFIA ABDOMINAL',
            'ECOGRAFIA RENAL',
            'ECOGRAFIA VESICAL',
        ])
        batch = ImportBatch.objects.create(usuario=self.user, archivo_nombre='practicas.xlsx')

        resultado = procesar_excel_eges(BytesIO(contenido), batch)

        self.assertEqual(resultado['creadas'], 3)
        self.assertEqual(EgesRow.objects.count(), 3)
        self.assertEqual(
            set(EgesRow.objects.values_list('practica', flat=True)),
            {'ECOGRAFIA ABDOMINAL', 'ECOGRAFIA RENAL', 'ECOGRAFIA VESICAL'},
        )

    def test_misma_practica_con_misma_identidad_real_se_deduplica(self):
        contenido = _archivo_practicas_mismo_protocolo_xlsx(['ECOGRAFIA ABDOMINAL'])
        primero = ImportBatch.objects.create(usuario=self.user, archivo_nombre='primero.xlsx')
        segundo = ImportBatch.objects.create(usuario=self.user, archivo_nombre='segundo.xlsx')

        resultado_primero = procesar_excel_eges(BytesIO(contenido), primero)
        resultado_segundo = procesar_excel_eges(BytesIO(contenido), segundo)

        self.assertEqual(resultado_primero['creadas'], 1)
        self.assertEqual(resultado_segundo['creadas'], 0)
        self.assertEqual(resultado_segundo['duplicadas'], 1)
        self.assertEqual(EgesRow.objects.count(), 1)

    def _crear_estudio_dashboard(self, batch, protocolo, fecha, modalidad, dni=None, practica=None):
        practica = practica or ('TRANSITO DE INTESTINO' if modalidad == 'SERIE' else f'PRACTICA {protocolo}')
        fila = EgesRow.objects.create(
            batch=batch,
            protocolo=protocolo,
            historia_clinica=protocolo,
            dni_paciente=dni,
            fecha_turno=fecha,
            centro_atencion='Sanatorio Colegiales',
            practica=practica,
            estado_turno='Informado',
            modalidad=modalidad,
            es_insumo=False,
            medico_informante='PROFESIONAL PRUEBA',
        )
        fila.modalidad = modalidad
        fila.save(update_fields=['modalidad'])
        return fila

    def test_kpis_separan_pacientes_practicas_y_excluyen_insumos(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.client.force_login(self.user)
        batch = ImportBatch.objects.create(usuario=self.user, archivo_nombre='kpis.xlsx')

        for numero, practica in enumerate(('ECO ABDOMEN', 'ECO RENAL', 'ECO VESICAL'), start=1):
            self._crear_estudio_dashboard(
                batch, f'ECO-A-{numero}', date(2026, 5, 10), 'ECO',
                dni='12.345.678', practica=practica,
            )
        self._crear_estudio_dashboard(
            batch, 'ECO-B-1', date(2026, 5, 10), 'ECO',
            dni='23456789', practica='ECO MAMARIA',
        )
        EgesRow.objects.create(
            batch=batch,
            historia_clinica='INSUMO-1',
            dni_paciente='99999999',
            fecha_turno=date(2026, 5, 10),
            centro_atencion='Sanatorio Colegiales',
            practica='GUANTES',
            estado_turno='Informado',
            modalidad='ECO',
            es_insumo=True,
        )

        data = self.client.get('/eges/datos/kpis/', {
            'fecha_desde': '2026-05-01',
            'fecha_hasta': '2026-05-31',
            'modalidades[]': 'ECO',
        }).json()

        self.assertEqual(data['pacientes_atendidos'], 2)
        self.assertEqual(data['practicas_realizadas'], 4)
        self.assertEqual(data['practicas_por_paciente'], 2.0)

    def test_kpis_respetan_modalidad_seleccionada(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.client.force_login(self.user)
        batch = ImportBatch.objects.create(usuario=self.user, archivo_nombre='modalidades.xlsx')
        self._crear_estudio_dashboard(batch, 'ECO-1', date(2026, 5, 10), 'ECO', dni='11111111')
        self._crear_estudio_dashboard(batch, 'TC-1', date(2026, 5, 10), 'TC', dni='22222222')

        eco = self.client.get('/eges/datos/kpis/', {'modalidades[]': 'ECO'}).json()
        tc = self.client.get('/eges/datos/kpis/', {'modalidades[]': 'TC'}).json()

        self.assertEqual(eco['pacientes_atendidos'], 1)
        self.assertEqual(eco['practicas_realizadas'], 1)
        self.assertEqual(tc['pacientes_atendidos'], 1)
        self.assertEqual(tc['practicas_realizadas'], 1)

    def _crear_comparativa(self, fecha, modalidad, practicas, pacientes=1, prefijo='P'):
        filas = []
        indice = 0
        for practica, cantidad in practicas.items():
            for _ in range(cantidad):
                dni = f'{prefijo}{indice % pacientes:03d}'
                filas.append(EgesRow(
                    batch=self.batch_comparativa,
                    historia_clinica=dni,
                    dni_paciente=dni,
                    fecha_turno=fecha,
                    centro_atencion='Centro test',
                    practica=practica,
                    estado_turno='Informado',
                    modalidad=modalidad,
                    es_insumo=False,
                ))
                indice += 1
        EgesRow.objects.bulk_create(filas)

    def _preparar_comparativa(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.client.force_login(self.user)
        self.batch_comparativa = ImportBatch.objects.create(
            usuario=self.user,
            archivo_nombre='comparativa-tests.xlsx',
        )
        return {
            'fecha_desde': '2026-05-01',
            'fecha_hasta': '2026-05-10',
        }

    def test_comparativa_calcula_pacientes_practicas_y_promedio(self):
        filtros = self._preparar_comparativa()
        self._crear_comparativa(date(2026, 5, 1), 'ECO', {'ECO ABDOMEN': 160}, pacientes=100, prefijo='A')
        self._crear_comparativa(date(2026, 4, 21), 'ECO', {'ECO ABDOMEN': 100}, pacientes=80, prefijo='B')

        data = self.client.get('/eges/datos/comparativa/', filtros).json()['comparativa']

        self.assertEqual(data['pacientes']['actual'], 100)
        self.assertEqual(data['pacientes']['anterior'], 80)
        self.assertEqual(data['pacientes']['absoluta'], 20)
        self.assertEqual(data['practicas']['absoluta'], 60)
        self.assertEqual(data['promedio_dia']['actual'], 160)
        self.assertEqual(data['promedio_dia']['anterior'], 100)
        self.assertEqual(data['practicas_por_paciente']['actual'], 1.6)
        self.assertEqual(data['practicas_por_paciente']['anterior'], 1.25)

    def test_hallazgos_director_informa_cambios_relevantes_y_acciones(self):
        filtros = self._preparar_comparativa()
        self._crear_comparativa(date(2026, 5, 1), 'ECO', {'ECO ABDOMEN': 160}, pacientes=100, prefijo='A')
        self._crear_comparativa(date(2026, 4, 21), 'ECO', {'ECO ABDOMEN': 100}, pacientes=80, prefijo='B')
        token = DirectorToken.objects.create(nombre_etiqueta='Test hallazgos')

        response = self.client.get(f'/eges/director/{token.token}/hallazgos/', filtros)

        self.assertEqual(response.status_code, 200)
        hallazgos = response.json()['hallazgos']
        self.assertLessEqual(len(hallazgos), 3)
        self.assertTrue(any('Prácticas realizadas aumentó +60,0%' in item['titulo'] for item in hallazgos))
        self.assertTrue(all(item['evidencia'] and item['accion'] for item in hallazgos))

    def test_comparativa_ordena_aumentos_y_disminuciones_por_diferencia(self):
        filtros = self._preparar_comparativa()
        self._crear_comparativa(date(2026, 5, 1), 'ECO', {'ECO ABDOMEN': 120, 'DOPPLER': 60})
        self._crear_comparativa(date(2026, 4, 21), 'ECO', {'ECO ABDOMEN': 100, 'DOPPLER': 80})
        data = self.client.get('/eges/datos/comparativa/', filtros).json()['comparativa']

        aumentos = {item['practica']: item for item in data['practicas_mayores_aumentos']}
        disminuciones = {item['practica']: item for item in data['practicas_mayores_disminuciones']}
        self.assertEqual(aumentos['ECO ABDOMEN']['absoluta'], 20)
        self.assertEqual(disminuciones['DOPPLER']['absoluta'], -20)

    def test_comparativa_identifica_practica_nueva_sin_division_por_cero(self):
        filtros = self._preparar_comparativa()
        self._crear_comparativa(date(2026, 5, 1), 'ECO', {'ECO NUEVA': 15})
        data = self.client.get('/eges/datos/comparativa/', filtros).json()['comparativa']

        nueva = next(item for item in data['practicas_mayores_aumentos'] if item['practica'] == 'ECO NUEVA')
        self.assertEqual(nueva['estado'], 'NUEVA')
        self.assertIsNone(nueva['porcentaje'])

    def test_comparativa_identifica_practica_desaparecida(self):
        filtros = self._preparar_comparativa()
        self._crear_comparativa(date(2026, 4, 21), 'ECO', {'ECO DESAPARECE': 20})
        data = self.client.get('/eges/datos/comparativa/', filtros).json()['comparativa']

        desaparecida = next(item for item in data['practicas_mayores_disminuciones'] if item['practica'] == 'ECO DESAPARECE')
        self.assertEqual(desaparecida['estado'], 'DESAPARECIO')
        self.assertEqual(desaparecida['absoluta'], -20)

    def test_comparativa_filtro_eco_no_incluye_tc(self):
        filtros = self._preparar_comparativa()
        filtros['modalidades[]'] = 'ECO'
        self._crear_comparativa(date(2026, 5, 1), 'ECO', {'ECO ABDOMEN': 2})
        self._crear_comparativa(date(2026, 5, 1), 'TC', {'TOMOGRAFIA': 20})
        data = self.client.get('/eges/datos/comparativa/', filtros).json()['comparativa']

        self.assertEqual(data['practicas']['actual'], 2)
        self.assertIsNone(data['bloqueos_tc'])

    def test_comparativa_informa_periodo_anterior_sin_actividad(self):
        filtros = self._preparar_comparativa()
        self._crear_comparativa(date(2026, 5, 1), 'ECO', {'ECO ABDOMEN': 2})
        data = self.client.get('/eges/datos/comparativa/', filtros).json()['comparativa']

        self.assertFalse(data['hay_datos_anterior'])
        self.assertEqual(data['practicas']['estado'], 'NUEVA')

    def test_comparativa_automatica_usa_ultimo_mes_disponible(self):
        self._preparar_comparativa()
        self._crear_comparativa(date(2026, 7, 15), 'TC', {'TOMOGRAFIA': 2})
        self._crear_comparativa(date(2026, 6, 15), 'TC', {'TOMOGRAFIA': 1})

        data = self.client.get('/eges/datos/comparativa/', {
            'modalidades[]': 'TC',
        }).json()

        self.assertEqual(data['modo_periodo'], 'automatico')
        self.assertEqual(data['periodo_actual'], {'desde': '01/07/2026', 'hasta': '31/07/2026'})
        self.assertEqual(data['periodo_anterior'], {'desde': '01/06/2026', 'hasta': '30/06/2026'})

    def test_comparativa_automatica_ancla_cada_modalidad_a_su_ultimo_mes(self):
        self._preparar_comparativa()
        self._crear_comparativa(date(2026, 5, 15), 'ECO', {'ECO ABDOMEN': 2})
        self._crear_comparativa(date(2026, 4, 15), 'ECO', {'ECO ABDOMEN': 1})
        self._crear_comparativa(date(2026, 7, 15), 'TC', {'TOMOGRAFIA': 2})
        self._crear_comparativa(date(2026, 6, 15), 'TC', {'TOMOGRAFIA': 1})

        eco = self.client.get('/eges/datos/comparativa/', {'modalidades[]': 'ECO'}).json()
        tc = self.client.get('/eges/datos/comparativa/', {'modalidades[]': 'TC'}).json()

        self.assertEqual(eco['periodo_actual']['desde'], '01/05/2026')
        self.assertEqual(eco['periodo_actual']['hasta'], '31/05/2026')
        self.assertEqual(tc['periodo_actual']['desde'], '01/07/2026')
        self.assertEqual(tc['periodo_actual']['hasta'], '31/07/2026')

    def test_comparativa_manual_conserva_rango_e_intervalo_anterior(self):
        self._preparar_comparativa()
        self._crear_comparativa(date(2026, 5, 10), 'ECO', {'ECO ABDOMEN': 2})
        self._crear_comparativa(date(2026, 4, 29), 'ECO', {'ECO ABDOMEN': 1})

        data = self.client.get('/eges/datos/comparativa/', {
            'fecha_desde': '2026-05-10',
            'fecha_hasta': '2026-05-20',
            'modalidades[]': 'ECO',
        }).json()

        self.assertEqual(data['modo_periodo'], 'manual')
        self.assertEqual(data['periodo_actual'], {'desde': '10/05/2026', 'hasta': '20/05/2026'})
        self.assertEqual(data['periodo_anterior'], {'desde': '29/04/2026', 'hasta': '09/05/2026'})

    def test_evolucion_no_agrega_meses_sin_datos(self):
        self._preparar_comparativa()
        self._crear_comparativa(date(2026, 7, 15), 'TC', {'TOMOGRAFIA': 2})

        data = self.client.get('/eges/datos/analisis-temporal/', {
            'modalidades[]': 'TC',
            'agrupacion': 'mes',
        }).json()

        self.assertEqual(data['labels'], ['07/2026'])

    def test_evolucion_obras_sociales_mantiene_rango_y_meses_sin_actividad(self):
        self._preparar_comparativa()
        for fecha, obra_social in (
            (date(2026, 1, 15), 'COBERTURA A'),
            (date(2026, 3, 15), 'COBERTURA A'),
            (date(2026, 2, 15), 'COBERTURA B'),
        ):
            EgesRow.objects.create(
                batch=self.batch_comparativa,
                historia_clinica=f'{obra_social}-{fecha}',
                fecha_turno=fecha,
                centro_atencion='Centro test',
                practica='ECO TEST',
                obra_social=obra_social,
                estado_turno='Informado',
                modalidad='ECO',
                es_insumo=False,
            )

        data = self.client.get('/eges/datos/obras-sociales/evolucion/', {
            'obras_sociales[]': ['COBERTURA A', 'COBERTURA B'],
        }).json()

        self.assertEqual(data['labels'], ['2026-01', '2026-02', '2026-03'])
        self.assertEqual(data['datasets'][0]['data'], [1, 0, 1])
        self.assertEqual(data['datasets'][1]['data'], [0, 1, 0])

    def test_dia_y_franja_conservan_conteos_tras_agregacion(self):
        self._preparar_comparativa()
        for indice, (fecha, hora) in enumerate([
            (date(2026, 5, 4), time(9, 0)),   # lunes, 08-10
            (date(2026, 5, 5), time(11, 0)),  # martes, 10-12
            (date(2026, 5, 4), time(9, 30)),  # lunes, 08-10
        ]):
            EgesRow.objects.create(
                batch=self.batch_comparativa,
                historia_clinica=f'DIA-{indice}',
                dni_paciente=f'DIA-{indice}',
                fecha_turno=fecha,
                hora_turno=hora,
                centro_atencion='Centro test',
                practica='ECO TEST',
                estado_turno='Informado',
                modalidad='ECO',
                es_insumo=False,
            )

        filtros = {'fecha_desde': '2026-05-01', 'fecha_hasta': '2026-05-31', 'modalidades[]': 'ECO'}
        dias = self.client.get('/eges/estadisticas/grafico-dia-semana/', filtros).json()
        franjas = self.client.get('/eges/estadisticas/grafico-franja-horaria/', filtros).json()

        self.assertEqual(dias['datasets'][0]['data'], [2, 1, 0, 0, 0, 0, 0])
        self.assertEqual(franjas['datasets'][0]['data'][4:6], [2, 1])

    def test_comparativa_respeta_modalidad_seleccionada(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.client.force_login(self.user)
        batch = ImportBatch.objects.create(usuario=self.user, archivo_nombre='comparativa.xlsx')
        actual_desde = date.today() - timedelta(days=9)
        actual_hasta = date.today()
        anterior_desde = actual_desde - timedelta(days=10)

        self._crear_estudio_dashboard(batch, 'TC-ACTUAL-1', actual_desde, 'TC')
        self._crear_estudio_dashboard(batch, 'TC-ACTUAL-2', actual_hasta, 'TC')
        self._crear_estudio_dashboard(batch, 'TC-ANTERIOR-1', anterior_desde, 'TC')
        for numero in range(5):
            self._crear_estudio_dashboard(batch, f'RM-ACTUAL-{numero}', actual_desde, 'RM')
            self._crear_estudio_dashboard(batch, f'RM-ANTERIOR-{numero}', anterior_desde, 'RM')

        response = self.client.get('/eges/datos/comparativa/', {
            'fecha_desde': actual_desde.isoformat(),
            'fecha_hasta': actual_hasta.isoformat(),
            'modalidades[]': 'TC',
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['actual']['total_finalizados'], 2)
        self.assertEqual(data['anterior']['total_finalizados'], 1)
        self.assertEqual(data['delta']['total_finalizados'], 100.0)

    def test_tendencia_y_productividad_incluyen_serie(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.client.force_login(self.user)
        batch = ImportBatch.objects.create(usuario=self.user, archivo_nombre='serie.xlsx')
        fila_serie = self._crear_estudio_dashboard(batch, 'SERIE-1', date.today(), 'SERIE')
        fila_serie.refresh_from_db()

        self.assertEqual(EgesRow.objects.filter(
            modalidad='SERIE', estado_turno__iexact='Informado', es_insumo=False,
        ).count(), 1, (fila_serie.modalidad, fila_serie.estado_turno, fila_serie.es_insumo))

        temporal = self.client.get('/eges/datos/analisis-temporal/').json()
        productividad = self.client.get('/eges/datos/productividad-medico/').json()

        self.assertIn('Seriografía', [dataset['label'] for dataset in temporal['datasets']])
        self.assertIn('Seriografía', [dataset['label'] for dataset in productividad['datasets']])

    def test_portal_director_separa_doppler_ecocardio_y_responsables(self):
        batch = ImportBatch.objects.create(usuario=self.user, archivo_nombre='doppler-ecocardio.xlsx')
        doppler_mayo = self._crear_estudio_dashboard(
            batch, 'DOP-MAYO', date(2026, 5, 10), 'ECO', practica='DOPPLER CAROTIDEO',
        )
        doppler_junio = self._crear_estudio_dashboard(
            batch, 'DOP-JUNIO', date(2026, 6, 10), 'ECO', practica='DOPPLER VENOSO',
        )
        ecocardio_junio = self._crear_estudio_dashboard(
            batch, 'ECOCAR-JUNIO', date(2026, 6, 11), 'ECO', practica='ECODOPPLER CARDIACO',
        )
        for fila, sub_modalidad, medico in (
            (doppler_mayo, 'DOPPLER', 'DRA DOPPLER'),
            (doppler_junio, 'DOPPLER', 'DRA DOPPLER'),
            (ecocardio_junio, 'ECOCARDIO', 'DR CARDIO'),
        ):
            fila.sub_modalidad = sub_modalidad
            fila.medico_informante = medico
            fila.save(update_fields=['sub_modalidad', 'medico_informante'])

        token = DirectorToken.objects.create(nombre_etiqueta='Test Doppler')
        response = self.client.get(f'/eges/director/{token.token}/doppler-ecocardio/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['evolucion']['labels'], ['2026-05', '2026-06'])
        self.assertEqual(data['evolucion']['datasets'][0]['data'], [1, 1])
        self.assertEqual(data['evolucion']['datasets'][1]['data'], [0, 1])
        self.assertEqual(data['responsables']['labels'], ['DRA DOPPLER', 'DR CARDIO'])
        self.assertEqual(data['responsables']['datasets'][0]['data'], [2, 0])
        self.assertEqual(data['responsables']['datasets'][1]['data'], [0, 1])

    def test_portal_director_guardias_cuenta_solo_guardias_por_modalidad(self):
        batch = ImportBatch.objects.create(usuario=self.user, archivo_nombre='guardias.xlsx')
        guardia_eco = self._crear_estudio_dashboard(batch, 'GUARDIA-ECO', date(2026, 5, 10), 'ECO')
        guardia_tc = self._crear_estudio_dashboard(batch, 'GUARDIA-TC', date(2026, 6, 10), 'TC')
        ambulatorio = self._crear_estudio_dashboard(batch, 'AMB-ECO', date(2026, 6, 11), 'ECO')
        for fila, tipo_atencion in (
            (guardia_eco, 'Guardia'),
            (guardia_tc, 'Guardia'),
            (ambulatorio, 'Ambulatorio'),
        ):
            fila.tipo_atencion = tipo_atencion
            fila.save(update_fields=['tipo_atencion'])

        token = DirectorToken.objects.create(nombre_etiqueta='Test guardias')
        response = self.client.get(f'/eges/director/{token.token}/guardias/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_guardia'], 2)
        self.assertEqual(data['porcentaje_sobre_total'], 66.7)
        self.assertEqual(data['labels'], ['2026-05', '2026-06'])
        self.assertEqual([item['label'] for item in data['datasets']], ['Tomografía Computada', 'Ecografía'])
        self.assertEqual(data['datasets'][0]['data'], [0, 1])
        self.assertEqual(data['datasets'][1]['data'], [1, 0])

    def test_dashboard_advierte_lote_con_posible_tope_eges(self):
        self.user.is_superuser = True
        self.user.save(update_fields=['is_superuser'])
        self.client.force_login(self.user)
        ImportBatch.objects.create(
            usuario=self.user,
            archivo_nombre='Atendidos-mayo-ECO.xls',
            total_filas=1000,
        )

        response = self.client.get('/eges/estadisticas/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['lotes_posible_tope'], 1)
        self.assertContains(response, 'podrían haber alcanzado el límite')
