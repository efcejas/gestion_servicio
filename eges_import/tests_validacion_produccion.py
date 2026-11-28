import json
from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse

from .models import ProduccionValidada
from .services_validacion_produccion import preparar_validacion_produccion, confirmar_produccion
from .tests_produccion import FuentesSinteticasMixin


class ProteccionesProcedimientosTest(SimpleTestCase):
    def test_documento_alternativo_con_nombre_igual_reconoce_paciente(self):
        from types import SimpleNamespace
        from .services_estadisticas import _identidades_netterm
        from .services_conciliacion import _paciente_clave
        eges = {1: SimpleNamespace(dni_paciente='12345678', apellido_nombre='PRUEBA, ANA')}
        nt = {2: {'tipo_documento': 'L.C.', 'documento': '12345678', 'paciente': 'ANA PRUEBA'}}
        self.assertEqual(_identidades_netterm(eges, nt)[2], _paciente_clave('12345678'))
        nt[2]['paciente'] = 'OTRA PERSONA'
        self.assertIsNone(_identidades_netterm(eges, nt)[2])

    def test_historia_clinica_netterm_reconoce_identidad_y_rechaza_conflictos(self):
        from .services_estadisticas import _identidades_netterm
        from .services_conciliacion import _paciente_clave
        nt = {1: {'tipo_documento': 'DNI', 'documento': '12345678', 'historia_clinica': 'HC001'},
              2: {'historia_clinica': 'HC001'}}
        self.assertEqual(_identidades_netterm({}, nt)[2], _paciente_clave('12345678'))
        nt[3] = {'tipo_documento': 'DNI', 'documento': '87654321', 'historia_clinica': 'HC001'}
        self.assertIsNone(_identidades_netterm({}, nt)[2])

    def test_documentos_alternativos_y_hc_sin_documento_tienen_claves_privadas(self):
        from .services_estadisticas import _identidades_netterm
        nt = {1: {'tipo_documento': 'LC', 'documento': '00123456'},
              2: {'tipo_documento': 'L.C.', 'documento': '123456'},
              3: {'historia_clinica': 'HC002'}, 4: {'historia_clinica': 'HC002'}}
        claves = _identidades_netterm({}, nt)
        self.assertTrue(claves[1])
        self.assertEqual(claves[1], claves[2])
        self.assertTrue(claves[3])
        self.assertEqual(claves[3], claves[4])
        self.assertNotIn('123456', claves[1])

    def test_identificacion_no_usa_hc_o_documentos_cero(self):
        from .services_estadisticas import _identidades_netterm
        nt = {1: {'tipo_documento': 'LC', 'documento': '000', 'historia_clinica': '0'}}
        self.assertIsNone(_identidades_netterm({}, nt)[1])

    def test_componente_ambiguo_conserva_revision_individual(self):
        from .services_procedimientos import completar_decisiones_procedimientos
        grupo = self.grupo()
        grupo['candidatas_componentes'] = {'2': [10, 11]}
        decisiones = completar_decisiones_procedimientos(
            [grupo], {'2'}, {'procedimiento:qa': {'accion': 'UNICO'}},
        )
        self.assertNotIn('2', decisiones)
    def grupo(self):
        return {'id': 'procedimiento:qa', 'filas_ids': [1, 2], 'componentes_ids': [2],
                'principales_ids': [1], 'candidatas_componentes': {'2': []},
                'candidatas_principales': {'1': []}}

    def test_unico_requiere_principal_aceptada(self):
        from .services_procedimientos import aplicar_decisiones_procedimientos
        componente = {'fila': {'id': 2, 'fecha_pedido': date(2026, 10, 1)}}
        with self.assertRaises(ValidationError):
            aplicar_decisiones_procedimientos([componente], [self.grupo()], {'procedimiento:qa': {'accion': 'UNICO'}})

    def test_solo_marca_la_principal_eges_elegida(self):
        from .services_procedimientos import aplicar_decisiones_procedimientos
        grupo = self.grupo()
        grupo['candidatas_principales'] = {'1': [10, 11]}
        elegida = {'fila': {'id': 10, 'fecha_turno': date(2026, 10, 1)}, 'netterm': {'id': 1}}
        otra = {'fila': {'id': 11, 'fecha_turno': date(2026, 10, 1)}}
        resultado, _ = aplicar_decisiones_procedimientos(
            [elegida, otra], [grupo], {'procedimiento:qa': {'accion': 'UNICO'}, '1': {'accion': 'VINCULAR:10'}},
        )
        self.assertEqual(len(resultado), 2)
        self.assertTrue(elegida['procedimiento_guiado'])
        self.assertNotIn('procedimiento_guiado', otra)


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
class ValidacionProduccionTest(FuentesSinteticasMixin, TestCase):
    def seleccion(self):
        return dict(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk],
                    fecha_desde=date(2026, 10, 1), fecha_hasta=date(2026, 10, 31))

    def parametros(self):
        return {'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk],
                'fecha_desde': '2026-10-01', 'fecha_hasta': '2026-10-31'}

    def confirmar(self, decisiones=None):
        preparacion = preparar_validacion_produccion(**self.seleccion())
        return confirmar_produccion(**self.seleccion(), usuario=self.usuario,
                                    firma_esperada=preparacion['firma'], decisiones=decisiones or {})

    def test_claros_automaticos_se_confirman_sin_revision_individual(self):
        self.eges()
        self.netterm()
        self.netterm(pedido='2', documento='87654321')
        preparacion = preparar_validacion_produccion(**self.seleccion())
        self.assertEqual(preparacion['automaticas'], 2)
        self.assertEqual(preparacion['excepciones'], [])
        validacion = self.confirmar()
        self.assertEqual(validacion.resultado_json['total_produccion'], 2)
        self.assertEqual(validacion.resultado_json['aporte_netterm'], 1)
        self.assertEqual(self.confirmar().pk, validacion.pk)

    def test_doppler_bilateral_confirmado_cuenta_una_practica_y_preserva_origen(self):
        from .models import NettermFila
        for pedido in ('1', '2'):
            self.netterm(pedido=pedido, codigo='900048', practica='ECODOPPLER VENOSO MM INF')
        preparacion = preparar_validacion_produccion(**self.seleccion())
        self.assertEqual(len(preparacion['grupos_bilaterales']), 1)
        grupo = preparacion['grupos_bilaterales'][0]
        with self.assertRaises(ValidationError):
            self.confirmar()
        validacion = self.confirmar({grupo['id']: {'accion': 'UNICO'}})
        self.assertEqual(validacion.resultado_json['total_produccion'], 1)
        self.assertEqual(validacion.resultado_json['pacientes_unicos_identificables'], 1)
        self.assertEqual(NettermFila.objects.count(), 2)
        self.assertEqual(validacion.resultado_json['agrupaciones_bilaterales'][0]['practicas_antes'], 2)

    def test_doppler_independientes_conserva_dos_practicas(self):
        for pedido in ('1', '2'):
            self.netterm(pedido=pedido, codigo='900048', practica='ECODOPPLER VENOSO DE MIEMBRO INFERIOR')
        grupo = preparar_validacion_produccion(**self.seleccion())['grupos_bilaterales'][0]
        validacion = self.confirmar({grupo['id']: {'accion': 'INDEPENDIENTES'}})
        self.assertEqual(validacion.resultado_json['total_produccion'], 2)

    def test_arterial_y_venoso_bilaterales_suman_dos(self):
        for codigo, nombre in [('900046', 'ECODOPPLER ARTERIAL MMII'), ('900048', 'ECODOPPLER VENOSO MMII')]:
            for indice in (1, 2):
                self.netterm(pedido=f'{codigo}-{indice}', codigo=codigo, practica=nombre)
        grupos = preparar_validacion_produccion(**self.seleccion())['grupos_bilaterales']
        self.assertEqual(len(grupos), 2)
        validacion = self.confirmar({grupo['id']: {'accion': 'UNICO'} for grupo in grupos})
        self.assertEqual(validacion.resultado_json['total_produccion'], 2)

    def test_doppler_de_dias_distintos_se_conservan(self):
        self.netterm(pedido='1', codigo='900048', practica='ECODOPPLER VENOSO MM INF')
        self.netterm(pedido='2', codigo='900048', practica='ECODOPPLER VENOSO MM INF',
                     fecha_realizacion=date(2026, 10, 11))
        self.assertEqual(preparar_validacion_produccion(**self.seleccion())['grupos_bilaterales'], [])
        self.assertEqual(self.confirmar().resultado_json['total_produccion'], 2)

    def test_grupo_con_libreta_civica_y_excepciones_de_identidad(self):
        for pedido in ('1', '2'):
            self.netterm(pedido=pedido, codigo='900048', practica='ECODOPPLER VENOSO MM INF', tipo_documento='L.C.')
        preparacion = preparar_validacion_produccion(**self.seleccion())
        decisiones = {item['id']: {'accion': 'ADICIONAL', 'modalidad': 'ECO'} for item in preparacion['excepciones']}
        decisiones[preparacion['grupos_bilaterales'][0]['id']] = {'accion': 'UNICO'}
        self.assertEqual(self.confirmar(decisiones).resultado_json['total_produccion'], 1)

    def test_interfaz_muestra_grupos_bilaterales(self):
        for pedido in ('1', '2'):
            self.netterm(pedido=pedido, codigo='900048', practica='ECODOPPLER VENOSO MM INF')
        self.client.force_login(self.usuario)
        response = self.client.get(reverse('eges_import:validar_produccion'), self.parametros())
        self.assertContains(response, 'Representan un único estudio')
        self.assertContains(response, 'Son estudios independientes')

    def cargar_procedimiento(self, pedido='1'):
        for codigo, practica in (
            ('900079', 'PUNCION BIOPSIA BAJO CTROL.ECOGRAFICO'),
            ('150101', 'BIOPSIA POR INCISION O PUNCION'),
            ('150111', 'CITOLOGIA EXFOLIATIVA ONCOLOGICA DE LIQUIDOS'),
        ):
            self.netterm(pedido=pedido, codigo=codigo, practica=practica)

    def test_procedimiento_ecoguiado_retira_componentes_de_ambas_fuentes(self):
        from .models import EgesRow, NettermFila
        self.cargar_procedimiento()
        for codigo, practica in (
            ('900079', 'PUNCION BIOPSIA BAJO CTROL.ECOGRAFICO'),
            ('150101', 'BIOPSIA POR INCISION O PUNCION'),
            ('150111', 'CITOLOGIA EXFOLIATIVA DE LIQUIDOS'),
        ):
            self.eges(codigo_practica=codigo, practica=practica, servicio='Ecografia')
        preparacion = preparar_validacion_produccion(**self.seleccion())
        self.assertEqual(len(preparacion['grupos_procedimientos']), 1)
        decisiones = {item['id']: {'accion': 'EXCLUIR'} for item in preparacion['excepciones']}
        grupo = preparacion['grupos_procedimientos'][0]
        decisiones[grupo['id']] = {'accion': 'UNICO'}
        resultado = self.confirmar(decisiones).resultado_json
        self.assertEqual(resultado['total_produccion'], 1)
        self.assertEqual(resultado['pacientes_unicos_identificables'], 1)
        self.assertTrue(resultado['practicas'][0]['procedimiento_guiado'])
        self.assertEqual(EgesRow.objects.count(), 3)
        self.assertEqual(NettermFila.objects.count(), 3)
        self.assertEqual(resultado['agrupaciones_procedimientos'][0]['componentes_retirados_del_conteo'], 2)

    def test_decision_grupal_resuelve_componentes_sin_modalidad_individual(self):
        self.cargar_procedimiento()
        preparacion = preparar_validacion_produccion(**self.seleccion())
        grupo = preparacion['grupos_procedimientos'][0]
        validacion = self.confirmar({grupo['id']: {'accion': 'UNICO'}})
        self.assertEqual(validacion.resultado_json['total_produccion'], 1)
        for componente in grupo['componentes_ids']:
            self.assertEqual(validacion.decisiones_json[str(componente)], {'accion': 'EXCLUIR'})
        decisiones_redundantes = {grupo['id']: {'accion': 'UNICO'}}
        decisiones_redundantes.update({item['id']: {'accion': 'ADICIONAL', 'modalidad': 'ECO'}
                                       for item in preparacion['excepciones']})
        self.assertEqual(self.confirmar(decisiones_redundantes).pk, validacion.pk)

    def test_procedimientos_de_pedidos_distintos_conservan_sus_unidades(self):
        self.cargar_procedimiento(pedido='1')
        self.cargar_procedimiento(pedido='2')
        preparacion = preparar_validacion_produccion(**self.seleccion())
        self.assertEqual(len(preparacion['grupos_procedimientos']), 2)
        decisiones = {item['id']: {'accion': 'ADICIONAL', 'modalidad': 'ECO'} for item in preparacion['excepciones']}
        decisiones.update({grupo['id']: {'accion': 'UNICO'} for grupo in preparacion['grupos_procedimientos']})
        self.assertEqual(self.confirmar(decisiones).resultado_json['total_produccion'], 2)

    def test_componentes_sin_puncion_guiada_conservan_revision_individual(self):
        self.netterm(codigo='150101', practica='BIOPSIA POR INCISION O PUNCION')
        preparacion = preparar_validacion_produccion(**self.seleccion())
        self.assertEqual(preparacion['grupos_procedimientos'], [])
        self.assertEqual(len(preparacion['excepciones']), 1)

    def test_interfaz_de_procedimientos_y_subclasificacion_estadistica(self):
        self.cargar_procedimiento()
        self.client.force_login(self.usuario)
        url = reverse('eges_import:validar_produccion')
        response = self.client.get(url, self.parametros())
        self.assertContains(response, 'Revisar procedimientos guiados')
        preparacion = response.context['preparacion']
        decisiones = {item['id']: {'accion': 'EXCLUIR'} for item in preparacion['excepciones']}
        decisiones.update({grupo['id']: {'accion': 'UNICO'} for grupo in preparacion['grupos_procedimientos']})
        validacion = self.confirmar(decisiones)
        datos = self.client.get(reverse('eges_import:estadisticas_fuentes_data'), {
            **self.parametros(), 'validacion': validacion.pk,
        })
        self.assertEqual(datos.status_code, 200)
        self.assertEqual(datos.json()['sub_eco']['labels'], ['Procedimientos intervencionistas ecoguiados'])
        self.assertEqual(datos.json()['sub_eco']['datasets'][0]['data'], [1])

    def test_ecoestrés_archivado_se_reclasifica_y_conserva_practica_independiente(self):
        self.eges(codigo_practica='180304', practica='ECOESTRESS CON EJERCICIO')
        self.eges(codigo_practica='900009', practica='ECODOPPLER CARDIACO')
        fila = self.netterm(codigo='180304', practica='ECOESTRESS CON EJERCICIO',
                            modalidad_original='SIN_CLASIFICAR')
        self.netterm(pedido='2', codigo='900009', practica='ECODOPPLER CARDIACO')
        preparacion = preparar_validacion_produccion(**self.seleccion())
        self.assertEqual(preparacion['excepciones'], [])
        validacion = self.confirmar()
        self.assertEqual(validacion.resultado_json['total_produccion'], 2)
        self.assertEqual(validacion.resultado_json['pacientes_unicos_identificables'], 1)
        fila.refresh_from_db()
        self.assertEqual(fila.normalizados_json['modalidad'], 'SIN_CLASIFICAR')
        self.client.force_login(self.usuario)
        datos = self.client.get(reverse('eges_import:estadisticas_fuentes_data'), {
            **self.parametros(), 'validacion': validacion.pk,
        })
        self.assertEqual(datos.json()['sub_eco']['datasets'][0]['data'], [2])

    def test_ecoestrés_exclusivo_netterm_aparece_en_ecocardio(self):
        self.netterm(codigo='180304', practica='ECOESTRESS CON EJERCICIO',
                     modalidad_original='SIN_CLASIFICAR')
        validacion = self.confirmar()
        self.client.force_login(self.usuario)
        datos = self.client.get(reverse('eges_import:estadisticas_fuentes_data'), {
            **self.parametros(), 'validacion': validacion.pk,
        }).json()
        self.assertEqual(datos['kpis']['practicas_realizadas'], 1)
        self.assertEqual(datos['sub_eco']['labels'], ['Ecocardiograma'])
        self.assertEqual(datos['sub_eco']['datasets'][0]['data'], [1])

    def test_rechaza_confirmar_excepciones_sin_decision(self):
        self.eges()
        self.eges(hora_turno='11:00')
        self.netterm()
        with self.assertRaises(ValidationError):
            self.confirmar()
        self.assertFalse(ProduccionValidada.objects.exists())

    def test_vincular_no_elimina_otras_practicas_eges(self):
        primera = self.eges()
        self.eges(hora_turno='11:00')
        fila = self.netterm()
        grupo = preparar_validacion_produccion(**self.seleccion())['grupos_repeticiones'][0]['id']
        validacion = self.confirmar({str(fila.pk): {'accion': f'VINCULAR:{primera.pk}', 'modalidad': 'ECO'},
                                    grupo: {'accion': 'INDEPENDIENTES'}})
        self.assertEqual(validacion.resultado_json['total_produccion'], 2)
        self.assertEqual(validacion.resultado_json['aporte_netterm'], 0)

    def test_aprobacion_conjunta_adicional_y_exclusion(self):
        self.eges()
        self.eges(hora_turno='11:00')
        primera = self.netterm()
        segunda = self.netterm(pedido='2')
        grupo = preparar_validacion_produccion(**self.seleccion())['grupos_repeticiones'][0]['id']
        validacion = self.confirmar({
            str(primera.pk): {'accion': 'ADICIONAL', 'modalidad': 'ECO'},
            str(segunda.pk): {'accion': 'EXCLUIR'},
            grupo: {'accion': 'INDEPENDIENTES'},
        })
        self.assertEqual(validacion.resultado_json['total_produccion'], 3)
        self.assertEqual(len(validacion.decisiones_json), 3)

    def test_vinculaciones_competidoras_se_rechazan_atomicamente(self):
        eges = self.eges()
        primera = self.netterm()
        segunda = self.netterm(pedido='2')
        with self.assertRaises(ValidationError):
            self.confirmar({str(fila.pk): {'accion': f'VINCULAR:{eges.pk}', 'modalidad': 'ECO'}
                            for fila in (primera, segunda)})
        self.assertFalse(ProduccionValidada.objects.exists())

    def test_fuentes_modificadas_requieren_revisar(self):
        self.eges()
        self.netterm()
        preparacion = preparar_validacion_produccion(**self.seleccion())
        self.netterm(pedido='2', documento='87654321')
        with self.assertRaises(ValidationError):
            confirmar_produccion(**self.seleccion(), usuario=self.usuario,
                                 firma_esperada=preparacion['firma'], decisiones={})

    def test_recorrido_http_publica_y_dashboard_pdf_usan_version_aprobada(self):
        self.eges()
        self.netterm()
        self.client.force_login(self.usuario)
        url = reverse('eges_import:validar_produccion')
        consulta = self.client.get(url, self.parametros())
        self.assertContains(consulta, 'Confirmar producción y actualizar gráficos')
        preparacion = consulta.context['preparacion']
        post = self.client.post(url, {**self.parametros(), 'firma': preparacion['firma'], 'decisiones_json': '{}'})
        self.assertEqual(post.status_code, 302)
        validacion = ProduccionValidada.objects.get()
        parametros = {**self.parametros(), 'validacion': validacion.pk}
        datos = self.client.get(reverse('eges_import:estadisticas_fuentes_data'), parametros)
        self.assertEqual(datos.status_code, 200)
        self.assertEqual(datos.json()['kpis']['practicas_realizadas'], 1)
        self.assertNotContains(datos, '12345678')
        pdf = self.client.get(reverse('eges_import:exportar_pdf_fuentes'), parametros)
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF-'))
        self.assertEqual(self.client.get(reverse('eges_import:estadisticas')).status_code, 200)

    def test_graficos_bloquean_netterm_sin_confirmacion(self):
        self.eges()
        self.netterm()
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse('eges_import:estadisticas_fuentes_data'), self.parametros()).status_code, 400)
        self.assertEqual(self.client.get(reverse('eges_import:exportar_pdf_fuentes'), self.parametros()).status_code, 400)

    def test_resumen_final_calcula_sin_guardar_ni_modificar_fuentes(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.eges()
        self.netterm()
        self.client.force_login(self.usuario)
        preparacion = preparar_validacion_produccion(**self.seleccion())
        with CaptureQueriesContext(connection) as consultas:
            response = self.client.post(reverse('eges_import:validar_produccion'), {
                **self.parametros(), 'accion': 'resumen', 'firma': preparacion['firma'], 'decisiones_json': '{}',
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total_produccion'], 1)
        self.assertEqual(response.json()['pacientes_unicos_identificables'], 1)
        self.assertFalse(ProduccionValidada.objects.exists())
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for q in consultas))

    def test_dashboard_agrega_historico_eges_a_periodo_confirmado(self):
        from .models import ImportBatch
        self.eges()
        self.netterm()
        validacion = self.confirmar()
        historico = ImportBatch.objects.create(usuario=self.usuario, archivo_nombre='junio.xls')
        self.eges(batch=historico, fecha_turno=date(2026, 6, 10))
        self.client.force_login(self.usuario)
        response = self.client.get(reverse('eges_import:estadisticas_fuentes_data'), {
            'lotes_eges': [self.batch.pk, historico.pk], 'lotes_netterm': [self.lote.pk],
            'validacion': validacion.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['kpis']['practicas_realizadas'], 2)
        self.assertEqual(response.json()['temporal']['labels'], ['06/2026', '10/2026'])
        self.assertTrue(response.json()['metadatos']['historico_eges'])
        validacion.refresh_from_db()
        self.assertEqual(validacion.resultado_json['total_produccion'], 1)

    def test_dashboard_requiere_validacion_para_lote_agregado_del_mismo_periodo(self):
        from .models import ImportBatch
        self.eges()
        self.netterm()
        validacion = self.confirmar()
        adicional = ImportBatch.objects.create(usuario=self.usuario, archivo_nombre='octubre_extra.xls')
        self.eges(batch=adicional)
        self.client.force_login(self.usuario)
        response = self.client.get(reverse('eges_import:estadisticas_fuentes_data'), {
            **self.parametros(), 'lotes_eges': [self.batch.pk, adicional.pk], 'validacion': validacion.pk,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('período aprobado', response.json()['error'])

    def test_resumen_rechaza_decisiones_incompletas(self):
        self.eges()
        self.eges(hora_turno='11:00')
        self.netterm()
        self.client.force_login(self.usuario)
        preparacion = preparar_validacion_produccion(**self.seleccion())
        response = self.client.post(reverse('eges_import:validar_produccion'), {
            **self.parametros(), 'accion': 'resumen', 'firma': preparacion['firma'], 'decisiones_json': '{}',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        self.assertFalse(ProduccionValidada.objects.exists())

    def test_formulario_excepciones_renderiza_y_rechaza_post_incompleto(self):
        self.eges()
        self.eges(hora_turno='11:00')
        self.netterm()
        self.client.force_login(self.usuario)
        url = reverse('eges_import:validar_produccion')
        consulta = self.client.get(url, self.parametros())
        self.assertContains(consulta, 'Seleccionar todas las excepciones')
        response = self.client.post(url, {**self.parametros(), 'firma': consulta.context['preparacion']['firma'],
                                          'decisiones_json': json.dumps({})})
        self.assertContains(response, 'Resolvé todas las excepciones')
        self.assertFalse(ProduccionValidada.objects.exists())

    def test_confirmacion_y_pantalla_restringidas_a_administracion(self):
        self.usuario.is_superuser = False
        self.usuario.save()
        with self.assertRaises(ValidationError):
            self.confirmar()
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(reverse('eges_import:validar_produccion')).status_code, 302)
