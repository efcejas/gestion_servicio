"""
🚀 FASE 4: Tests para el Sistema de Monitoreo de Métricas

Tests para el modelo MetricaDictado y funcionalidades de análisis.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from dictado_informes.models import MetricaDictado, TipoEstudio

User = get_user_model()


class TestMetricaDictado(TestCase):
    """Tests para el modelo MetricaDictado"""
    
    def setUp(self):
        """Crear usuarios y métricas de prueba"""
        self.user1 = User.objects.create_user(
            username='doctor1',
            password='test123',
            email='doctor1@example.com'
        )
        self.user2 = User.objects.create_user(
            username='doctor2',
            password='test123',
            email='doctor2@example.com'
        )
    
    def test_crear_metrica_basica(self):
        """Prueba creación básica de métrica"""
        metrica = MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=1500,
            tiempo_transcripcion_ms=800,
            tiempo_mejora_ms=700,
            tuvo_errores=False
        )
        
        self.assertIsNotNone(metrica.id)
        self.assertEqual(metrica.usuario, self.user1)
        self.assertEqual(metrica.tiempo_total_ms, 1500)
        self.assertFalse(metrica.tuvo_errores)
    
    def test_metrica_con_error(self):
        """Prueba creación de métrica con error"""
        metrica = MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=2000,
            tuvo_errores=True,
            error_detalle='API timeout'
        )
        
        self.assertTrue(metrica.tuvo_errores)
        self.assertEqual(metrica.error_detalle, 'API timeout')
    
    def test_cache_hit_rate_completo(self):
        """Prueba cálculo de tasa de caché con ambos hits"""
        metrica = MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=1000,
            tiempo_transcripcion_ms=100,
            tiempo_mejora_ms=200,
            transcripcion_from_cache=True,
            mejora_from_cache=True
        )
        
        # Ambos hits = 100%
        self.assertEqual(metrica.cache_hit_rate, 1.0)
    
    def test_cache_hit_rate_parcial(self):
        """Prueba cálculo de tasa de caché con un hit"""
        metrica = MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=1000,
            tiempo_transcripcion_ms=800,
            tiempo_mejora_ms=200,
            transcripcion_from_cache=False,
            mejora_from_cache=True
        )
        
        # 1 de 2 hits = 50%
        self.assertEqual(metrica.cache_hit_rate, 0.5)
    
    def test_cache_hit_rate_ninguno(self):
        """Prueba cálculo de tasa de caché sin hits"""
        metrica = MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=1000,
            tiempo_transcripcion_ms=800,
            tiempo_mejora_ms=200,
            transcripcion_from_cache=False,
            mejora_from_cache=False
        )
        
        # 0 de 2 hits = 0%
        self.assertEqual(metrica.cache_hit_rate, 0.0)
    
    def test_metrica_con_tipo_estudio(self):
        """Prueba métrica con tipo de estudio"""
        metrica = MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=1500,
            tipo_estudio=TipoEstudio.RESONANCIA,
            modo_mejora='FIEL'
        )
        
        self.assertEqual(metrica.tipo_estudio, TipoEstudio.RESONANCIA)
        self.assertEqual(metrica.modo_mejora, 'FIEL')
    
    def test_metrica_con_audio_info(self):
        """Prueba métrica con información de audio"""
        metrica = MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=1500,
            duracion_audio_segundos=5.5,
            tamanio_audio_kb=128,
            longitud_transcripcion=250,
            longitud_mejora=300
        )
        
        self.assertEqual(metrica.duracion_audio_segundos, 5.5)
        self.assertEqual(metrica.tamanio_audio_kb, 128)
        self.assertEqual(metrica.longitud_transcripcion, 250)
        self.assertEqual(metrica.longitud_mejora, 300)
    
    def test_obtener_estadisticas_periodo(self):
        """Prueba obtención de estadísticas por periodo"""
        # Crear métricas de prueba
        # 3 métricas normales
        for i in range(3):
            MetricaDictado.objects.create(
                usuario=self.user1,
                tiempo_total_ms=1000 + i*100,
                tiempo_transcripcion_ms=500,
                tiempo_mejora_ms=500,
                tipo_estudio=TipoEstudio.RESONANCIA,
                tuvo_errores=False
            )
        
        # 1 métrica con error
        MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=1500,
            tuvo_errores=True,
            error_detalle='Test error'
        )
        
        # Calcular periodo DESPUÉS de crear métricas
        ahora = timezone.now()
        ayer = ahora - timedelta(days=1)
        
        # Obtener estadísticas
        stats = MetricaDictado.obtener_estadisticas_periodo(ayer, ahora)
        
        # Verificar totales
        self.assertEqual(stats['total_requests'], 4)
        self.assertEqual(stats['total_errores'], 1)
        self.assertEqual(stats['tasa_error'], 25.0)  # 1 de 4 = 25%
        
        # Verificar tiempos
        self.assertIsNotNone(stats['tiempo_promedio'])
        self.assertEqual(stats['tiempo_min'], 1000)
        self.assertEqual(stats['tiempo_max'], 1500)
    
    def test_obtener_estadisticas_periodo_por_usuario(self):
        """Prueba estadísticas filtradas por usuario"""
        # Crear métricas para user1
        MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=1000,
            tuvo_errores=False
        )
        
        # Crear métricas para user2
        MetricaDictado.objects.create(
            usuario=self.user2,
            tiempo_total_ms=2000,
            tuvo_errores=False
        )
        
        # Calcular periodo DESPUÉS de crear métricas
        ahora = timezone.now()
        ayer = ahora - timedelta(days=1)
        
        # Obtener solo stats de user1
        stats = MetricaDictado.obtener_estadisticas_periodo(ayer, ahora, usuario=self.user1)
        
        self.assertEqual(stats['total_requests'], 1)
        self.assertEqual(stats['tiempo_promedio'], 1000)
    
    def test_obtener_top_usuarios(self):
        """Prueba obtención de usuarios con más uso"""
        # User1 con 5 usos
        for i in range(5):
            MetricaDictado.objects.create(
                usuario=self.user1,
                tiempo_total_ms=1000,
                tuvo_errores=False
            )
        
        # User2 con 2 usos
        for i in range(2):
            MetricaDictado.objects.create(
                usuario=self.user2,
                tiempo_total_ms=1500,
                tuvo_errores=False
            )
                # Calcular periodo DESPUÉS de crear métricas
        ahora = timezone.now()
        ayer = ahora - timedelta(days=1)
                # Obtener top usuarios
        top = MetricaDictado.obtener_top_usuarios(ayer, ahora, limite=5)
        
        # Verificar orden (user1 primero con 5 usos)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]['usuario__username'], 'doctor1')
        self.assertEqual(top[0]['total_usos'], 5)
        self.assertEqual(top[1]['usuario__username'], 'doctor2')
        self.assertEqual(top[1]['total_usos'], 2)
    
    def test_detectar_anomalias(self):
        """Prueba detección de requests anormalmente lentos"""
        # Métrica normal (1 segundo)
        MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=1000,
            tuvo_errores=False
        )
        
        # Métrica lenta (10 segundos)
        metrica_lenta = MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=10000,
            tuvo_errores=False
        )
        
        # Detectar anomalías con umbral de 5 segundos
        anomalias = MetricaDictado.detectar_anomalias(umbral_ms=5000)
        
        # Solo debe detectar la métrica lenta
        self.assertEqual(anomalias.count(), 1)
        self.assertEqual(anomalias.first().id, metrica_lenta.id)
    
    def test_metrica_str(self):
        """Prueba representación en string de métrica"""
        metrica = MetricaDictado.objects.create(
            usuario=self.user1,
            tiempo_total_ms=1500,
            tuvo_errores=False
        )
        
        str_repr = str(metrica)
        
        # Debe contener status OK y username
        self.assertIn('✅ OK', str_repr)
        self.assertIn('doctor1', str_repr)
        self.assertIn('1500ms', str_repr)
    
    def test_distribucion_por_tipo_estudio(self):
        """Prueba distribución de métricas por tipo de estudio"""
        # 3 resonancias
        for i in range(3):
            MetricaDictado.objects.create(
                usuario=self.user1,
                tiempo_total_ms=1000,
                tipo_estudio=TipoEstudio.RESONANCIA
            )
        
        # 2 tomografías
        for i in range(2):
            MetricaDictado.objects.create(
                usuario=self.user1,
                tiempo_total_ms=1000,
                tipo_estudio=TipoEstudio.TOMOGRAFIA
            )
        
        # Calcular periodo DESPUÉS de crear métricas
        ahora = timezone.now()
        ayer = ahora - timedelta(days=1)
        
        stats = MetricaDictado.obtener_estadisticas_periodo(ayer, ahora)
        
        # Verificar distribución (las claves son los VALORES del enum: 'RES', 'TOM', etc.)
        self.assertEqual(stats['por_tipo_estudio']['RES'], 3)  # RESONANCIA
        self.assertEqual(stats['por_tipo_estudio']['TOM'], 2)  # TOMOGRAFIA
    
    def test_distribucion_por_modo(self):
        """Prueba distribución de métricas por modo de mejora"""
        # 4 en modo FIEL
        for i in range(4):
            MetricaDictado.objects.create(
                usuario=self.user1,
                tiempo_total_ms=1000,
                modo_mejora='FIEL'
            )
        
        # 2 en modo LIBRE
        for i in range(2):
            MetricaDictado.objects.create(
                usuario=self.user1,
                tiempo_total_ms=1000,
                modo_mejora='LIBRE'
            )
        
        # Calcular periodo DESPUÉS de crear métricas
        ahora = timezone.now()
        ayer = ahora - timedelta(days=1)
        
        stats = MetricaDictado.obtener_estadisticas_periodo(ayer, ahora)
        
        # Verificar distribución
        self.assertEqual(stats['por_modo']['FIEL'], 4)
        self.assertEqual(stats['por_modo']['LIBRE'], 2)


class TestComandoReporteMetricas(TestCase):
    """Tests para el comando generar_reporte_metricas"""
    
    def setUp(self):
        """Crear datos de prueba"""
        self.user = User.objects.create_user(
            username='test_doctor',
            password='test123'
        )
        
        # Crear métricas de prueba
        for i in range(5):
            MetricaDictado.objects.create(
                usuario=self.user,
                tiempo_total_ms=1000 + i*100,
                tipo_estudio=TipoEstudio.RESONANCIA,
                tuvo_errores=False
            )
    
    def test_comando_existe(self):
        """Prueba que el comando existe y puede importarse"""
        from django.core.management import call_command
        
        # No debe lanzar error al importar
        try:
            from dictado_informes.management.commands import generar_reporte_metricas
            self.assertTrue(True)
        except ImportError:
            self.fail("Comando generar_reporte_metricas no encontrado")
    
    def test_comando_ejecuta_sin_errores(self):
        """Prueba que el comando se ejecuta sin errores"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        
        # Ejecutar comando con parámetros por defecto
        try:
            call_command('generar_reporte_metricas', '--dias=7', stdout=out)
            output = out.getvalue()
            
            # Verificar que se generó output
            self.assertIn('REPORTE DE MÉTRICAS', output)
            self.assertIn('Total de requests', output)
        except Exception as e:
            self.fail(f"Comando falló con error: {str(e)}")
    
    def test_comando_con_silencioso(self):
        """Prueba comando en modo silencioso"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        
        # Ejecutar en modo silencioso
        call_command('generar_reporte_metricas', '--silencioso', stdout=out)
        output = out.getvalue()
        
        # No debe haber output (o muy poco)
        self.assertLess(len(output), 100)
