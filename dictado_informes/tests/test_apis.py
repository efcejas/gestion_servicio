"""
Tests de las APIs REST con Mocks
=================================
Tests para las APIs de transcripción, mejora de texto y aprendizaje

Fecha: 2026-03-08
Cobertura esperada: ~70% de las APIs
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
import json
import base64

User = get_user_model()


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
        
        # Debe rechazar por falta de permisos
        self.assertEqual(response.status_code, 403)


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
                'modo': 'FIEL'
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
        CorreccionAprendizaje.objects.create(
            texto_original='a',
            texto_ia='b',
            texto_final='c',
            usuario=self.user
        )
        
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
