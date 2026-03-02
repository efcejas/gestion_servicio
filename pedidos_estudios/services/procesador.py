"""
Procesador principal de emails de pedidos de estudios.

Este módulo coordina la lectura de emails, parsing y creación de pedidos.

MEJORAS IMPLEMENTADAS (03/03/2026):
- Búsqueda mejorada de tipos de estudio con 3 estrategias:
  1. Coincidencia exacta o muy cercana del tipo sugerido
  2. Búsqueda por múltiples palabras coincidentes
  3. Palabras clave prioritarias como fallback
- Logging detallado de decisiones de clasificación
- Score mínimo de 2 palabras coincidentes para mejor precisión
- Sistema de validación en 3 capas para rechazar emails no relacionados a pedidos:
  1. Detección de remitentes automáticos (no-reply, etc)
  2. Validación de contenido mínimo (tipo estudio + datos paciente)
  3. Score de confianza basado en completitud de información
"""
import logging
import time
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from django.core.files.base import ContentFile

from ..models import (
    PacienteEstudio, 
    TipoEstudio, 
    PedidoEstudio,
    AdjuntoEmail,
    LogProcesamientoEmail
)
from .gmail_service import GmailService
from .email_parser import EmailParser, serializar_datos_raw
from .notificador import NotificadorPedidos, notificar_error_procesamiento, notificar_pedido_urgente

logger = logging.getLogger(__name__)


# ============================================================================
# FUNCIONES DE VALIDACIÓN DE EMAILS
# ============================================================================

def es_email_automatico(email_data: Dict) -> Tuple[bool, str]:
    """
    Detecta si un email es automático/sistema y no un pedido legítimo.
    
    CAPA 1 de validación: Filtro rápido de emails de sistema.
    
    Args:
        email_data: Diccionario con datos del email
    
    Returns:
        Tupla (es_automatico, razón)
    """
    remitente = email_data.get('remitente', '').lower()
    asunto = email_data.get('asunto', '').lower()
    
    # Remitentes automáticos típicos
    remitentes_automaticos = [
        'no-reply', 'noreply', 'no_reply', 'donotreply',
        'alerts', 'security', 'notification', 'automated',
        'mailer-daemon', 'postmaster', 'daemon@',
        '@accounts.google.com', '@notify.google.com'
    ]
    
    for pattern in remitentes_automaticos:
        if pattern in remitente:
            return True, f"Remitente automático detectado: {pattern}"
    
    # Asuntos típicos de emails de sistema
    asuntos_sistema = [
        'alerta de seguridad', 'security alert', 'security code',
        'verificación', 'verification', 'verify your',
        'password reset', 'contraseña', 'reset password',
        'activación de cuenta', 'account activation',
        'confirm your email', 'confirma tu email',
        'two-factor', '2fa', 'código de verificación',
        'se ha activado', 'has been enabled'
    ]
    
    for pattern in asuntos_sistema:
        if pattern in asunto:
            return True, f"Asunto de sistema detectado: {pattern}"
    
    return False, "No parece email automático"


def tiene_datos_minimos_pedido(datos_parseados: Dict) -> Tuple[bool, str]:
    """
    Verifica que el email tenga información mínima para ser un pedido válido.
    
    CAPA 2 de validación: Contenido mínimo requerido.
    
    Args:
        datos_parseados: Diccionario con datos parseados del email
    
    Returns:
        Tupla (es_valido, razón)
    """
    # Debe tener tipo de estudio sugerido (buscar ambos nombres de campo por compatibilidad)
    tipo_sugerido = datos_parseados['estudio'].get('tipo_estudio_sugerido') or datos_parseados['estudio'].get('tipo_sugerido', '')
    if not tipo_sugerido or len(str(tipo_sugerido).strip()) < 3:
        return False, "No tiene tipo de estudio identificable"
    
    # Debe tener al menos UN dato del paciente
    paciente = datos_parseados['paciente']
    tiene_nombre = paciente.get('nombre_completo') and len(paciente['nombre_completo']) > 3
    tiene_dni = paciente.get('dni')
    tiene_hc = paciente.get('historia_clinica')
    
    if not (tiene_nombre or tiene_dni or tiene_hc):
        return False, "No tiene datos de paciente identificable"
    
    return True, "Tiene datos mínimos suficientes"


