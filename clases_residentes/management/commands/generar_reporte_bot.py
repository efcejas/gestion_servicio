"""
Comando de management para generar reportes de uso del bot de presentaciones.

Uso:
    python manage.py generar_reporte_bot [--dias=30] [--archivo=reporte.txt]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Avg, Q
from datetime import timedelta
from clases_residentes.models import ConversacionBot, MensajeBot
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Genera un reporte detallado de uso del bot de presentaciones'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=30,
            help='Número de días a analizar (default: 30)'
        )
        parser.add_argument(
            '--archivo',
            type=str,
            default=None,
            help='Guardar reporte en archivo (opcional)'
        )

    def handle(self, *args, **options):
        dias = options['dias']
        archivo = options['archivo']
        
        fecha_inicio = timezone.now() - timedelta(days=dias)
        
        self.stdout.write(self.style.SUCCESS(f'\n{"="*70}'))
        self.stdout.write(self.style.SUCCESS(f'REPORTE DE USO DEL BOT DE PRESENTACIONES'))
        self.stdout.write(self.style.SUCCESS(f'Período: Últimos {dias} días'))
        self.stdout.write(self.style.SUCCESS(f'{"="*70}\n'))
        
        lineas_reporte = []
        
        # 1. Estadísticas generales
        self.stdout.write(self.style.WARNING('📊 ESTADÍSTICAS GENERALES'))
        lineas_reporte.append('📊 ESTADÍSTICAS GENERALES')
        lineas_reporte.append('=' * 70)
        
        total_conversaciones = ConversacionBot.objects.filter(
            fecha_inicio__gte=fecha_inicio
        ).count()
        
        total_mensajes = MensajeBot.objects.filter(
            conversacion__fecha_inicio__gte=fecha_inicio
        ).count()
        
        mensajes_usuario = MensajeBot.objects.filter(
            conversacion__fecha_inicio__gte=fecha_inicio,
            rol='user'
        ).count()
        
        mensajes_bot = MensajeBot.objects.filter(
            conversacion__fecha_inicio__gte=fecha_inicio,
            rol='assistant'
        ).count()
        
        usuarios_unicos = ConversacionBot.objects.filter(
            fecha_inicio__gte=fecha_inicio
        ).values('usuario').distinct().count()
        
        promedio_mensajes = mensajes_usuario / total_conversaciones if total_conversaciones > 0 else 0
        
        linea = f"Total de conversaciones: {total_conversaciones}"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        linea = f"Total de mensajes: {total_mensajes} (Usuario: {mensajes_usuario}, Bot: {mensajes_bot})"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        linea = f"Usuarios únicos: {usuarios_unicos}"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        linea = f"Promedio de mensajes por conversación: {promedio_mensajes:.1f}"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        self.stdout.write("")
        lineas_reporte.append("")
        
        # 2. Feedback
        self.stdout.write(self.style.WARNING('👍 FEEDBACK DE USUARIOS'))
        lineas_reporte.append('👍 FEEDBACK DE USUARIOS')
        lineas_reporte.append('=' * 70)
        
        feedback_positivo = MensajeBot.objects.filter(
            conversacion__fecha_inicio__gte=fecha_inicio,
            rol='assistant',
            feedback='positivo'
        ).count()
        
        feedback_negativo = MensajeBot.objects.filter(
            conversacion__fecha_inicio__gte=fecha_inicio,
            rol='assistant',
            feedback='negativo'
        ).count()
        
        total_respuestas = mensajes_bot
        sin_feedback = total_respuestas - feedback_positivo - feedback_negativo
        
        tasa_feedback = ((feedback_positivo + feedback_negativo) / total_respuestas * 100) if total_respuestas > 0 else 0
        satisfaccion = (feedback_positivo / (feedback_positivo + feedback_negativo) * 100) if (feedback_positivo + feedback_negativo) > 0 else 0
        
        linea = f"Respuestas positivas: {feedback_positivo} ({feedback_positivo/total_respuestas*100:.1f}%)" if total_respuestas > 0 else "Respuestas positivas: 0"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        linea = f"Respuestas negativas: {feedback_negativo} ({feedback_negativo/total_respuestas*100:.1f}%)" if total_respuestas > 0 else "Respuestas negativas: 0"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        linea = f"Sin feedback: {sin_feedback} ({sin_feedback/total_respuestas*100:.1f}%)" if total_respuestas > 0 else "Sin feedback: 0"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        linea = f"Tasa de feedback: {tasa_feedback:.1f}%"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        linea = f"Índice de satisfacción: {satisfaccion:.1f}%"
        self.stdout.write(self.style.SUCCESS(f"  {linea}"))
        lineas_reporte.append(linea)
        
        self.stdout.write("")
        lineas_reporte.append("")
        
        # 3. Top usuarios más activos
        self.stdout.write(self.style.WARNING('🏆 TOP 10 USUARIOS MÁS ACTIVOS'))
        lineas_reporte.append('🏆 TOP 10 USUARIOS MÁS ACTIVOS')
        lineas_reporte.append('=' * 70)
        
        top_usuarios = ConversacionBot.objects.filter(
            fecha_inicio__gte=fecha_inicio
        ).values(
            'usuario__username',
            'usuario__first_name',
            'usuario__last_name'
        ).annotate(
            total_conversaciones=Count('id'),
            total_mensajes=Count('mensajes', filter=Q(mensajes__rol='user'))
        ).order_by('-total_mensajes')[:10]
        
        for idx, usuario in enumerate(top_usuarios, 1):
            nombre = f"{usuario['usuario__first_name']} {usuario['usuario__last_name']}" if usuario['usuario__first_name'] else usuario['usuario__username']
            linea = f"  {idx}. {nombre}: {usuario['total_conversaciones']} conversaciones, {usuario['total_mensajes']} mensajes"
            self.stdout.write(linea)
            lineas_reporte.append(linea)
        
        self.stdout.write("")
        lineas_reporte.append("")
        
        # 4. Análisis temporal
        self.stdout.write(self.style.WARNING('📅 DISTRIBUCIÓN TEMPORAL'))
        lineas_reporte.append('📅 DISTRIBUCIÓN TEMPORAL')
        lineas_reporte.append('=' * 70)
        
        # Por día de la semana
        dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        
        self.stdout.write("  Mensajes por día de la semana:")
        lineas_reporte.append("Mensajes por día de la semana:")
        
        for idx, dia in enumerate(dias_semana, 1):
            mensajes_dia = MensajeBot.objects.filter(
                timestamp__gte=fecha_inicio,
                timestamp__week_day=idx,
                rol='user'
            ).count()
            porcentaje = (mensajes_dia / mensajes_usuario * 100) if mensajes_usuario > 0 else 0
            barra = '█' * int(porcentaje / 2)
            linea = f"    {dia:10s}: {mensajes_dia:4d} mensajes {barra} ({porcentaje:.1f}%)"
            self.stdout.write(linea)
            lineas_reporte.append(linea)
        
        self.stdout.write("")
        lineas_reporte.append("")
        
        # 5. Preguntas con feedback negativo
        self.stdout.write(self.style.WARNING('⚠️  RESPUESTAS CON FEEDBACK NEGATIVO (últimas 5)'))
        lineas_reporte.append('⚠️  RESPUESTAS CON FEEDBACK NEGATIVO (últimas 5)')
        lineas_reporte.append('=' * 70)
        
        mensajes_negativos = MensajeBot.objects.filter(
            timestamp__gte=fecha_inicio,
            rol='assistant',
            feedback='negativo'
        ).select_related('conversacion').order_by('-timestamp')[:5]
        
        if mensajes_negativos:
            for msg in mensajes_negativos:
                # Obtener el mensaje anterior (pregunta del usuario)
                pregunta = MensajeBot.objects.filter(
                    conversacion=msg.conversacion,
                    timestamp__lt=msg.timestamp,
                    rol='user'
                ).order_by('-timestamp').first()
                
                linea = f"  • Pregunta: {pregunta.contenido[:100] if pregunta else 'N/A'}..."
                self.stdout.write(linea)
                lineas_reporte.append(linea)
                
                linea = f"    Respuesta: {msg.contenido[:100]}..."
                self.stdout.write(linea)
                lineas_reporte.append(linea)
                
                linea = f"    Usuario: {msg.conversacion.usuario.get_full_name() or msg.conversacion.usuario.username}"
                self.stdout.write(linea)
                lineas_reporte.append(linea)
                
                self.stdout.write("")
                lineas_reporte.append("")
        else:
            linea = "  ¡No hay respuestas con feedback negativo! 🎉"
            self.stdout.write(self.style.SUCCESS(linea))
            lineas_reporte.append(linea)
        
        self.stdout.write("")
        lineas_reporte.append("")
        
        # 6. Estadísticas de longitud de conversaciones
        self.stdout.write(self.style.WARNING('💬 LONGITUD DE CONVERSACIONES'))
        lineas_reporte.append('💬 LONGITUD DE CONVERSACIONES')
        lineas_reporte.append('=' * 70)
        
        conversaciones_con_mensajes = ConversacionBot.objects.filter(
            fecha_inicio__gte=fecha_inicio
        ).annotate(
            num_mensajes=Count('mensajes', filter=Q(mensajes__rol='user'))
        )
        
        conv_1_mensaje = conversaciones_con_mensajes.filter(num_mensajes=1).count()
        conv_2_5_mensajes = conversaciones_con_mensajes.filter(num_mensajes__gte=2, num_mensajes__lte=5).count()
        conv_6_10_mensajes = conversaciones_con_mensajes.filter(num_mensajes__gte=6, num_mensajes__lte=10).count()
        conv_mas_10 = conversaciones_con_mensajes.filter(num_mensajes__gt=10).count()
        
        linea = f"1 mensaje: {conv_1_mensaje} conversaciones"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        linea = f"2-5 mensajes: {conv_2_5_mensajes} conversaciones"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        linea = f"6-10 mensajes: {conv_6_10_mensajes} conversaciones"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        linea = f"Más de 10 mensajes: {conv_mas_10} conversaciones"
        self.stdout.write(f"  {linea}")
        lineas_reporte.append(linea)
        
        self.stdout.write(self.style.SUCCESS(f'\n{"="*70}'))
        self.stdout.write(self.style.SUCCESS('FIN DEL REPORTE'))
        self.stdout.write(self.style.SUCCESS(f'{"="*70}\n'))
        
        # Guardar en archivo si se especificó
        if archivo:
            with open(archivo, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lineas_reporte))
            self.stdout.write(self.style.SUCCESS(f'✅ Reporte guardado en: {archivo}'))
