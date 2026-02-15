"""
Servicio de notificaciones por email para pedidos de estudios.
"""
import logging
from typing import List, Optional, Dict
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from ..models import PedidoEstudio, TipoEstudio

logger = logging.getLogger(__name__)


class NotificadorPedidos:
    """
    Servicio para enviar notificaciones por email sobre pedidos de estudios.
    """
    
    def __init__(self):
        """Inicializa el notificador."""
        self.from_email = getattr(
            settings, 
            'DEFAULT_FROM_EMAIL', 
            'no-reply@sanatoriocolegiales.com.ar'
        )
        self.admin_emails = getattr(
            settings,
            'ADMINS',
            [('Admin', 'ecejas@sanatoriocolegiales.com.ar')]
        )
        # Extraer solo los emails de ADMINS
        self.admin_email_list = [email for name, email in self.admin_emails]
    
    def notificar_pedido(self, pedido: PedidoEstudio) -> bool:
        """
        Envía notificación de nuevo pedido al médico responsable.
        
        Args:
            pedido: Instancia de PedidoEstudio
        
        Returns:
            True si se envió correctamente
        """
        try:
            # Determinar destinatarios
            destinatarios = self._obtener_destinatarios(pedido)
            
            if not destinatarios:
                logger.warning(f"No hay destinatarios para pedido {pedido.id}")
                return False
            
            # Preparar contenido del email
            asunto = self._generar_asunto(pedido)
            contenido_html = self._generar_contenido_html(pedido)
            contenido_texto = strip_tags(contenido_html)
            
            # Enviar email
            email = EmailMultiAlternatives(
                subject=asunto,
                body=contenido_texto,
                from_email=self.from_email,
                to=destinatarios,
            )
            email.attach_alternative(contenido_html, "text/html")
            email.send(fail_silently=False)
            
            # Marcar como notificado
            pedido.notificacion_enviada = True
            pedido.fecha_notificacion = timezone.now()
            pedido.save()
            
            logger.info(f"Notificación enviada para pedido {pedido.id} a {destinatarios}")
            return True
        
        except Exception as e:
            logger.error(f"Error al enviar notificación de pedido {pedido.id}: {e}", exc_info=True)
            return False
    
    def notificar_cambio_estado(
        self, 
        pedido: PedidoEstudio, 
        nuevo_estado: str,
        notificar_a: Optional[List[str]] = None
    ) -> bool:
        """
        Notifica cambio de estado de un pedido.
        
        Args:
            pedido: Instancia de PedidoEstudio
            nuevo_estado: Nuevo estado del pedido
            notificar_a: Lista de emails adicionales (opcional)
        
        Returns:
            True si se envió correctamente
        """
        try:
            destinatarios = notificar_a or ['ecejas@sanatoriocolegiales.com.ar']
            
            asunto = f"Cambio de estado: Pedido #{pedido.id} - {pedido.get_estado_display()}"
            
            mensaje = (
                f"El pedido de estudio #{pedido.id} ha cambiado de estado.\n\n"
                f"Paciente: {pedido.paciente.nombre_completo}\n"
                f"Estudio: {pedido.descripcion_estudio}\n"
                f"Nuevo estado: {pedido.get_estado_display()}\n"
                f"Fecha: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')}\n"
            )
            
            send_mail(
                subject=asunto,
                message=mensaje,
                from_email=self.from_email,
                recipient_list=destinatarios,
                fail_silently=False,
            )
            
            logger.info(f"Notificación de cambio de estado enviada para pedido {pedido.id}")
            return True
        
        except Exception as e:
            logger.error(f"Error al notificar cambio de estado: {e}", exc_info=True)
            return False
    
    def _obtener_destinatarios(self, pedido: PedidoEstudio) -> List[str]:
        """
        Obtiene la lista de destinatarios para un pedido.
        
        Args:
            pedido: Instancia de PedidoEstudio
        
        Returns:
            Lista de emails
        """
        destinatarios = []
        
        # Médico asignado
        if pedido.medico_asignado and pedido.medico_asignado.email:
            destinatarios.append(pedido.medico_asignado.email)
        
        # Médico responsable del tipo de estudio
        elif pedido.tipo_estudio:
            if pedido.tipo_estudio.email_notificacion:
                destinatarios.append(pedido.tipo_estudio.email_notificacion)
            elif pedido.tipo_estudio.medico_responsable and pedido.tipo_estudio.medico_responsable.email:
                destinatarios.append(pedido.tipo_estudio.medico_responsable.email)
        
        # Email por defecto si no hay ninguno configurado
        if not destinatarios:
            email_default = getattr(
                settings, 
                'PEDIDOS_EMAIL_DEFAULT', 
                'ecejas@sanatoriocolegiales.com.ar'
            )
            destinatarios.append(email_default)
        
        return destinatarios
    
    def _generar_asunto(self, pedido: PedidoEstudio) -> str:
        """
        Genera el asunto del email de notificación.
        
        Args:
            pedido: Instancia de PedidoEstudio
        
        Returns:
            Asunto del email
        """
        prioridad_texto = f"[{pedido.get_prioridad_display().upper()}] " if pedido.prioridad != 'NORMAL' else ""
        
        tipo = pedido.tipo_estudio.nombre if pedido.tipo_estudio else "Estudio"
        
        return f"{prioridad_texto}Nuevo pedido: {tipo} - {pedido.paciente.nombre_completo}"
    
    def _generar_contenido_html(self, pedido: PedidoEstudio) -> str:
        """
        Genera el contenido HTML del email.
        
        Args:
            pedido: Instancia de PedidoEstudio
        
        Returns:
            HTML del email
        """
        # Por ahora, genera HTML simple
        # Podrías crear un template Django para esto
        
        prioridad_color = {
            'URGENTE': '#dc3545',
            'ALTA': '#fd7e14',
            'NORMAL': '#28a745',
            'BAJA': '#6c757d',
        }.get(pedido.prioridad, '#6c757d')
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .header {{ background-color: #007bff; color: white; padding: 20px; }}
                .content {{ padding: 20px; }}
                .badge {{ 
                    background-color: {prioridad_color}; 
                    color: white; 
                    padding: 5px 10px; 
                    border-radius: 3px;
                    font-weight: bold;
                }}
                .info-row {{ margin: 10px 0; }}
                .label {{ font-weight: bold; }}
                .footer {{ padding: 20px; background-color: #f8f9fa; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>Nuevo Pedido de Estudio</h2>
            </div>
            <div class="content">
                <div class="info-row">
                    <span class="badge">{pedido.get_prioridad_display()}</span>
                </div>
                
                <h3>Datos del Paciente</h3>
                <div class="info-row">
                    <span class="label">Nombre:</span> {pedido.paciente.nombre_completo}
                </div>
        """
        
        if pedido.paciente.historia_clinica:
            html += f"""
                <div class="info-row">
                    <span class="label">Historia Clínica:</span> {pedido.paciente.historia_clinica}
                </div>
            """
        
        if pedido.paciente.habitacion:
            html += f"""
                <div class="info-row">
                    <span class="label">Habitación:</span> {pedido.paciente.habitacion}
                    {f' Cama {pedido.paciente.cama}' if pedido.paciente.cama else ''}
                </div>
            """
        
        html += f"""
                <h3>Estudio Solicitado</h3>
                <div class="info-row">
                    <span class="label">Tipo:</span> {pedido.tipo_estudio or 'No especificado'}
                </div>
                <div class="info-row">
                    <span class="label">Descripción:</span> {pedido.descripcion_estudio}
                </div>
        """
        
        if pedido.indicacion_clinica:
            html += f"""
                <div class="info-row">
                    <span class="label">Indicación Clínica:</span> {pedido.indicacion_clinica}
                </div>
            """
        
        html += f"""
                <div class="info-row">
                    <span class="label">Médico Solicitante:</span> {pedido.medico_solicitante}
                </div>
                <div class="info-row">
                    <span class="label">Fecha Solicitud:</span> {timezone.localtime(pedido.fecha_solicitud).strftime('%d/%m/%Y %H:%M')}
                </div>
            </div>
            
            <div class="footer">
                <p>Este es un mensaje automático del sistema de gestión de estudios.</p>
                <p>Pedido ID: #{pedido.id}</p>
            </div>
        </body>
        </html>
        """
        
        return html


def notificar_pedido_nuevo(pedido: PedidoEstudio) -> bool:
    """
    Helper function para notificar un nuevo pedido.
    
    Args:
        pedido: Instancia de PedidoEstudio
    
    Returns:
        True si se envió correctamente
    """
    notificador = NotificadorPedidos()
    return notificador.notificar_pedido(pedido)


def notificar_error_procesamiento(
    error_msg: str,
    email_data: Optional[Dict] = None,
    traceback_info: Optional[str] = None
) -> bool:
    """
    Envía alerta por email a los administradores cuando hay un error en el procesamiento.
    
    Args:
        error_msg: Mensaje de error
        email_data: Datos del email que causó el error (opcional)
        traceback_info: Información del traceback (opcional)
    
    Returns:
        True si se envió correctamente
    """
    try:
        notificador = NotificadorPedidos()
        
        asunto = "[ALERTA] Error en procesamiento de pedidos de estudios"
        
        # Construir mensaje
        mensaje = f"Se detectó un error en el procesamiento de pedidos de estudios.\n\n"
        mensaje += f"Fecha y hora: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')}\n"
        mensaje += f"Error: {error_msg}\n\n"
        
        if email_data:
            mensaje += "Datos del email:\n"
            mensaje += f"  - Asunto: {email_data.get('asunto', 'N/A')}\n"
            mensaje += f"  - Remitente: {email_data.get('remitente', 'N/A')}\n"
            mensaje += f"  - Fecha: {email_data.get('fecha', 'N/A')}\n"
            mensaje += f"  - Message ID: {email_data.get('message_id', 'N/A')}\n\n"
        
        if traceback_info:
            mensaje += f"Traceback:\n{traceback_info}\n"
        
        # Enviar solo a administradores
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=notificador.from_email,
            recipient_list=notificador.admin_email_list,
            fail_silently=True,  # No queremos que un error al enviar notificación rompa el sistema
        )
        
        logger.info(f"Alerta de error enviada a administradores")
        return True
    
    except Exception as e:
        logger.error(f"Error al enviar alerta de error: {e}")
        return False


def notificar_pedido_urgente(pedido: PedidoEstudio) -> bool:
    """
    Envía notificación especial para pedidos urgentes.
    Incluye a los administradores además del médico responsable.
    
    Args:
        pedido: Instancia de PedidoEstudio
    
    Returns:
        True si se envió correctamente
    """
    try:
        notificador = NotificadorPedidos()
        
        # Obtener destinatarios normales + administradores
        destinatarios = notificador._obtener_destinatarios(pedido)
        
        # Agregar administradores para pedidos urgentes
        destinatarios.extend(notificador.admin_email_list)
        destinatarios = list(set(destinatarios))  # Eliminar duplicados
        
        # Asunto con prioridad
        asunto = f"[URGENTE] Nuevo pedido: {pedido.tipo_estudio or 'Estudio'} - {pedido.paciente.nombre_completo}"
        
        # Generar contenido HTML con estilo urgente
        contenido_html = notificador._generar_contenido_html(pedido)
        contenido_html = contenido_html.replace(
            '<div class="header">',
            '<div class="header" style="background-color: #dc3545;">'
        )
        
        contenido_texto = strip_tags(contenido_html)
        
        # Enviar email
        email = EmailMultiAlternatives(
            subject=asunto,
            body=contenido_texto,
            from_email=notificador.from_email,
            to=destinatarios,
        )
        email.attach_alternative(contenido_html, "text/html")
        email.send(fail_silently=False)
        
        # Marcar como notificado
        pedido.notificacion_enviada = True
        pedido.fecha_notificacion = timezone.now()
        pedido.save()
        
        logger.info(f"Notificación URGENTE enviada para pedido {pedido.id} a {destinatarios}")
        return True
    
    except Exception as e:
        logger.error(f"Error al enviar notificación urgente de pedido {pedido.id}: {e}", exc_info=True)
        return False

