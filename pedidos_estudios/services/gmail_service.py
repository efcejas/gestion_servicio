"""
Servicio para conexión y lectura de emails desde Gmail usando la API de Google.

Documentación oficial: https://developers.google.com/gmail/api/guides
"""
import base64
import json
import logging
import os
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

# Google API libraries
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    logging.warning("Google API libraries not installed. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")


logger = logging.getLogger(__name__)


class GmailService:
    """
    Servicio para interactuar con la API de Gmail.
    
    Requiere configuración de credenciales OAuth 2.0 de Google Cloud Console.
    
    Configuración requerida en settings.py:
    
    GMAIL_CONFIG = {
        'CREDENTIALS_FILE': 'path/to/credentials.json',  # Archivo de credenciales OAuth
        'TOKEN_FILE': 'path/to/token.json',  # Archivo donde se guarda el token
        'SCOPES': ['https://www.googleapis.com/auth/gmail.readonly'],
        'EMAIL_ADDRESS': 'solicitudestudioscolegiales@gmail.com',
    }
    """
    
    # Alcances de la API (permisos necesarios)
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify',  # Para marcar como leído
    ]
    
    def __init__(self):
        """Inicializa el servicio de Gmail."""
        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google API libraries required. Install with: "
                "pip install google-auth google-auth-oauthlib "
                "google-auth-httplib2 google-api-python-client"
            )
        
        self.service = None
        self.config = getattr(settings, 'GMAIL_CONFIG', {})
        self._authenticate()
    
    def _authenticate(self):
        """
        Autentica con Google OAuth 2.0 y construye el servicio de Gmail.
        
        Soporta dos modos:
        1. PRODUCCIÓN (Heroku): Lee credenciales desde variables de entorno
           - GMAIL_TOKEN_JSON: Token de acceso en formato JSON
           - GMAIL_CREDENTIALS_JSON: Credenciales OAuth (fallback)
        
        2. DESARROLLO: Lee desde archivos locales
           - token.json: Token generado localmente
           - credentials.json: Credenciales descargadas de Google Cloud
        
        El token se renueva automáticamente si está expirado.
        """
        creds = None
        token_file = self.config.get('TOKEN_FILE', 'token.json')
        credentials_file = self.config.get('CREDENTIALS_FILE', 'credentials.json')
        
        # MODO 1: Intentar cargar desde variables de entorno (PRODUCCIÓN)
        if os.getenv('GMAIL_TOKEN_JSON'):
            try:
                logger.info("Cargando token desde variable de entorno GMAIL_TOKEN_JSON")
                token_data = json.loads(os.getenv('GMAIL_TOKEN_JSON'))
                creds = Credentials.from_authorized_user_info(token_data, self.SCOPES)
                logger.info("✓ Token cargado exitosamente desde variable de entorno")
            except Exception as e:
                logger.error(f"Error cargando token desde variable de entorno: {e}")
        
        # MODO 2: Fallback a archivos locales (DESARROLLO)
        if not creds:
            try:
                if Path(token_file).exists():
                    logger.info(f"Cargando token desde archivo: {token_file}")
                    creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)
                    logger.info("✓ Token cargado exitosamente desde archivo")
            except Exception as e:
                logger.warning(f"No se pudo cargar token desde archivo: {e}")
        
        # Renovar token si está expirado
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info("Token expirado, renovando...")
                creds.refresh(Request())
                logger.info("✓ Token renovado exitosamente")
                
                # Guardar token renovado en archivo (solo en desarrollo)
                if Path(token_file).exists() or not os.getenv('GMAIL_TOKEN_JSON'):
                    try:
                        with open(token_file, 'w') as token:
                            token.write(creds.to_json())
                        logger.info(f"Token actualizado guardado en {token_file}")
                    except Exception as e:
                        logger.warning(f"No se pudo guardar token renovado: {e}")
                
                # En producción, informar que se debe actualizar la variable
                if os.getenv('GMAIL_TOKEN_JSON'):
                    logger.warning(
                        "ATENCION: Token renovado. Actualiza GMAIL_TOKEN_JSON en Heroku con: "
                        f"{creds.to_json()}"
                    )
            except Exception as e:
                logger.error(f"Error renovando token: {e}")
                creds = None
        
        # Si no hay credenciales válidas, intentar flujo OAuth (solo desarrollo)
        if not creds or not creds.valid:
            if os.getenv('HEROKU_APP_NAME') or os.getenv('DYNO'):
                # Estamos en producción, no podemos hacer flujo interactivo
                logger.error(
                    "No hay credenciales válidas en producción. "
                    "Configura GMAIL_TOKEN_JSON en las variables de entorno de Heroku."
                )
                raise ValueError(
                    "Gmail credentials not configured. Set GMAIL_TOKEN_JSON environment variable."
                )
            else:
                # Modo desarrollo: flujo OAuth interactivo
                logger.info("Iniciando flujo OAuth interactivo (solo desarrollo)...")
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_file, self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    
                    # Guardar credenciales para futuros usos
                    with open(token_file, 'w') as token:
                        token.write(creds.to_json())
                    logger.info(f"✓ Token generado y guardado en {token_file}")
                except Exception as e:
                    logger.error(f"Error en flujo OAuth: {e}")
                    raise
        
        # Construir servicio de Gmail
        try:
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("✓ Servicio de Gmail autenticado correctamente")
        except HttpError as error:
            logger.error(f"Error al construir servicio de Gmail: {error}")
            raise
    
    def obtener_emails_nuevos(
        self, 
        query: str = 'is:unread',
        max_results: int = 10,
        desde_fecha: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Obtiene emails desde Gmail.
        
        Args:
            query: Consulta de búsqueda de Gmail (ej: 'from:example@gmail.com is:unread')
            max_results: Máximo número de emails a obtener
            desde_fecha: Filtrar emails desde esta fecha
        
        Returns:
            Lista de diccionarios con datos de cada email
        
        Ejemplos de queries:
            - 'is:unread' - Emails no leídos
            - 'from:sanatorio@example.com' - De un remitente específico
            - 'subject:pedido estudio' - Con texto en asunto
            - 'after:2026/02/01' - Desde una fecha
        """
        if not self.service:
            logger.error("Servicio de Gmail no inicializado")
            return []
        
        # Agregar filtro de fecha si se proporciona
        if desde_fecha:
            fecha_str = desde_fecha.strftime('%Y/%m/%d')
            query = f"{query} after:{fecha_str}"
        
        try:
            # Listar mensajes que coinciden con la query
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                logger.info("No se encontraron emails nuevos")
                return []
            
            logger.info(f"Encontrados {len(messages)} emails")
            
            # Obtener detalles completos de cada mensaje
            emails_completos = []
            for message in messages:
                email_data = self._obtener_email_completo(message['id'])
                if email_data:
                    emails_completos.append(email_data)
            
            return emails_completos
        
        except HttpError as error:
            logger.error(f"Error al obtener emails: {error}")
            return []
    
    def _obtener_email_completo(self, message_id: str) -> Optional[Dict]:
        """
        Obtiene los detalles completos de un email específico.
        
        Args:
            message_id: ID del mensaje en Gmail
        
        Returns:
            Diccionario con todos los datos del email
        """
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extraer headers importantes
            headers = {}
            for header in message['payload'].get('headers', []):
                name = header['name'].lower()
                if name in ['from', 'to', 'subject', 'date', 'message-id']:
                    headers[name] = header['value']
            
            # Extraer cuerpo del mensaje
            body = self._extraer_cuerpo_mensaje(message['payload'])
            
            # Extraer adjuntos
            adjuntos = self._extraer_adjuntos(message['payload'], message_id)
            
            email_data = {
                'id': message_id,
                'message_id': headers.get('message-id', ''),
                'asunto': headers.get('subject', ''),
                'remitente': headers.get('from', ''),
                'destinatario': headers.get('to', ''),
                'fecha': self._parsear_fecha(headers.get('date', '')),
                'cuerpo_texto': body.get('texto', ''),
                'cuerpo_html': body.get('html', ''),
                'adjuntos': adjuntos,
                'thread_id': message.get('threadId', ''),
                'labels': message.get('labelIds', []),
                'raw_data': message,  # Datos crudos completos
            }
            
            return email_data
        
        except HttpError as error:
            logger.error(f"Error al obtener email {message_id}: {error}")
            return None
    
    def _extraer_cuerpo_mensaje(self, payload: Dict) -> Dict[str, str]:
        """
        Extrae el cuerpo del mensaje (texto plano y HTML).
        
        Args:
            payload: Payload del mensaje de Gmail
        
        Returns:
            Diccionario con 'texto' y 'html'
        """
        body = {'texto': '', 'html': ''}
        
        def decodificar_body(data):
            """Decodifica el cuerpo base64."""
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            return ''
        
        # Si el mensaje tiene partes múltiples
        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                
                if mime_type == 'text/plain':
                    if 'data' in part['body']:
                        body['texto'] = decodificar_body(part['body']['data'])
                
                elif mime_type == 'text/html':
                    if 'data' in part['body']:
                        body['html'] = decodificar_body(part['body']['data'])
                
                # Revisar subpartes recursivamente
                elif 'parts' in part:
                    sub_body = self._extraer_cuerpo_mensaje(part)
                    body['texto'] = body['texto'] or sub_body['texto']
                    body['html'] = body['html'] or sub_body['html']
        
        # Si el mensaje es simple (no multipart)
        elif 'body' in payload and 'data' in payload['body']:
            mime_type = payload.get('mimeType', '')
            contenido = decodificar_body(payload['body']['data'])
            
            if mime_type == 'text/plain':
                body['texto'] = contenido
            elif mime_type == 'text/html':
                body['html'] = contenido
        
        return body
    
    def _extraer_adjuntos(self, payload: Dict, message_id: str) -> List[Dict]:
        """
        Extrae información de los adjuntos del email.
        
        Args:
            payload: Payload del mensaje
            message_id: ID del mensaje
        
        Returns:
            Lista de diccionarios con info de adjuntos
        """
        adjuntos = []
        
        def procesar_parte(part):
            filename = part.get('filename', '')
            if filename:
                attachment_id = part['body'].get('attachmentId', '')
                mime_type = part.get('mimeType', '')
                size = part['body'].get('size', 0)
                
                adjuntos.append({
                    'nombre': filename,
                    'mime_type': mime_type,
                    'tamaño': size,
                    'attachment_id': attachment_id,
                    'message_id': message_id,
                })
        
        # Buscar adjuntos en las partes del mensaje
        if 'parts' in payload:
            for part in payload['parts']:
                procesar_parte(part)
                
                # Revisar subpartes
                if 'parts' in part:
                    for subpart in part['parts']:
                        procesar_parte(subpart)
        
        return adjuntos
    
    def descargar_adjunto(
        self, 
        message_id: str, 
        attachment_id: str
    ) -> Optional[bytes]:
        """
        Descarga un adjunto específico.
        
        Args:
            message_id: ID del mensaje
            attachment_id: ID del adjunto
        
        Returns:
            Bytes del archivo adjunto
        """
        try:
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            data = attachment.get('data', '')
            file_data = base64.urlsafe_b64decode(data)
            
            return file_data
        
        except HttpError as error:
            logger.error(f"Error al descargar adjunto: {error}")
            return None
    
    def marcar_como_leido(self, message_id: str) -> bool:
        """
        Marca un email como leído.
        
        Args:
            message_id: ID del mensaje
        
        Returns:
            True si fue exitoso
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            
            logger.info(f"Email {message_id} marcado como leído")
            return True
        
        except HttpError as error:
            logger.error(f"Error al marcar email como leído: {error}")
            return False
    
    def marcar_con_etiqueta(self, message_id: str, label_id: str) -> bool:
        """
        Agrega una etiqueta a un email.
        
        Args:
            message_id: ID del mensaje
            label_id: ID de la etiqueta (ej: 'INBOX', 'TRASH', o ID personalizado)
        
        Returns:
            True si fue exitoso
        """
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            
            logger.info(f"Etiqueta {label_id} agregada al email {message_id}")
            return True
        
        except HttpError as error:
            logger.error(f"Error al agregar etiqueta: {error}")
            return False
    
    def _parsear_fecha(self, fecha_str: str) -> Optional[datetime]:
        """
        Parsea el string de fecha del header del email.
        
        Args:
            fecha_str: String de fecha del header
        
        Returns:
            Objeto datetime o None
        """
        if not fecha_str:
            return None
        
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(fecha_str)
        except Exception as e:
            logger.warning(f"No se pudo parsear fecha '{fecha_str}': {e}")
            return None
    
    def obtener_info_cuenta(self) -> Dict:
        """
        Obtiene información de la cuenta de Gmail conectada.
        
        Returns:
            Diccionario con info de la cuenta
        """
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return {
                'email': profile.get('emailAddress', ''),
                'total_mensajes': profile.get('messagesTotal', 0),
                'total_threads': profile.get('threadsTotal', 0),
                'historyId': profile.get('historyId', ''),
            }
        except HttpError as error:
            logger.error(f"Error al obtener info de cuenta: {error}")
            return {}


# Funciones auxiliares para uso directo

def leer_emails_pendientes(max_resultados: int = 10) -> List[Dict]:
    """
    Helper function para leer emails no procesados.
    
    Args:
        max_resultados: Número máximo de emails a obtener
    
    Returns:
        Lista de emails
    """
    try:
        gmail = GmailService()
        query = getattr(settings, 'GMAIL_PEDIDOS_QUERY', 'is:unread')
        emails = gmail.obtener_emails_nuevos(query=query, max_results=max_resultados)
        return emails
    except Exception as e:
        logger.error(f"Error al leer emails pendientes: {e}")
        return []


def verificar_configuracion_gmail() -> Tuple[bool, str]:
    """
    Verifica que la configuración de Gmail esté correcta.
    
    Returns:
        Tupla (bool, str) - (éxito, mensaje)
    """
    if not GOOGLE_API_AVAILABLE:
        return False, "Librerías de Google API no instaladas"
    
    try:
        gmail = GmailService()
        info = gmail.obtener_info_cuenta()
        
        if info.get('email'):
            return True, f"Conectado a {info['email']} - {info['total_mensajes']} mensajes"
        else:
            return False, "No se pudo obtener información de la cuenta"
    
    except Exception as e:
        return False, f"Error de configuración: {str(e)}"
