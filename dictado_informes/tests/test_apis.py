"""
Tests de las APIs REST con Mocks
=================================
Tests para las APIs de transcripción, mejora de texto y aprendizaje

Fecha: 2026-03-08
Cobertura esperada: ~70% de las APIs
"""

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
import json
import base64

from dictado_informes.models import PlantillaEstructurada, TrazaAgenteDictado
from dictado_informes.views import (
    extraer_contexto_clinico_dictado,
    sugerir_plantilla_hibrida_en_sombra,
    sugerir_plantilla_para_dictado,
)

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver', 'localhost'])
class TestAPIsTranscripcion(TestCase):
    """Tests para API de transcripción"""
    
    def setUp(self):
        """Crear usuario superuser y cliente"""
        self.user = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@test.com'
        )
        self.client = Client()
        self.client.login(username='admin', password='admin123')
    
    @patch('dictado_informes.ai_services.AIService.transcribe_audio')
    def test_transcribir_whisper_success(self, mock_transcribe):
        """Prueba transcripción exitosa"""
        # Mock de respuesta de Whisper
        mock_transcribe.return_value = {
            'text': 'Hallazgo de prueba',
            'confidence': 0.95,
            'duration': 3.5
        }
        
        # Audio fake en base64
        audio_fake = base64.b64encode(b'fake audio data' * 100).decode()
        
        response = self.client.post(
            '/dictado_informes/api/transcribir-whisper/',
            data=json.dumps({
                'audio': f'data:audio/webm;base64,{audio_fake}'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertIn('texto_transcrito', data)
        self.assertEqual(data['confianza'], 0.95)
    
    @patch('dictado_informes.ai_services.AIService.transcribe_audio')
    def test_transcribir_whisper_con_comandos_voz(self, mock_transcribe):
        """Prueba que comandos de voz se procesan"""
        mock_transcribe.return_value = {
            'text': 'Hallazgo uno punto nueva línea Hallazgo dos',
            'confidence': 0.95
        }
        
        audio_fake = base64.b64encode(b'fake audio' * 100).decode()
        
        response = self.client.post(
            '/dictado_informes/api/transcribir-whisper/',
            data=json.dumps({'audio': f'data:audio/webm;base64,{audio_fake}'}),
            content_type='application/json'
        )
        
        data = response.json()
        texto = data['texto_transcrito']
        
        # Debe tener puntos y saltos de línea procesados
        self.assertIn('.', texto)
        self.assertIn('\n', texto)

    @patch('dictado_informes.ai_services.AIService.transcribe_audio')
    def test_transcribir_whisper_rechaza_texto_vacio(self, mock_transcribe):
        mock_transcribe.return_value = {
            'text': '',
            'confidence': 0.95
        }

        audio_fake = base64.b64encode(b'fake audio' * 100).decode()

        response = self.client.post(
            '/dictado_informes/api/transcribir-whisper/',
            data=json.dumps({'audio': f'data:audio/webm;base64,{audio_fake}'}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('No se detecto texto', data['error'])
    
    def test_transcribir_audio_muy_corto(self):
        """Prueba que rechaza audios muy cortos"""
        audio_corto = base64.b64encode(b'short').decode()
        
        response = self.client.post(
            '/dictado_informes/api/transcribir-whisper/',
            data=json.dumps({'audio': f'data:audio/webm;base64,{audio_corto}'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('corto', data['error'].lower())
    
    def test_transcribir_sin_audio(self):
        """Prueba error cuando no se envía audio"""
        response = self.client.post(
            '/dictado_informes/api/transcribir-whisper/',
            data=json.dumps({}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_transcribir_sin_autenticacion(self):
        """Prueba que requiere autenticación"""
        # Logout
        self.client.logout()
        
        audio_fake = base64.b64encode(b'fake audio' * 100).decode()
        
        response = self.client.post(
            '/dictado_informes/api/transcribir-whisper/',
            data=json.dumps({'audio': f'data:audio/webm;base64,{audio_fake}'}),
            content_type='application/json'
        )
        
        # LoginRequired redirige al login cuando no hay sesion.
        self.assertIn(response.status_code, [302, 403])


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver', 'localhost'])
class TestAPIsMejora(TestCase):
    """Tests para API de mejora de texto"""
    
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin',
            password='admin123'
        )
        self.client = Client()
        self.client.login(username='admin', password='admin123')
    
    @patch('dictado_informes.ai_services.AIService.improve_medical_text')
    def test_mejorar_texto_modo_fiel(self, mock_improve):
        """Prueba mejora en modo FIEL"""
        mock_improve.return_value = {
            'texto_mejorado': 'Texto mejorado por IA',
            'confianza': 0.90,
            'sugerencias': []
        }
        
        response = self.client.post(
            '/dictado_informes/api/mejorar-texto/',
            data=json.dumps({
                'texto_original': 'texto de prueba',
                'modo': 'FIEL',
                'tipo_estudio': 'RES'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertEqual(data['texto_mejorado'], 'Texto mejorado por IA')

    @patch('dictado_informes.ai_services.AIService.improve_medical_text')
    def test_mejorar_texto_acepta_texto_transcrito(self, mock_improve):
        mock_improve.return_value = {
            'texto_mejorado': 'Texto mejorado por IA',
            'confianza': 0.90,
            'sugerencias': []
        }

        response = self.client.post(
            '/dictado_informes/api/mejorar-texto/',
            data=json.dumps({
                'texto_transcrito': 'texto desde transcripcion',
                'modo': 'AGENTE',
                'tipo_estudio': 'RES'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_improve.call_args.args[0], 'texto desde transcripcion')

    @override_settings(DICTADO_AGENTE_HABILITADO=False)
    @patch('dictado_informes.ai_services.AIService.improve_medical_text')
    def test_mejorar_texto_rechaza_agente_si_flag_apagado(self, mock_improve):
        response = self.client.post(
            '/dictado_informes/api/mejorar-texto/',
            data=json.dumps({
                'texto_original': 'gonalgia derecha',
                'modo': 'AGENTE',
                'tipo_estudio': 'RES'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(mock_improve.called)
    
    @patch('dictado_informes.models.TerminoMedico.aplicar_correcciones')
    @patch('dictado_informes.ai_services.AIService.improve_medical_text')
    def test_mejorar_texto_aplica_diccionario(self, mock_ia, mock_correcciones):
        """Prueba que se aplica diccionario médico"""
        mock_correcciones.return_value = (
            'texto corregido',
            [{'de': 'gonartrosis', 'a': 'gonartrosis tricompartimental'}]
        )
        mock_ia.return_value = {
            'texto_mejorado': 'texto final',
            'confianza': 0.9
        }
        
        response = self.client.post(
            '/dictado_informes/api/mejorar-texto/',
            data=json.dumps({
                'texto_original': 'gonartrosis',
                'modo': 'FIEL',
                'from_manual_edit': True,
            }),
            content_type='application/json'
        )
        
        # Verificar que se aplicaron correcciones
        self.assertTrue(mock_correcciones.called)
        data = response.json()
        self.assertIn('correcciones_aplicadas', data)
    
    def test_mejorar_texto_sin_texto(self):
        """Prueba error cuando no se envía texto"""
        response = self.client.post(
            '/dictado_informes/api/mejorar-texto/',
            data=json.dumps({'modo': 'FIEL'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_mejorar_texto_sin_autenticacion(self):
        """Prueba que requiere autenticación"""
        self.client.logout()
        
        response = self.client.post(
            '/dictado_informes/api/mejorar-texto/',
            data=json.dumps({
                'texto_original': 'test',
                'modo': 'FIEL'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 403)

    def test_selector_agente_sugiere_plantilla_por_dictado(self):
        PlantillaEstructurada.objects.create(
            codigo='100000',
            nombre='RM de Rodilla',
            titulo='RESONANCIA MAGNETICA DE RODILLA',
            seccion_tecnica='Se exploro la rodilla con secuencias habituales.',
            comentarios_base=[
                'Meniscos de altura y senal normales.',
                'No se observa aumento del liquido articular.',
            ],
            creada_por=self.user,
            origen='user',
        )
        PlantillaEstructurada.objects.create(
            codigo='100001',
            nombre='RM de Cerebro',
            titulo='RESONANCIA MAGNETICA DE CEREBRO',
            seccion_tecnica='Se exploro el encefalo con secuencias habituales.',
            comentarios_base=['Sistema ventricular conservado.'],
            creada_por=self.user,
            origen='user',
        )

        sugerida = sugerir_plantilla_para_dictado(
            'rodilla derecha con desgarro de menisco y derrame articular',
            self.user,
        )

        self.assertEqual(sugerida['codigo'], '100000')
        self.assertEqual(sugerida['candidatos'][0]['codigo'], '100000')
        self.assertIn(sugerida['confianza_selector'], {'alta', 'media', 'baja'})
        self.assertGreaterEqual(sugerida['margen'], 0)

    def test_selector_agente_no_mezcla_cadera_con_columna(self):
        PlantillaEstructurada.objects.create(
            codigo='100010',
            nombre='RM de columna lumbosacra',
            titulo='RM DE COLUMNA LUMBOSACRA',
            seccion_tecnica='Se exploro la columna lumbosacra.',
            comentarios_base=[
                'Correcta alineacion en el plano sagital.',
                'Cuerpos vertebrales y espacios discales de altura conservada.',
            ],
            creada_por=self.user,
            origen='user',
        )
        PlantillaEstructurada.objects.create(
            codigo='100011',
            nombre='RM de caderas',
            titulo='RM DE CADERAS',
            seccion_tecnica='Se exploraron ambas caderas.',
            comentarios_base=[
                'Articulaciones coxofemorales conservadas.',
                'Tendones gluteos conservados.',
            ],
            creada_por=self.user,
            origen='user',
        )

        sugerida = sugerir_plantilla_para_dictado(
            'Resonancia de ambas caderas con tendinopatia glutea derecha.',
            self.user,
        )

        self.assertEqual(sugerida['codigo'], '100011')

    def test_selector_agente_no_mezcla_mano_con_columna(self):
        PlantillaEstructurada.objects.create(
            codigo='100020',
            nombre='RM de columna lumbosacra',
            titulo='RM DE COLUMNA LUMBOSACRA',
            seccion_tecnica='Se exploro la columna lumbosacra.',
            comentarios_base=[
                'Correcta alineacion en el plano sagital.',
                'Cuerpos vertebrales y espacios discales de altura conservada.',
            ],
            creada_por=self.user,
            origen='user',
        )
        PlantillaEstructurada.objects.create(
            codigo='100021',
            nombre='RM de mano',
            titulo='RM DE MANO [<DERECHA/IZQUIERDA>]',
            seccion_tecnica='Se exploro la mano [<lado>] con protocolo habitual.',
            comentarios_base=[
                'Alineacion carpometacarpiana conservada.',
                'Tendones flexores y extensores sin alteraciones.',
            ],
            creada_por=self.user,
            origen='user',
        )

        sugerida = sugerir_plantilla_para_dictado(
            'resonancia magnetica de mano izquierda con trauma, risartrosis y tenosinovitis del tendon flexor del pulgar',
            self.user,
        )

        self.assertEqual(sugerida['codigo'], '100021')

    def test_selector_hibrido_distingue_plantillas_de_la_misma_region(self):
        PlantillaEstructurada.objects.create(
            codigo='100030',
            nombre='RM de rodilla general',
            titulo='RM DE RODILLA',
            seccion_tecnica='Se exploro la rodilla con protocolo habitual.',
            comentarios_base=['Ligamentos cruzados conservados.'],
            creada_por=self.user,
            origen='user',
        )
        PlantillaEstructurada.objects.create(
            codigo='100031',
            nombre='RM de rodilla meniscal',
            titulo='RM DE RODILLA',
            seccion_tecnica='Se exploro la rodilla con protocolo habitual.',
            comentarios_base=[
                'Menisco interno de altura y senal conservadas.',
                'Menisco externo de altura y senal conservadas.',
            ],
            creada_por=self.user,
            origen='user',
        )

        sugerida = sugerir_plantilla_hibrida_en_sombra(
            'Rodilla derecha con desgarro del menisco interno.',
            self.user,
        )

        self.assertEqual(sugerida['codigo'], '100031')
        self.assertEqual(sugerida['version'], 'hibrido_v1')
        self.assertEqual(sugerida['candidatos'][0]['codigo'], '100031')

    def test_extrae_contexto_clinico_mano_izquierda(self):
        contexto = extraer_contexto_clinico_dictado(
            'Resonancia magnetica de mano izquierda con antecedente traumatico y risartrosis.'
        )

        self.assertEqual(contexto['region'], 'MANO')
        self.assertEqual(contexto['lateralidad'], 'IZQUIERDA')
        self.assertEqual(contexto['lado_tecnica'], 'izquierda')

    def test_extrae_contexto_clinico_gonalgia_derecha(self):
        contexto = extraer_contexto_clinico_dictado('Paciente con gonalgia derecha.')

        self.assertEqual(contexto['region'], 'RODILLA')
        self.assertEqual(contexto['lateralidad'], 'DERECHA')
        self.assertEqual(contexto['lado_tecnica'], 'derecha')
        self.assertEqual(contexto['indicacion_clinica'], 'Gonalgia derecha.')

    def test_extrae_contexto_clinico_ambas_caderas(self):
        contexto = extraer_contexto_clinico_dictado('Paciente con coxalgia de ambas caderas.')

        self.assertEqual(contexto['region'], 'CADERA')
        self.assertEqual(contexto['lateralidad'], 'BILATERAL')
        self.assertEqual(contexto['titulo_lateralidad'], 'AMBAS CADERAS')
        self.assertEqual(contexto['frase_lateralidad'], 'ambas caderas')
        self.assertEqual(contexto['indicacion_clinica'], 'Coxalgia bilateral.')

    @patch('dictado_informes.ai_services.AIService.improve_medical_text')
    def test_modo_agente_usa_plantilla_sugerida(self, mock_improve):
        PlantillaEstructurada.objects.create(
            codigo='100000',
            nombre='RM de Rodilla',
            titulo='RESONANCIA MAGNETICA DE RODILLA',
            seccion_tecnica='Se exploro la rodilla con secuencias habituales.',
            comentarios_base=['Meniscos de altura y senal normales.'],
            creada_por=self.user,
            origen='user',
        )
        mock_improve.return_value = {
            'texto_mejorado': 'Informe estructurado',
            'confianza': 0.9,
            'sugerencias': [],
            'modo': 'ESTRUCTURADO',
        }

        response = self.client.post(
            '/dictado_informes/api/mejorar-texto/',
            data=json.dumps({
                'texto_original': 'gonalgia derecha con desgarro meniscal',
                'modo': 'AGENTE',
                'tipo_plantilla': 'FALLBACK',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['plantilla_sugerida']['codigo'], '100000')
        self.assertEqual(data['tipo_plantilla_usada'], '100000')
        contexto = mock_improve.call_args.args[2]
        self.assertEqual(contexto['modo'], 'ESTRUCTURADO')
        self.assertEqual(contexto['tipo_plantilla'], '100000')
        self.assertEqual(contexto['contexto_clinico']['lateralidad'], 'DERECHA')
        self.assertEqual(contexto['contexto_clinico']['indicacion_clinica'], 'Gonalgia derecha.')

        traza = TrazaAgenteDictado.objects.get()
        self.assertEqual(traza.usuario, self.user)
        self.assertEqual(traza.codigo_plantilla, '100000')
        self.assertEqual(traza.region_detectada, 'RODILLA')
        self.assertEqual(traza.lateralidad_detectada, 'DERECHA')
        self.assertTrue(traza.huella_entrada)
        self.assertNotIn('gonalgia', str(traza.candidatos).lower())
        self.assertTrue(traza.exitosa)
        self.assertEqual(traza.codigo_plantilla_sombra, '100000')
        self.assertTrue(traza.selector_sombra_coincide)

    @override_settings(DICTADO_SELECTOR_HIBRIDO_SOMBRA=False)
    @patch('dictado_informes.ai_services.AIService.improve_medical_text')
    def test_selector_sombra_puede_desactivarse_sin_afectar_agente(self, mock_improve):
        PlantillaEstructurada.objects.create(
            codigo='100040',
            nombre='RM de Rodilla',
            titulo='RM DE RODILLA',
            seccion_tecnica='Se exploro la rodilla.',
            comentarios_base=['Meniscos conservados.'],
            creada_por=self.user,
            origen='user',
        )
        mock_improve.return_value = {
            'texto_mejorado': 'Informe estructurado',
            'confianza': 0.9,
        }

        response = self.client.post(
            '/dictado_informes/api/mejorar-texto/',
            data=json.dumps({
                'texto_original': 'gonalgia derecha',
                'modo': 'AGENTE',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tipo_plantilla_usada'], '100040')
        self.assertEqual(TrazaAgenteDictado.objects.get().codigo_plantilla_sombra, '')

    @patch('dictado_informes.ai_services.AIService.improve_medical_text')
    def test_modo_fiel_no_registra_traza_agente(self, mock_improve):
        mock_improve.return_value = {
            'texto_mejorado': 'Texto corregido',
            'confianza': 0.9,
        }

        response = self.client.post(
            '/dictado_informes/api/mejorar-texto/',
            data=json.dumps({
                'texto_original': 'texto de prueba',
                'modo': 'FIEL',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TrazaAgenteDictado.objects.exists())


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver', 'localhost'])
class TestAPIsAprendizaje(TestCase):
    """Tests para API de aprendizaje"""
    
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin',
            password='admin123'
        )
        self.client = Client()
        self.client.login(username='admin', password='admin123')
    
    def test_guardar_aprendizaje_success(self):
        """Prueba guardar corrección de aprendizaje"""
        response = self.client.post(
            '/dictado_informes/api/guardar-aprendizaje/',
            data=json.dumps({
                'texto_original': 'original',
                'texto_ia': 'ia mejorado',
                'texto_final': 'final editado',
                'tipo_estudio': 'RES'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertTrue(data['guardado'])
        self.assertIn('cambios', data)
    
    def test_guardar_aprendizaje_sin_cambios(self):
        """Prueba que no guarda si no hay cambios"""
        response = self.client.post(
            '/dictado_informes/api/guardar-aprendizaje/',
            data=json.dumps({
                'texto_original': 'igual',
                'texto_ia': 'igual',
                'texto_final': 'igual',
            }),
            content_type='application/json'
        )
        
        data = response.json()
        self.assertFalse(data['guardado'])
    
    def test_info_aprendizaje(self):
        """Prueba obtener info de ejemplos activos"""
        from dictado_informes.models import CorreccionAprendizaje
        
        # Crear corrección
        correccion = CorreccionAprendizaje.objects.create(
            texto_original='rodilla con lesion',
            texto_ia='Se observa lesion meniscal.',
            texto_final='Desgarro meniscal.',
            usuario=self.user
        )
        correccion.cambios_detectados = correccion.calcular_diferencias()
        correccion.save(update_fields=['cambios_detectados'])
        
        response = self.client.get('/dictado_informes/api/info-aprendizaje/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['cantidad'], 1)
    
    def test_guardar_aprendizaje_sin_autenticacion(self):
        """Prueba que requiere autenticación"""
        self.client.logout()
        
        response = self.client.post(
            '/dictado_informes/api/guardar-aprendizaje/',
            data=json.dumps({
                'texto_original': 'test',
                'texto_ia': 'test',
                'texto_final': 'test final',
            }),
            content_type='application/json'
        )
        
        # Debe rechazar
        self.assertIn(response.status_code, [302, 403])
