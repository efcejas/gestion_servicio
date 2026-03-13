import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from preinformes.asistente_service import AsistenteRadiologicoBot
from preinformes.models import ConversacionAsistentePreinforme, MensajeAsistentePreinforme, Preinforme, TipoEstudio, Region

User = get_user_model()


class AsistenteScoringPersistenceTest(TestCase):
    def setUp(self):
        self.residente = User.objects.create_user(
            username='residente_scoring',
            email='residente_scoring@test.com',
            password='testpass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.docente = User.objects.create_user(
            username='docente_scoring',
            email='docente_scoring@test.com',
            password='testpass123',
            rol='jefe_residentes',
            perfil_completo=True,
        )
        self.tipo_estudio = TipoEstudio.objects.create(nombre='RM Abdomen', activo=True)
        self.region = Region.objects.create(nombre='Abdomen', activo=True)

    def _crear_conversacion_con_suficientes_mensajes(self):
        conversacion = ConversacionAsistentePreinforme.objects.create(usuario=self.residente)
        mensajes = [
            ('user', 'Estoy describiendo una lesión hepática y no sé si la terminología es correcta.'),
            ('assistant', 'Mirá primero la modalidad. ¿Qué término corresponde usar en ese estudio?'),
            ('user', 'Es una resonancia. Creo que puse hipodensa y probablemente esté mal.'),
            ('assistant', 'Bien visto. ¿Qué palabra usarías en RM en vez de esa?'),
            ('user', 'Debería hablar de señal e intensidad. También tengo dudas con la conclusión.'),
        ]
        for rol, contenido in mensajes:
            MensajeAsistentePreinforme.objects.create(
                conversacion=conversacion,
                rol=rol,
                contenido=contenido,
            )
        return conversacion

    def _mock_openai_response(self):
        contenido = json.dumps({
            'razonamiento_clinico': 8,
            'terminologia': 7,
            'autonomia': 9,
            'receptividad': 8,
            'comentario': 'Buena sesión: corrige términos y muestra autonomía creciente.',
        })
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=contenido))]
        )

    def test_evaluar_conversacion_persiste_scoring_en_modelo(self):
        conversacion = self._crear_conversacion_con_suficientes_mensajes()
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = self._mock_openai_response()

        bot = AsistenteRadiologicoBot()
        bot.client = mock_client
        bot.fallback_client = None
        bot.model = 'fake-model'

        resultado = bot.evaluar_conversacion(conversacion.id)

        self.assertTrue(resultado['success'])

        conversacion.refresh_from_db()
        self.assertTrue(conversacion.evaluada)
        self.assertEqual(conversacion.evaluacion_ia['razonamiento_clinico'], 8)
        self.assertEqual(conversacion.evaluacion_ia['terminologia'], 7)
        self.assertEqual(conversacion.evaluacion_ia['autonomia'], 9)
        self.assertEqual(conversacion.evaluacion_ia['receptividad'], 8)
        self.assertEqual(conversacion.puntuacion_global, 8.0)

    @patch('preinformes.asistente_service.OpenAI')
    @patch('preinformes.asistente_service.config')
    def test_endpoint_docente_guarda_scoring_de_conversacion_del_residente(self, mock_config, mock_openai):
        conversacion = self._crear_conversacion_con_suficientes_mensajes()
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = self._mock_openai_response()
        mock_openai.return_value = mock_client
        mock_config.side_effect = lambda key, default=None: 'fake-key' if key == 'OPENAI_API_KEY' else None

        self.client.force_login(self.docente)
        response = self.client.post(
            reverse('preinformes:asistente_evaluar'),
            data=json.dumps({'conversacion_id': conversacion.id}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['puntuacion_global'], 8.0)

        conversacion.refresh_from_db()
        self.assertTrue(conversacion.evaluada)
        self.assertEqual(conversacion.puntuacion_global, 8.0)
        self.assertEqual(conversacion.evaluacion_ia['comentario'], 'Buena sesión: corrige términos y muestra autonomía creciente.')

    def test_endpoint_residente_no_puede_evaluar(self):
        conversacion = self._crear_conversacion_con_suficientes_mensajes()
        self.client.force_login(self.residente)

        response = self.client.post(
            reverse('preinformes:asistente_evaluar'),
            data=json.dumps({'conversacion_id': conversacion.id}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)
        conversacion.refresh_from_db()
        self.assertFalse(conversacion.evaluada)
        self.assertIsNone(conversacion.puntuacion_global)

    @patch('preinformes.asistente_service.OpenAI')
    @patch('preinformes.asistente_service.config')
    def test_crear_y_enviar_preinforme_autoevalua_chat_y_asocia_conversacion(self, mock_config, mock_openai):
        conversacion = self._crear_conversacion_con_suficientes_mensajes()
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = self._mock_openai_response()
        mock_openai.return_value = mock_client
        mock_config.side_effect = lambda key, default=None: 'fake-key' if key == 'OPENAI_API_KEY' else None

        self.client.force_login(self.residente)
        response = self.client.post(
            reverse('preinformes:crear_preinforme'),
            data={
                'numero_estudio': '2026-0001',
                'tipo_estudio': self.tipo_estudio.id,
                'region': self.region.id,
                'sistema_destino': 'eges',
                'apellido_paciente': 'Perez',
                'nombre_paciente': 'Maria',
                'dni_paciente': '',
                'edad_paciente': 45,
                'sexo_paciente': 'F',
                'informe_html': '<p>Hígado de tamaño normal. Sin lesiones focales.</p>',
                'guardar_y_enviar': '1',
                'asistente_conversacion_id': str(conversacion.id),
            },
        )

        self.assertEqual(response.status_code, 302)

        preinforme = Preinforme.objects.get(numero_estudio='2026-0001')
        self.assertEqual(preinforme.estado, 'pendiente_revision')

        conversacion.refresh_from_db()
        self.assertEqual(conversacion.preinforme_id, preinforme.id)
        self.assertTrue(conversacion.evaluada)
        self.assertEqual(conversacion.puntuacion_global, 8.0)