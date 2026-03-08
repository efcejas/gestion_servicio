"""
🚀 FASE 4: Comando para generar reportes automáticos de métricas

Uso:
    python manage.py generar_reporte_metricas
    python manage.py generar_reporte_metricas --dias 30
    python manage.py generar_reporte_metricas --email admin@example.com
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from dictado_informes.models import MetricaDictado, TipoEstudio
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '📊 Genera reporte de métricas del sistema de dictado'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=7,
            help='Número de días a analizar (default: 7)'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email para enviar el reporte (opcional)'
        )
        parser.add_argument(
            '--umbral-lento',
            type=int,
            default=5000,
            help='Umbral en ms para detectar requests lentos (default: 5000)'
        )
        parser.add_argument(
            '--silencioso',
            action='store_true',
            help='No mostrar output en consola'
        )
    
    def handle(self, *args, **options):
        dias = options['dias']
        email_destino = options['email']
        umbral_lento = options['umbral_lento']
        silencioso = options['silencioso']
        
        if not silencioso:
            self.stdout.write(self.style.SUCCESS(f'\n📊 Generando reporte de métricas de los últimos {dias} días...\n'))
        
        # Calcular fechas
        fecha_hasta = timezone.now()
        fecha_desde = fecha_hasta - timedelta(days=dias)
        
        # Obtener estadísticas
        stats = MetricaDictado.obtener_estadisticas_periodo(fecha_desde, fecha_hasta)
        
        # Detectar anomalías
        anomalias = MetricaDictado.detectar_anomalias(umbral_ms=umbral_lento)[:10]
        
        # Top usuarios
        top_usuarios = MetricaDictado.obtener_top_usuarios(fecha_desde, fecha_hasta, limite=10)
        
        # Generar reporte en texto
        reporte = self._generar_reporte_texto(stats, anomalias, top_usuarios, dias, umbral_lento)
        
        # Mostrar en consola si no es silencioso
        if not silencioso:
            self.stdout.write(reporte)
        
        # Enviar por email si se especificó
        if email_destino:
            self._enviar_email(reporte, email_destino, fecha_desde, fecha_hasta)
            if not silencioso:
                self.stdout.write(self.style.SUCCESS(f'\n✅ Reporte enviado a {email_destino}'))
        
        if not silencioso:
            self.stdout.write(self.style.SUCCESS('\n✅ Reporte generado exitosamente\n'))
    
    def _generar_reporte_texto(self, stats, anomalias, top_usuarios, dias, umbral_lento):
        """Genera el reporte en formato texto"""
        lineas = []
        
        # Encabezado
        lineas.append('=' * 80)
        lineas.append(f'📊 REPORTE DE MÉTRICAS - SISTEMA DE DICTADO INTELIGENTE')
        lineas.append(f'Periodo: Últimos {dias} días')
        lineas.append(f'Fecha generación: {timezone.now().strftime("%d/%m/%Y %H:%M:%S")}')
        lineas.append('=' * 80)
        lineas.append('')
        
        # Resumen General
        lineas.append('📈 RESUMEN GENERAL')
        lineas.append('-' * 80)
        lineas.append(f'Total de requests:        {stats["total_requests"]:,}')
        lineas.append(f'Requests con errores:     {stats["total_errores"]:,} ({stats["tasa_error"]:.2f}%)')
        lineas.append(f'Tiempo promedio:          {stats["tiempo_promedio"]:.0f} ms' if stats["tiempo_promedio"] else 'Tiempo promedio:          N/A')
        lineas.append(f'Tiempo mínimo:            {stats["tiempo_min"]} ms' if stats["tiempo_min"] else 'Tiempo mínimo:            N/A')
        lineas.append(f'Tiempo máximo:            {stats["tiempo_max"]} ms' if stats["tiempo_max"] else 'Tiempo máximo:            N/A')
        lineas.append(f'Audio procesado (total):  {stats["duracion_audio_total"]:.1f} segundos' if stats["duracion_audio_total"] else 'Audio procesado (total):  N/A')
        lineas.append('')
        
        # Uso de Caché
        lineas.append('💾 USO DE CACHÉ')
        lineas.append('-' * 80)
        lineas.append(f'Caché de transcripción:   {stats["cache_transcripcion"]:,} hits ({stats["tasa_cache_transcripcion"]:.1f}%)')
        lineas.append(f'Caché de mejora IA:       {stats["cache_mejora"]:,} hits ({stats["tasa_cache_mejora"]:.1f}%)')
        lineas.append('')
        
        # Distribución por Tipo de Estudio
        if stats.get('por_tipo_estudio'):
            lineas.append('🏥 DISTRIBUCIÓN POR TIPO DE ESTUDIO')
            lineas.append('-' * 80)
            for tipo_code, count in sorted(stats['por_tipo_estudio'].items(), key=lambda x: x[1], reverse=True):
                try:
                    tipo_display = dict(TipoEstudio.choices).get(tipo_code, tipo_code)
                    lineas.append(f'  {tipo_display:25s} {count:5d} requests')
                except:
                    lineas.append(f'  {tipo_code:25s} {count:5d} requests')
            lineas.append('')
        
        # Distribución por Modo
        if stats.get('por_modo'):
            lineas.append('🎯 DISTRIBUCIÓN POR MODO')
            lineas.append('-' * 80)
            for modo, count in sorted(stats['por_modo'].items(), key=lambda x: x[1], reverse=True):
                lineas.append(f'  {modo:25s} {count:5d} requests')
            lineas.append('')
        
        # Top Usuarios
        if top_usuarios:
            lineas.append('👥 TOP 10 USUARIOS')
            lineas.append('-' * 80)
            for i, usuario in enumerate(top_usuarios, 1):
                username = usuario['usuario__username'] or 'Desconocido'
                nombre_completo = f"{usuario.get('usuario__first_name', '')} {usuario.get('usuario__last_name', '')}".strip()
                nombre = nombre_completo if nombre_completo else username
                lineas.append(f'  {i:2d}. {nombre:30s} {usuario["total_usos"]:5d} usos | {usuario["tiempo_promedio"]:.0f} ms promedio | {usuario["errores"]} errores')
            lineas.append('')
        
        # Anomalías (requests lentos)
        if anomalias.exists():
            lineas.append(f'⚠️ ANOMALÍAS DETECTADAS (>{umbral_lento}ms)')
            lineas.append('-' * 80)
            for i, metrica in enumerate(anomalias[:10], 1):
                usuario = metrica.usuario.username if metrica.usuario else 'Desconocido'
                fecha_str = metrica.fecha.strftime('%d/%m %H:%M')
                lineas.append(f'  {i:2d}. {fecha_str} | {usuario:15s} | {metrica.tiempo_total_ms:6d} ms | {"❌ Error" if metrica.tuvo_errores else "✅ OK"}')
                if metrica.error_detalle:
                    lineas.append(f'      Error: {metrica.error_detalle[:60]}...')
            lineas.append('')
        
        # Recomendaciones
        lineas.append('💡 RECOMENDACIONES')
        lineas.append('-' * 80)
        
        if stats['tasa_error'] > 5:
            lineas.append('  ⚠️ Tasa de error alta (>5%). Revisar logs de errores.')
        
        if stats.get('tiempo_promedio') and stats['tiempo_promedio'] > 3000:
            lineas.append('  ⚠️ Tiempo promedio alto (>3s). Considerar optimizaciones o upgrading de plan API.')
        
        if stats['tasa_cache_transcripcion'] < 20:
            lineas.append('  💡 Tasa de caché de transcripción baja. Considerar aumentar TTL del caché.')
        
        if stats['total_requests'] == 0:
            lineas.append('  ℹ️ No hay datos en este periodo. Sistema sin usar o problema de registro.')
        elif stats['total_requests'] < 10:
            lineas.append('  ℹ️ Pocos datos en este periodo. Ampliar rango para análisis más significativo.')
        else:
            lineas.append('  ✅ Sistema funcionando correctamente.')
        
        lineas.append('')
        lineas.append('=' * 80)
        
        return '\n'.join(lineas)
    
    def _enviar_email(self, reporte, email_destino, fecha_desde, fecha_hasta):
        """Envía el reporte por email"""
        try:
            asunto = f'📊 Reporte Métricas Dictado - {fecha_desde.strftime("%d/%m/%Y")} - {fecha_hasta.strftime("%d/%m/%Y")}'
            
            send_mail(
                subject=asunto,
                message=reporte,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email_destino],
                fail_silently=False,
            )
            
            logger.info(f"✅ Reporte enviado a {email_destino}")
        
        except Exception as e:
            logger.error(f"❌ Error enviando email: {str(e)}")
            self.stdout.write(self.style.ERROR(f'Error enviando email: {str(e)}'))
