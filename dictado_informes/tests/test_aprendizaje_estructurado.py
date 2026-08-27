import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from dictado_informes.learning_services import registrar_evento_aprendizaje
from dictado_informes.models import (
    CorreccionAprendizaje,
    EventoAprendizajeDictado,
    PlantillaEstructurada,
    PreferenciaAprendidaDictado,
)
from dictado_informes.views import priorizar_preferencia_aprendida


User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver', 'localhost'])
class TestMemoriaEstructurada(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin_memoria',
            password='admin123',
        )

    def confirmar(self, codigo='RODILLA_GENERAL'):
        return registrar_evento_aprendizaje(
            usuario=self.user,
            tipo_evento=EventoAprendizajeDictado.TipoEvento.PLANTILLA_CONFIRMADA,
            modo_dictado='AGENTE',
            region='RODILLA',
            modalidad='RM',
            lateralidad='DERECHA',
            plantilla_propuesta_codigo='RODILLA_GENERAL',
            plantilla_confirmada_codigo=codigo,
        )

    def test_preferencia_nace_candidata_y_se_activa_con_tres_confirmaciones(self):
        self.confirmar()
        preferencia = PreferenciaAprendidaDictado.objects.get(vigente=True)
        self.assertEqual(preferencia.estado, PreferenciaAprendidaDictado.Estado.CANDIDATA)
        self.assertEqual(preferencia.confirmaciones, 1)

        self.confirmar()
        self.confirmar()
        preferencia.refresh_from_db()

        self.assertEqual(preferencia.estado, PreferenciaAprendidaDictado.Estado.ACTIVA)
        self.assertEqual(preferencia.confirmaciones, 3)
        self.assertEqual(preferencia.confianza, 1.0)

    def test_cambio_sostenido_crea_una_version_y_conserva_historial(self):
        for _ in range(3):
            self.confirmar()
        for _ in range(10):
            self.confirmar('RODILLA_MENISCAL')

        versiones = list(PreferenciaAprendidaDictado.objects.order_by('version'))
        self.assertEqual(len(versiones), 2)
        self.assertFalse(versiones[0].vigente)
        self.assertEqual(versiones[0].estado, PreferenciaAprendidaDictado.Estado.REEMPLAZADA)
        self.assertTrue(versiones[1].vigente)
        self.assertEqual(versiones[1].version, 2)
        self.assertEqual(versiones[1].valor['codigo_plantilla'], 'RODILLA_MENISCAL')
        self.assertEqual(versiones[1].reemplaza_a, versiones[0])

    def test_contexto_sin_region_se_audita_pero_no_activa_memoria(self):
        registrar_evento_aprendizaje(
            usuario=self.user,
            tipo_evento=EventoAprendizajeDictado.TipoEvento.PLANTILLA_CONFIRMADA,
            plantilla_confirmada_codigo='GENERAL',
        )

        self.assertEqual(EventoAprendizajeDictado.objects.count(), 1)
        self.assertFalse(PreferenciaAprendidaDictado.objects.exists())

    def test_memoria_activa_prioriza_candidata_sin_saltar_confirmacion_humana(self):
        PlantillaEstructurada.objects.create(
            codigo='RODILLA_MENISCAL',
            nombre='RM de rodilla meniscal',
            titulo='RM DE RODILLA',
            seccion_tecnica='Tecnica habitual.',
            comentarios_base=['Meniscos conservados.'],
            creada_por=self.user,
            origen='user',
        )
        for _ in range(3):
            self.confirmar('RODILLA_MENISCAL')

        candidatos, codigo = priorizar_preferencia_aprendida(
            [{'codigo': 'RODILLA_GENERAL', 'nombre': 'RM de rodilla general'}],
            {'region': 'RODILLA', 'modalidad': 'RM', 'lateralidad': 'DERECHA'},
            self.user,
        )

        self.assertEqual(codigo, 'RODILLA_MENISCAL')
        self.assertEqual(candidatos[0]['codigo'], 'RODILLA_MENISCAL')
        self.assertTrue(candidatos[0]['desde_preferencia_aprendida'])

    def test_ejemplos_se_aislan_por_plantilla(self):
        for plantilla, termino in (
            ('RODILLA', 'menisco medial'),
            ('CEREBRO', 'sustancia blanca'),
        ):
            CorreccionAprendizaje.objects.create(
                usuario=self.user,
                tipo_plantilla=plantilla,
                texto_original='Texto original suficientemente claro.',
                texto_ia='Se observa una alteracion focal de señal.',
                texto_final=f'Se observa una alteracion focal de {termino}.',
                cambios_detectados=[{
                    'tipo': 'reemplazo',
                    'de': 'señal',
                    'a': termino,
                    'categoria': 'terminologia',
                    'score': 85,
                }],
            )

        ejemplos = CorreccionAprendizaje.obtener_ejemplos_aprendizaje(
            usuario=self.user,
            limite=10,
            tipo_plantilla='RODILLA',
        )

        self.assertIn('menisco medial', ejemplos)
        self.assertNotIn('sustancia blanca', ejemplos)


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver', 'localhost'])
class TestEventosAprendizajeAPI(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin_eventos',
            password='admin123',
        )
        self.client = Client()
        self.client.login(username='admin_eventos', password='admin123')

    @patch('dictado_informes.ai_services.AIService.edit_medical_report')
    def test_correccion_por_voz_y_deshacer_quedan_vinculadas(self, mock_edit):
        mock_edit.return_value = {
            'texto_editado': 'COMENTARIO\nDerrame moderado.',
            'operaciones_aplicadas': [{'tipo': 'reemplazar'}],
            'resumen_cambios': ['Cambio aplicado.'],
        }
        response = self.client.post(
            reverse('dictado_informes:corregir_borrador'),
            data=json.dumps({
                'texto_actual': 'COMENTARIO\nDerrame leve.',
                'instruccion': 'Cambiar la cuantia.',
                'modo_dictado': 'AGENTE',
                'tipo_plantilla': 'RODILLA',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        evento_id = response.json()['evento_aprendizaje_id']
        evento = EventoAprendizajeDictado.objects.get(pk=evento_id)
        self.assertEqual(evento.tipo_operacion, 'reemplazar')
        self.assertNotIn('Derrame', json.dumps(evento.metadatos))

        undo = self.client.post(
            reverse('dictado_informes:deshacer_correccion'),
            data=json.dumps({'evento_id': evento_id}),
            content_type='application/json',
        )

        self.assertEqual(undo.status_code, 200)
        evento.refresh_from_db()
        self.assertTrue(evento.revertido)
        self.assertTrue(EventoAprendizajeDictado.objects.filter(
            tipo_evento=EventoAprendizajeDictado.TipoEvento.CORRECCION_VOZ_DESHECHA,
        ).exists())

    def test_feedback_crea_evento_sin_copiar_el_informe(self):
        response = self.client.post(
            reverse('dictado_informes:feedback_calidad'),
            data=json.dumps({
                'estado_feedback': 'correcto',
                'texto_ia': 'Texto clinico reservado.',
                'texto_final': 'Texto clinico reservado.',
                'modo_dictado': 'AGENTE',
                'tipo_estudio': 'RES',
                'tipo_plantilla': 'RODILLA',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        evento = EventoAprendizajeDictado.objects.get()
        self.assertEqual(evento.tipo_evento, EventoAprendizajeDictado.TipoEvento.INFORME_ACEPTADO)
        self.assertEqual(evento.modo_dictado, 'AGENTE')
        self.assertNotIn('clinico', json.dumps(evento.metadatos).lower())

    def test_correccion_manual_guarda_contexto_de_plantilla(self):
        response = self.client.post(
            reverse('dictado_informes:guardar_aprendizaje'),
            data=json.dumps({
                'texto_original': 'Informe de rodilla derecha.',
                'texto_ia': 'Menisco interno conservado.',
                'texto_final': 'Menisco medial conservado.',
                'tipo_estudio': 'RES',
                'modo_dictado': 'AGENTE',
                'tipo_plantilla': 'RODILLA',
                'contexto_clinico': {
                    'region': 'RODILLA',
                    'modalidad': 'RES',
                    'lateralidad': 'DERECHA',
                },
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        correccion = CorreccionAprendizaje.objects.get()
        self.assertEqual(correccion.modo_dictado, 'AGENTE')
        self.assertEqual(correccion.tipo_plantilla, 'RODILLA')
        self.assertEqual(correccion.region, 'RODILLA')
        self.assertEqual(correccion.lateralidad, 'DERECHA')

    def test_dashboard_muestra_memoria_y_metricas_de_aprendizaje(self):
        registrar_evento_aprendizaje(
            usuario=self.user,
            tipo_evento=EventoAprendizajeDictado.TipoEvento.PLANTILLA_CONFIRMADA,
            region='CADERA',
            modalidad='RM',
            lateralidad='BILATERAL',
            plantilla_propuesta_codigo='CADERA_UNILATERAL',
            plantilla_confirmada_codigo='CADERAS',
        )

        response = self.client.get(reverse('dictado_informes:dashboard_metricas'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aprendizaje del agente')
        self.assertContains(response, 'CADERAS')
        self.assertEqual(response.context['aprendizaje_resumen']['selecciones_confirmadas'], 1)
        self.assertEqual(response.context['aprendizaje_resumen']['precision_sugerencia'], 0.0)


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver', 'localhost'])
class TestPanelPersonalMemoria(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='medico_memoria',
            password='admin123',
        )
        self.otro_usuario = User.objects.create_superuser(
            username='otro_medico_memoria',
            password='admin123',
        )
        self.client = Client()
        self.client.login(username='medico_memoria', password='admin123')
        for _ in range(3):
            registrar_evento_aprendizaje(
                usuario=self.user,
                tipo_evento=EventoAprendizajeDictado.TipoEvento.PLANTILLA_CONFIRMADA,
                region='CADERA',
                modalidad='RES',
                lateralidad='BILATERAL',
                plantilla_confirmada_codigo='CADERAS',
            )
        self.preferencia = PreferenciaAprendidaDictado.objects.get(usuario=self.user, vigente=True)

    def test_panel_muestra_solo_memoria_del_usuario(self):
        registrar_evento_aprendizaje(
            usuario=self.otro_usuario,
            tipo_evento=EventoAprendizajeDictado.TipoEvento.PLANTILLA_CONFIRMADA,
            region='CEREBRO',
            modalidad='RES',
            plantilla_confirmada_codigo='CEREBRO',
        )

        response = self.client.get(reverse('dictado_informes:memoria_aprendizaje'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CADERAS')
        self.assertNotContains(response, 'CEREBRO')

    def test_usuario_puede_pausar_y_reactivar_preferencia_fuerte(self):
        pausa = self.client.post(
            reverse('dictado_informes:actualizar_estado_memoria', args=[self.preferencia.pk]),
            {'accion': 'desactivar'},
        )
        self.assertRedirects(pausa, reverse('dictado_informes:memoria_aprendizaje'))
        self.preferencia.refresh_from_db()
        self.assertEqual(self.preferencia.estado, PreferenciaAprendidaDictado.Estado.INACTIVA)

        registrar_evento_aprendizaje(
            usuario=self.user,
            tipo_evento=EventoAprendizajeDictado.TipoEvento.PLANTILLA_CONFIRMADA,
            region='CADERA',
            modalidad='RES',
            lateralidad='BILATERAL',
            plantilla_confirmada_codigo='CADERAS',
        )
        self.preferencia.refresh_from_db()
        self.assertEqual(self.preferencia.estado, PreferenciaAprendidaDictado.Estado.INACTIVA)

        reactiva = self.client.post(
            reverse('dictado_informes:actualizar_estado_memoria', args=[self.preferencia.pk]),
            {'accion': 'reactivar'},
        )
        self.assertRedirects(reactiva, reverse('dictado_informes:memoria_aprendizaje'))
        self.preferencia.refresh_from_db()
        self.assertEqual(self.preferencia.estado, PreferenciaAprendidaDictado.Estado.ACTIVA)

    def test_usuario_no_puede_modificar_memoria_ajena(self):
        preferencia_ajena = PreferenciaAprendidaDictado.objects.create(
            usuario=self.otro_usuario,
            categoria=PreferenciaAprendidaDictado.Categoria.SELECCION_PLANTILLA,
            clave='MANO|RES|DERECHA',
            valor={'codigo_plantilla': 'MANO'},
            estado=PreferenciaAprendidaDictado.Estado.ACTIVA,
            confirmaciones=3,
            cantidad_evidencia=3,
            confianza=1.0,
        )

        response = self.client.post(
            reverse('dictado_informes:actualizar_estado_memoria', args=[preferencia_ajena.pk]),
            {'accion': 'desactivar'},
        )

        self.assertEqual(response.status_code, 404)
        preferencia_ajena.refresh_from_db()
        self.assertEqual(preferencia_ajena.estado, PreferenciaAprendidaDictado.Estado.ACTIVA)