def calcular_score_confianza(datos_parseados: Dict) -> Tuple[int, Dict[str, int]]:
    """
    Calcula un score de confianza (0-100) de que el email es un pedido legítimo.
    
    CAPA 3 de validación: Score basado en completitud de información.
    
    Args:
        datos_parseados: Diccionario con datos parseados del email
    
    Returns:
        Tupla (score_total, desglose_puntos)
    """
    desglose = {}
    
    # Tipo de estudio encontrado (+40 pts)
    # Buscar ambos nombres de campo por compatibilidad
    tipo_estudio = datos_parseados['estudio'].get('tipo_estudio_sugerido') or datos_parseados['estudio'].get('tipo_sugerido')
    if tipo_estudio:
        desglose['tipo_estudio'] = 40
    else:
        desglose['tipo_estudio'] = 0
    
    # Datos de paciente (+30 pts total)
    if datos_parseados['paciente'].get('nombre_completo'):
        desglose['nombre_paciente'] = 15
    else:
        desglose['nombre_paciente'] = 0
        
    if datos_parseados['paciente'].get('dni'):
        desglose['dni'] = 10
    else:
        desglose['dni'] = 0
        
    if datos_parseados['paciente'].get('historia_clinica'):
        desglose['historia_clinica'] = 5
    else:
        desglose['historia_clinica'] = 0
    
    # Datos adicionales del estudio (+20 pts total)
    if datos_parseados['estudio'].get('descripcion'):
        desglose['descripcion'] = 10
    else:
        desglose['descripcion'] = 0
        
    if datos_parseados['estudio'].get('medico_solicitante'):
        desglose['medico_solicitante'] = 10
    else:
        desglose['medico_solicitante'] = 0
    
    # Prioridad definida (+10 pts)
    if datos_parseados.get('prioridad') and datos_parseados['prioridad'] != 'NORMAL':
        desglose['prioridad'] = 10
    else:
        desglose['prioridad'] = 0
    
    score_total = sum(desglose.values())
    return score_total, desglose


def validar_email_es_pedido(email_data: Dict, datos_parseados: Dict) -> Tuple[bool, str, int]:
    """
    Valida si un email es realmente un pedido legítimo usando las 3 capas.
    
    Args:
        email_data: Datos crudos del email
        datos_parseados: Datos parseados del email
    
    Returns:
        Tupla (es_valido, razon, score)
    """
    from django.conf import settings
    
    # CAPA 1: Detectar emails automáticos
    es_automatico, razon_auto = es_email_automatico(email_data)
    if es_automatico:
        logger.warning(f"Email rechazado - {razon_auto}")
        return False, razon_auto, 0
    
    # CAPA 2: Verificar datos mínimos
    tiene_minimos, razon_minimos = tiene_datos_minimos_pedido(datos_parseados)
    if not tiene_minimos:
        logger.warning(f"Email rechazado - {razon_minimos}")
        return False, razon_minimos, 0
    
    # CAPA 3: Calcular score de confianza
    score, desglose = calcular_score_confianza(datos_parseados)
    score_minimo = getattr(settings, 'PEDIDOS_SCORE_MINIMO', 50)
    
    if score < score_minimo:
        razon = f"Score de confianza insuficiente: {score}/{score_minimo}. Desglose: {desglose}"
        logger.warning(f"Email rechazado - {razon}")
        return False, razon, score
    
    logger.info(f"Email validado como pedido legítimo - Score: {score}/100. Desglose: {desglose}")
    return True, "Validación exitosa", score


# ============================================================================
# PROCESADOR PRINCIPAL
# ============================================================================

class ProcesadorPedidos:
    """
    Procesador principal que coordina todo el flujo de trabajo.
    
    Flujo:
    1. Leer emails nuevos desde Gmail
    2. Parsear contenido y extraer datos
    3. Crear o actualizar pacientes
    4. Crear pedidos de estudios
    5. Guardar adjuntos
    6. Enviar notificaciones
    7. Marcar email como procesado
    """
    
    def __init__(self):
        """Inicializa el procesador."""
        self.gmail = None
        self.parser = EmailParser()
        self.notificador = NotificadorPedidos()
    
    def procesar_emails_pendientes(
        self, 
        max_emails: int = 10,
        marcar_como_leido: bool = True,
        enviar_notificaciones: bool = True
    ) -> Dict[str, int]:
        """
        Procesa todos los emails pendientes.
        
        Args:
            max_emails: Número máximo de emails a procesar
            marcar_como_leido: Si debe marcar los emails como leídos
            enviar_notificaciones: Si debe enviar notificaciones
        
        Returns:
            Diccionario con estadísticas del procesamiento:
            {
                'procesados': int,
                'exitosos': int,
                'errores': int,
                'duplicados': int,
                'rechazados': int
            }
        """
        stats = {
            'procesados': 0,
            'exitosos': 0,
            'errores': 0,
            'duplicados': 0,
            'rechazados': 0,
        }
        
        try:
            # Conectar a Gmail
            self.gmail = GmailService()
            
            # Obtener emails nuevos (sin filtrar por remitente)
            logger.info(f"Buscando emails pendientes (max: {max_emails})")
            emails = self.gmail.obtener_emails_nuevos(max_results=max_emails)
            
            if not emails:
                logger.info("No hay emails pendientes para procesar")
                return stats
            
            logger.info(f"Procesando {len(emails)} emails")
            
            # Procesar cada email
            for email_data in emails:
                stats['procesados'] += 1
                
                resultado, pedido = self.procesar_email_individual(
                    email_data,
                    enviar_notificacion=enviar_notificaciones
                )
                
                if resultado in ['EXITO', 'MULTIPLES']:
                    stats['exitosos'] += 1
                    
                    # Marcar como leído si fue exitoso
                    if marcar_como_leido:
                        self.gmail.marcar_como_leido(email_data['id'])
                
                elif resultado == 'DUPLICADO':
                    stats['duplicados'] += 1
                    
                    # También marcar duplicados como leídos
                    if marcar_como_leido:
                        self.gmail.marcar_como_leido(email_data['id'])
                
                elif resultado == 'RECHAZADO':
                    stats['rechazados'] += 1
                    
                    # Marcar rechazados como leídos (no son pedidos válidos)
                    if marcar_como_leido:
                        self.gmail.marcar_como_leido(email_data['id'])
                
                elif resultado == 'PARCIAL':
                    stats['exitosos'] += 1  # Considerar parcial como exitoso
                    
                    if marcar_como_leido:
                        self.gmail.marcar_como_leido(email_data['id'])
                
                else:
                    stats['errores'] += 1
            
            logger.info(
                f"Procesamiento completado: {stats['exitosos']} exitosos, "
                f"{stats['errores']} errores, {stats['duplicados']} duplicados, "
                f"{stats['rechazados']} rechazados"
            )
            
        except Exception as e:
            logger.error(f"Error en procesamiento de emails: {e}", exc_info=True)
        
        return stats
    
    @transaction.atomic
    def procesar_email_individual(
        self, 
        email_data: Dict,
        enviar_notificacion: bool = True
    ) -> Tuple[str, Optional[PedidoEstudio]]:
        """
        Procesa un email individual y crea el/los pedido(s).
        
        Detecta automáticamente si el email contiene múltiples estudios
        y los procesa todos.
        
        Args:
            email_data: Datos del email desde GmailService
            enviar_notificacion: Si debe enviar notificación
        
        Returns:
            Tupla (resultado, pedido):
            - resultado: 'EXITO', 'ERROR', 'DUPLICADO', 'PARCIAL', 'MULTIPLES'
            - pedido: Instancia del primer PedidoEstudio o None
        """
        tiempo_inicio = time.time()
        
        # Inicializar variables para el bloque finally
        pedido = None
        resultado = 'ERROR'
        mensaje = ''
        errores = []
        
        try:
            message_id = email_data.get('message_id', '')
            
            # Verificar si ya fue procesado
            if self._email_ya_procesado(message_id):
                logger.info(f"Email {message_id} ya fue procesado previamente")
                self._registrar_log(email_data, 'DUPLICADO', None, "Email ya procesado", [], time.time() - tiempo_inicio)
                return ('DUPLICADO', None)
            
            # Parsear email (detecta automáticamente múltiples estudios)
            logger.info(f"Parseando email: {email_data.get('asunto', '')}")
            estudios_parseados = self.parser.parsear_multiples_estudios(email_data)
            
            # VALIDACIÓN: Verificar que el primer estudio sea un pedido legítimo
            # Si el email tiene múltiples estudios, validamos solo el primero como representativo
            es_valido, razon_validacion, score = validar_email_es_pedido(
                email_data, 
                estudios_parseados[0]
            )
            
            if not es_valido:
                resultado = 'RECHAZADO'
                mensaje = f"Email rechazado: {razon_validacion}"
                logger.warning(mensaje)
                self._registrar_log(
                    email_data, 
                    resultado, 
                    None, 
                    mensaje, 
                    [razon_validacion],
                    time.time() - tiempo_inicio
                )
                return (resultado, None)
            
            if len(estudios_parseados) > 1:
                # Email con múltiples estudios
                logger.info(f"Detectados {len(estudios_parseados)} estudios en el email")
                return self._procesar_multiples_estudios(
                    email_data, 
                    estudios_parseados, 
                    enviar_notificacion, 
                    tiempo_inicio
                )
            
            # Email con un solo estudio (proceso normal)
            datos_parseados = estudios_parseados[0]
            pedido = None
            resultado = 'ERROR'
            mensaje = ''
            errores = []
            
            errores.extend(datos_parseados.get('errores', []))
            errores.extend(datos_parseados.get('advertencias_validacion', []))
            
            # Crear o actualizar paciente
            paciente = self._crear_o_actualizar_paciente(datos_parseados['paciente'])
            
            # Determinar tipo de estudio
            tipo_estudio = self._determinar_tipo_estudio(datos_parseados['estudio'])
            
            # Crear pedido
            pedido = self._crear_pedido(
                paciente=paciente,
                tipo_estudio=tipo_estudio,
                datos_estudio=datos_parseados['estudio'],
                datos_metadata=datos_parseados['metadata'],
                prioridad=datos_parseados['prioridad'],
                datos_raw=datos_parseados['datos_raw']
            )
            
            # Guardar adjuntos
            self._guardar_adjuntos(pedido, email_data.get('adjuntos', []))
            
            # Enviar notificación
            if enviar_notificacion:
                # Notificación especial para pedidos urgentes
                if pedido.prioridad == 'URGENTE':
                    if notificar_pedido_urgente(pedido):
                        logger.info(f"Notificación URGENTE enviada para pedido {pedido.id}")
                    else:
                        errores.append("No se pudo enviar notificación urgente")
                else:
                    # Notificación normal
                    if self.notificador.notificar_pedido(pedido):
                        logger.info(f"Notificación enviada para pedido {pedido.id}")
                    else:
                        errores.append("No se pudo enviar notificación")
            
            resultado = 'PARCIAL' if errores else 'EXITO'
            mensaje = f"Pedido #{pedido.id} creado exitosamente"
            
            if errores:
                mensaje += f" con {len(errores)} advertencias"
            
            logger.info(mensaje)
        
        except Exception as e:
            resultado = 'ERROR'
            mensaje = f"Error al procesar email: {str(e)}"
            errores = [str(e)]
            pedido = None
            logger.error(mensaje, exc_info=True)
            
            # Enviar alerta de error a administradores
            import traceback
            traceback_str = traceback.format_exc()
            notificar_error_procesamiento(
                error_msg=str(e),
                email_data=email_data,
                traceback_info=traceback_str
            )
        
        finally:
            # Registrar log de procesamiento
            tiempo_procesamiento = time.time() - tiempo_inicio
            self._registrar_log(
                email_data, 
                resultado, 
                pedido, 
                mensaje, 
                errores,
                tiempo_procesamiento
            )
        
        return (resultado, pedido)
    
    def _procesar_multiples_estudios(
        self,
        email_data: Dict,
        estudios_parseados: List[Dict],
        enviar_notificacion: bool,
        tiempo_inicio: float
    ) -> Tuple[str, Optional[PedidoEstudio]]:
        """
        Procesa un email que contiene múltiples estudios.
        
        Args:
            email_data: Datos del email original
            estudios_parseados: Lista de estudios parseados
            enviar_notificacion: Si debe enviar notificaciones
            tiempo_inicio: Tiempo de inicio del procesamiento
        
        Returns:
            Tupla (resultado, primer_pedido)
        """
        pedidos_creados = []
        errores_totales = []
        resultado = 'EXITO'
        
        logger.info(f"Procesando {len(estudios_parseados)} estudios del email")
        
        for i, datos_parseados in enumerate(estudios_parseados, 1):
            try:
                errores = []
                errores.extend(datos_parseados.get('errores', []))
                errores.extend(datos_parseados.get('advertencias_validacion', []))
                
                # Crear o actualizar paciente
                paciente = self._crear_o_actualizar_paciente(datos_parseados['paciente'])
                logger.info(f"Estudio {i}/{len(estudios_parseados)}: Paciente {paciente}")
                
                # Determinar tipo de estudio
                tipo_estudio = self._determinar_tipo_estudio(datos_parseados['estudio'])
                
                # Crear pedido (con sufijo único si hay múltiples estudios)
                pedido = self._crear_pedido(
                    paciente=paciente,
                    tipo_estudio=tipo_estudio,
                    datos_estudio=datos_parseados['estudio'],
                    datos_metadata=datos_parseados['metadata'],
                    prioridad=datos_parseados['prioridad'],
                    datos_raw=datos_parseados['datos_raw'],
                    indice_estudio=i if len(estudios_parseados) > 1 else None
                )
                
                # Solo guardar adjuntos en el primer pedido (son compartidos)
                if i == 1:
                    self._guardar_adjuntos(pedido, email_data.get('adjuntos', []))
                
                # Enviar notificación
                if enviar_notificacion:
                    if pedido.prioridad == 'URGENTE':
                        if notificar_pedido_urgente(pedido):
                            logger.info(f"Notificación URGENTE enviada para pedido {pedido.id}")
                        else:
                            errores.append("No se pudo enviar notificación urgente")
                    else:
                        if self.notificador.notificar_pedido(pedido):
                            logger.info(f"Notificación enviada para pedido {pedido.id}")
                        else:
                            errores.append("No se pudo enviar notificación")
                
                pedidos_creados.append(pedido)
                
                if errores:
                    errores_totales.extend(errores)
                    resultado = 'PARCIAL'
                
                logger.info(f"Pedido #{pedido.id} creado (estudio {i}/{len(estudios_parseados)})")
            
            except Exception as e:
                error_msg = f"Error en estudio {i}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errores_totales.append(error_msg)
                resultado = 'PARCIAL'
        
        # Registrar log del procesamiento
        mensaje = f"Procesados {len(pedidos_creados)}/{len(estudios_parseados)} estudios del email"
        if errores_totales:
            mensaje += f" con {len(errores_totales)} errores"
        
        tiempo_procesamiento = time.time() - tiempo_inicio
        self._registrar_log(
            email_data, 
            resultado if pedidos_creados else 'ERROR',
            pedidos_creados[0] if pedidos_creados else None,
            mensaje,
            errores_totales,
            tiempo_procesamiento
        )
        
        logger.info(mensaje)
        
        # Retornar el primer pedido creado
        return (
            'MULTIPLES' if len(pedidos_creados) > 1 else resultado,
            pedidos_creados[0] if pedidos_creados else None
        )
    
    def _email_ya_procesado(self, message_id: str) -> bool:
        """
        Verifica si un email ya fue procesado.
        
        Busca tanto el message_id exacto como aquellos que empiezan con el message_id
        (en caso de emails con múltiples estudios que tienen sufijos -estudio1, -estudio2, etc.)
        
        Args:
            message_id: Message-ID del email
        
        Returns:
            True si ya fue procesado
        """
        if not message_id:
            return False
        
        # Buscar pedidos con el message_id exacto o que empiecen con el message_id
        # Esto cubre tanto emails simples como los con múltiples estudios (con sufijos)
        return PedidoEstudio.objects.filter(
            email_message_id__startswith=message_id
        ).exists()
    
    def _crear_o_actualizar_paciente(self, datos_paciente: Dict) -> PacienteEstudio:
        """
        Crea o actualiza un paciente.
        
        Args:
            datos_paciente: Datos del paciente parseados
        
        Returns:
            Instancia de PacienteEstudio
        """
        historia_clinica = datos_paciente.get('historia_clinica')
        
        # Intentar encontrar por historia clínica
        if historia_clinica:
            paciente = PacienteEstudio.objects.filter(
                historia_clinica=historia_clinica
            ).first()
            
            if paciente:
                # Actualizar datos si están vacíos
                self._actualizar_datos_paciente(paciente, datos_paciente)
                return paciente
        
        # Crear nuevo paciente
        paciente = PacienteEstudio.objects.create(
            nombre_completo=datos_paciente.get('nombre_completo') or 'Paciente sin nombre',
            dni=datos_paciente.get('dni'),
            historia_clinica=historia_clinica,
            habitacion=datos_paciente.get('habitacion'),
            cama=datos_paciente.get('cama'),
            piso=datos_paciente.get('piso'),
            obra_social=datos_paciente.get('obra_social'),
        )
        
        logger.info(f"Paciente creado: {paciente.nombre_completo}")
        return paciente
    
    def _actualizar_datos_paciente(
        self, 
        paciente: PacienteEstudio, 
        nuevos_datos: Dict
    ):
        """
        Actualiza datos del paciente si los nuevos son más completos.
        
        Args:
            paciente: Instancia de PacienteEstudio
            nuevos_datos: Nuevos datos parseados
        """
        actualizado = False
        
        campos = ['habitacion', 'cama', 'piso', 'dni', 'obra_social']
        
        for campo in campos:
            valor_actual = getattr(paciente, campo, None)
            valor_nuevo = nuevos_datos.get(campo)
            
            if valor_nuevo and not valor_actual:
                setattr(paciente, campo, valor_nuevo)
                actualizado = True
        
        if actualizado:
            paciente.save()
            logger.info(f"Paciente {paciente.id} actualizado")
    
    def _determinar_tipo_estudio(self, datos_estudio: Dict) -> Optional[TipoEstudio]:
        """
        Intenta determinar el tipo de estudio desde el catálogo.
        
        Usa una estrategia mejorada:
        1. Busca coincidencia exacta o muy cercana del tipo sugerido
        2. Busca por frases completas en la descripción
        3. Como último recurso, busca por palabras clave
        
        Args:
            datos_estudio: Datos del estudio parseados
        
        Returns:
            Instancia de TipoEstudio o None
        """
        tipo_sugerido = datos_estudio.get('tipo_estudio_sugerido')
        descripcion = datos_estudio.get('descripcion_estudio', '')
        
        # Estrategia 1: Búsqueda por tipo sugerido (más confiable)
        if tipo_sugerido:
            # Búsqueda exacta primero
            tipo = TipoEstudio.objects.filter(
                nombre__iexact=tipo_sugerido,
                activo=True
            ).first()
            
            if tipo:
                logger.info(f"Tipo encontrado (exacto): {tipo.nombre}")
                return tipo
            
            # Búsqueda por contiene (caso insensitive)
            tipo = TipoEstudio.objects.filter(
                nombre__icontains=tipo_sugerido,
                activo=True
            ).first()
            
            if tipo:
                logger.info(f"Tipo encontrado (contiene): {tipo.nombre}")
                return tipo
        
        # Estrategia 2: Búsqueda por frases en la descripción
        if descripcion:
            descripcion_lower = descripcion.lower()
            
            # Obtener todos los tipos activos y buscar coincidencias
            tipos = TipoEstudio.objects.filter(activo=True)
            mejor_coincidencia = None
            max_palabras_coincidentes = 0
            
            for tipo in tipos:
                nombre_lower = tipo.nombre.lower()
                palabras_tipo = set(nombre_lower.split())
                palabras_desc = set(descripcion_lower.split())
                
                # Contar palabras coincidentes (excluyendo palabras cortas comunes)
                palabras_tipo_significativas = {p for p in palabras_tipo if len(p) > 3}
                coincidencias = palabras_tipo_significativas & palabras_desc
                
                if coincidencias and len(coincidencias) > max_palabras_coincidentes:
                    max_palabras_coincidentes = len(coincidencias)
                    mejor_coincidencia = tipo
            
            if mejor_coincidencia and max_palabras_coincidentes >= 2:
                logger.info(f"Tipo encontrado (múltiples palabras): {mejor_coincidencia.nombre}")
                return mejor_coincidencia
        
        # Estrategia 3: Búsqueda por palabras clave individuales (último recurso)
        if descripcion:
            # Palabras clave específicas y prioritarias
            palabras_prioritarias = ['mmii', 'mmss', 'carotideo', 'renal', 'cardiograma', 'testicular']
            descripcion_lower = descripcion.lower()
            
            for palabra_clave in palabras_prioritarias:
                if palabra_clave in descripcion_lower:
                    tipo = TipoEstudio.objects.filter(
                        nombre__icontains=palabra_clave,
                        activo=True
                    ).first()
                    
                    if tipo:
                        logger.info(f"Tipo encontrado (palabra clave): {tipo.nombre}")
                        return tipo
        
        logger.warning(f"No se pudo determinar tipo de estudio para: {descripcion}")
        return None
    
    def _crear_pedido(
        self,
        paciente: PacienteEstudio,
        tipo_estudio: Optional[TipoEstudio],
        datos_estudio: Dict,
        datos_metadata: Dict,
        prioridad: str,
        datos_raw: Dict,
        indice_estudio: Optional[int] = None
    ) -> PedidoEstudio:
        """
        Crea un nuevo pedido de estudio.
        
        Args:
            paciente: Instancia de PacienteEstudio
            tipo_estudio: Instancia de TipoEstudio o None
            datos_estudio: Datos del estudio parseados
            datos_metadata: Metadata del email
            prioridad: Prioridad del pedido
            datos_raw: Datos crudos completos
            indice_estudio: Índice del estudio si hay múltiples (1, 2, 3...)
        
        Returns:
            Instancia de PedidoEstudio
        """
        # Si hay múltiples estudios, agregar sufijo al email_message_id para hacerlo único
        email_message_id = datos_metadata.get('email_message_id')
        if indice_estudio is not None and email_message_id:
            email_message_id = f"{email_message_id}-estudio{indice_estudio}"
        
        pedido = PedidoEstudio.objects.create(
            paciente=paciente,
            tipo_estudio=tipo_estudio,
            descripcion_estudio=datos_estudio.get('descripcion_estudio') or 'Sin descripción',
            indicacion_clinica=datos_estudio.get('indicacion_clinica') or '',
            medico_solicitante=datos_estudio.get('medico_solicitante') or 'No especificado',
            estado='PENDIENTE',
            prioridad=prioridad,
            email_message_id=email_message_id,
            email_asunto=datos_metadata.get('email_asunto'),
            email_remitente=datos_metadata.get('email_remitente'),
            email_fecha=datos_metadata.get('email_fecha'),
            datos_raw=datos_raw,
            procesado_automaticamente=True,
            requiere_revision=True,  # Siempre requiere revisión inicial
        )
        
        logger.info(f"Pedido {pedido.id} creado para {paciente.nombre_completo}")
        return pedido
    
    def _guardar_adjuntos(self, pedido: PedidoEstudio, adjuntos: List[Dict]):
        """
        Descarga y guarda los adjuntos del email.
        
        Args:
            pedido: Instancia de PedidoEstudio
            adjuntos: Lista de adjuntos del email
        """
        if not adjuntos or not self.gmail:
            return
        
        for adjunto_info in adjuntos:
            try:
                # Descargar adjunto desde Gmail
                contenido = self.gmail.descargar_adjunto(
                    adjunto_info['message_id'],
                    adjunto_info['attachment_id']
                )
                
                if contenido:
                    # Crear registro de adjunto
                    adjunto = AdjuntoEmail(
                        pedido=pedido,
                        nombre_archivo=adjunto_info['nombre'],
                        tipo_mime=adjunto_info['mime_type'],
                        tamaño=adjunto_info['tamaño'],
                    )
                    
                    # Guardar archivo
                    adjunto.archivo.save(
                        adjunto_info['nombre'],
                        ContentFile(contenido),
                        save=True
                    )
                    
                    logger.info(f"Adjunto guardado: {adjunto_info['nombre']}")
            
            except Exception as e:
                logger.error(f"Error al guardar adjunto {adjunto_info['nombre']}: {e}")
    
    def _registrar_log(
        self,
        email_data: Dict,
        resultado: str,
        pedido: Optional[PedidoEstudio],
        mensaje: str,
        errores: List[str],
        tiempo_procesamiento: float
    ):
        """
        Registra el resultado del procesamiento en el log.
        
        Args:
            email_data: Datos del email
            resultado: Resultado del procesamiento
            pedido: Pedido creado o None
            mensaje: Mensaje descriptivo
            errores: Lista de errores
            tiempo_procesamiento: Tiempo en segundos
        """
        try:
            LogProcesamientoEmail.objects.create(
                email_message_id=email_data.get('message_id', ''),
                email_asunto=email_data.get('asunto', ''),
                email_remitente=email_data.get('remitente', ''),
                email_fecha=email_data.get('fecha') or timezone.now(),
                resultado=resultado,
                pedido_creado=pedido,
                mensaje=mensaje,
                datos_extraidos=serializar_datos_raw(email_data),  # Serializar para JSON
                errores=errores,
                tiempo_procesamiento=tiempo_procesamiento,
            )
        except Exception as e:
            logger.error(f"Error al registrar log: {e}")


# Funciones helper para uso en management commands o tasks

def procesar_emails_ahora(max_emails: int = 10) -> Dict[str, int]:
    """
    Helper function para procesar emails inmediatamente.
    
    Args:
        max_emails: Número máximo de emails a procesar
    
    Returns:
        Estadísticas del procesamiento
    """
    procesador = ProcesadorPedidos()
    return procesador.procesar_emails_pendientes(max_emails=max_emails)
