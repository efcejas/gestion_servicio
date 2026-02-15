"""
Parser de emails para extraer información de pedidos de estudios.

Este módulo procesa el contenido de emails y extrae datos estructurados
de pacientes y estudios solicitados.
"""
import re
import logging
import json
from typing import Dict, Optional, List, Any
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def serializar_datos_raw(datos: Dict) -> Dict:
    """
    Convierte objetos datetime a strings ISO para que sean serializables en JSON.
    
    Args:
        datos: Diccionario con datos del email
    
    Returns:
        Diccionario con valores serializables
    """
    datos_serializables = {}
    for key, value in datos.items():
        if isinstance(value, datetime):
            datos_serializables[key] = value.isoformat()
        elif isinstance(value, dict):
            datos_serializables[key] = serializar_datos_raw(value)
        elif isinstance(value, list):
            datos_serializables[key] = [
                item.isoformat() if isinstance(item, datetime) else item
                for item in value
            ]
        else:
            datos_serializables[key] = value
    return datos_serializables


class EmailParser:
    """
    Parser flexible para extraer información de pedidos de estudios desde emails.
    
    IMPORTANTE: Los patrones de extracción deben ajustarse según el formato
    real de los emails que lleguen del sanatorio.
    
    Este es un esqueleto base que deberás personalizar cuando recibas
    el primer email real.
    """
    
    # Patrones regex para extraer información (MEJORADO para formato Sanatorio)
    PATRONES = {
        'nombre_completo': [
            r'apellido\s+y\s+nombre\s*:?\s*([a-záéíóúñ]{2,}(?:\s*,?\s*[a-záéíóúñ]+)*)(?=\s*(?:\n|documento|dni|historia|habitaci[oó]n))',
            r'paciente\s*:?\s*([a-záéíóúñ][a-záéíóúñ\s,]+?)(?=\s*(?:dni|documento|historia|habitaci[oó]n|$))',
            r'nombre\s*:?\s*([a-záéíóúñ][a-záéíóúñ\s,]+?)(?=\s*(?:dni|documento|historia|$))',
            # Formato simple: Pac: Apellido Nombre o Pcte: Apellido Nombre
            r'pac[\.:]?\s+([a-záéíóúñ][a-záéíóúñ\s,]+?)(?=\s*\n)',
            r'pcte[\.:]?\s+([a-záéíóúñ][a-záéíóúñ\s,]+?)(?=\s*\n)',
            r'nombre\s*completo\s*:?\s*([a-záéíóúñ\s,]+)',
        ],
        'dni': [
            r'dni\s*:?\s*([\d\.]+\d)',
            r'documento\s*:?\s*([\d\.]+\d)',
            r'doc\s*:?\s*([\d\.]+\d)',
        ],
        'historia_clinica': [
            r'(?:nro\.?\s*)?h\.?c\.?\s*:?\s*(\d{4}-?[hH]?[cC]?-?\d+)',
            r'historia\s*cl[ií]nica\s*:?\s*([hH]?[cC]?-?\d{4}-?\d+)',
            r'h\.?c\.?\s*:?\s*([hH]?[cC]?-?\d{4}-\d+)',
            r'hc\s*:?\s*([hH]?[cC]?-?\d{4}-\d+)',
            r'historia\s*:?\s*([hH]?[cC]?-?\d+)',
        ],
        'habitacion': [
            r'habitaci[oó]n\s*:?\s*(\d+[a-z]?(?:-\d+)?)',
            r'hab\.?\s*:?\s*(\d+[a-z]?(?:-\d+)?)',
            r'sala\s*:?\s*(\d+[a-z]?)',
            r'ubicaci[oó]n\s*:.*?habitaci[oó]n\s+(\d+)',
        ],
        'cama': [
            r'cama\s*:?\s*([a-z0-9]+)',
            r'ubicaci[oó]n\s*:.*?cama\s+([a-z0-9]+)',
        ],
        'piso': [
            r'piso\s*:?\s*(\d+)',
            r'ubicaci[oó]n\s*:\s*piso\s+(\d+)',
        ],
        'estudio': [
            # Patrones que capturan el estudio en la misma línea
            r'tipo\s*:?\s*([^\n]+?)(?=\s*(?:datos\s*cl[ií]nicos|indicaci[oó]n|medico|$))',
            r'estudio\s*requerido\s*:?\s*(?:tipo\s*:?\s*)?([^\n]+)',
            r'estudio\s*solicitado\s*:?\s*([^\n]+)',
            r'(?:^|\n)\s*estudio\s*:?\s*([a-záéíóúñ][^\n]+)',
            r'tipo\s*de\s*estudio\s*:?\s*([^\n]+)',
            r'solicito\s*:?\s*([^\n]+)',
            r'solicita\s*:?\s*([^\n]+)',
            # Patrones que capturan cuando el valor está en la siguiente línea (con salto)
            r'estudio\s*solicitado\s*:?\s*\n\s*([^\n]+)',
            r'estudio\s*requerido\s*:?\s*\n\s*(?:tipo\s*:?\s*\n\s*)?([^\n]+)',
            r'tipo\s*de\s*estudio\s*:?\s*\n\s*([^\n]+)',
            r'(?:^|\n)\s*estudio\s*:?\s*\n\s*([^\n]+)',
            # Formato simple: línea que empieza con palabras clave de estudios
            r'(?:^|\n)\s*(ecodoppler[^\n]+)',
            r'(?:^|\n)\s*(ecocardio(?:grama)?[^\n]+)',
            r'(?:^|\n)\s*(eco\s+cardio[^\n]+)',
            r'(?:^|\n)\s*(doppler[^\n]+)',
        ],
        'medico_solicitante': [
            r'm[eé]dico\s*solicitante\s*:?\s*((?:dr|dra)\.?\s*[a-záéíóúñ][a-záéíóúñ\s]+)',
            r'm[eé]dico\s*:?\s*((?:dr|dra)\.?\s*[a-záéíóúñ][a-záéíóúñ\s]+)',
            r'solicitante\s*:?\s*((?:dr|dra)\.?\s*[a-záéíóúñ\s\.]+)',
            r'\n(dra?\.?\s+[a-záéíóúñ][a-záéíóúñ\s]+?)(?=\s*\n)',
        ],
        'prioridad': [
            r'(urgente)',
            r'(urgent)',
            r'prioridad\s*:?\s*(alta|urgente|normal|baja)',
            r'(emergencia)',
            r'(stat)',
        ],
        'obra_social': [
            r'obra\s*social\s*:?\s*([a-záéíóúñ0-9][^\n]+?)(?=\s*(?:nro|afiliado|estudio|$))',
            r'o\.?\s*s\.?\s*:?\s*([a-záéíóúñ0-9][^\n]+)',
            r'cobertura\s*:?\s*([a-záéíóúñ][^\n]+)',
        ],
        'indicacion_clinica': [
            # Mismo patrón que estudio: captura misma línea o siguiente línea
            r'indicaci[oó]n\s*cl[ií]nica\s*:?\s*([^\n]+)',
            r'indicaci[oó]n\s*:?\s*([^\n]+)',
            r'datos\s*cl[ií]nicos\s*:?\s*([^\n]+)',
            # Con salto de línea
            r'indicaci[oó]n\s*cl[ií]nica\s*:?\s*\n\s*([^\n]+)',
            r'indicaci[oó]n\s*:?\s*\n\s*([^\n]+)',
            r'datos\s*cl[ií]nicos\s*:?\s*\n\s*([^\n]+)',
        ],
    }
    
    # Palabras clave que indican urgencia
    PALABRAS_URGENCIA = ['urgente', 'urgent', 'emergencia', 'stat']
    
    def __init__(self):
        """Inicializa el parser."""
        self.errores = []
    
    def parsear_email(self, email_data: Dict) -> Dict[str, Any]:
        """
        Parsea un email completo y extrae toda la información estructurada.
        
        Args:
            email_data: Diccionario con datos del email (de GmailService)
        
        Returns:
            Diccionario con datos extraídos:
            {
                'paciente': {...},
                'estudio': {...},
                'metadata': {...},
                'errores': [...]
            }
        """
        self.errores = []
        
        # Obtener texto limpio del email
        texto = self._obtener_texto_limpio(email_data)
        
        # Extraer información del paciente
        datos_paciente = self._extraer_datos_paciente(texto)
        
        # Extraer información del estudio
        datos_estudio = self._extraer_datos_estudio(texto, email_data)
        
        # Detectar prioridad
        prioridad = self._detectar_prioridad(texto, email_data)
        
        # Metadata del email
        metadata = {
            'email_message_id': email_data.get('message_id', ''),
            'email_asunto': email_data.get('asunto', ''),
            'email_remitente': email_data.get('remitente', ''),
            'email_fecha': email_data.get('fecha'),
            'tiene_adjuntos': len(email_data.get('adjuntos', [])) > 0,
            'cantidad_adjuntos': len(email_data.get('adjuntos', [])),
        }
        
        return {
            'paciente': datos_paciente,
            'estudio': datos_estudio,
            'prioridad': prioridad,
            'metadata': metadata,
            'texto_completo': texto,
            'datos_raw': serializar_datos_raw(email_data),  # Serializar para JSON
            'errores': self.errores,
        }
    
    def parsear_multiples_estudios(self, email_data: Dict) -> List[Dict[str, Any]]:
        """
        Detecta y parsea múltiples estudios en un mismo email.
        
        Args:
            email_data: Diccionario con datos del email
        
        Returns:
            Lista de diccionarios con datos parseados de cada estudio
        """
        texto = self._obtener_texto_limpio(email_data)
        
        # Detectar si hay múltiples estudios
        bloques = self._dividir_en_bloques_estudios(texto)
        
        if len(bloques) <= 1:
            # Solo hay un estudio, parsear normalmente
            return [self.parsear_email(email_data)]
        
        # Hay múltiples estudios
        logger.info(f"Detectados {len(bloques)} estudios en el email")
        resultados = []
        
        # Extraer información común (médico solicitante, etc.)
        medico_comun = self._extraer_medico_comun(texto)
        
        for i, bloque in enumerate(bloques, 1):
            # Crear email_data modificado para cada bloque
            email_data_bloque = email_data.copy()
            email_data_bloque['cuerpo_texto'] = bloque
            email_data_bloque['body'] = bloque
            
            # Parsear el bloque
            resultado = self.parsear_email(email_data_bloque)
            
            # Si no se encontró médico en el bloque, usar el común
            if not resultado['estudio'].get('medico_solicitante') and medico_comun:
                resultado['estudio']['medico_solicitante'] = medico_comun
            
            # Agregar número de estudio a metadata
            resultado['metadata']['numero_estudio_en_email'] = i
            resultado['metadata']['total_estudios_en_email'] = len(bloques)
            
            resultados.append(resultado)
        
        return resultados
    
    def _dividir_en_bloques_estudios(self, texto: str) -> List[str]:
        """
        Divide el texto en bloques cuando detecta múltiples estudios.
        
        Detecta patrones como:
        - 1) Paciente: ...
        - 2) Paciente: ...
        
        Args:
            texto: Texto completo del email
        
        Returns:
            Lista de bloques de texto (uno por estudio)
        """
        # Patrón para detectar inicio de cada estudio numerado
        patron_inicio = r'(?:^|\n)\s*(\d+)\s*\)\s*(?:paciente|estudio)'
        
        coincidencias = list(re.finditer(patron_inicio, texto, re.IGNORECASE | re.MULTILINE))
        
        if len(coincidencias) < 2:
            # No hay múltiples estudios numerados
            return [texto]
        
        bloques = []
        for i, match in enumerate(coincidencias):
            inicio = match.start()
            
            # El final es el inicio del siguiente bloque o el final del texto
            if i + 1 < len(coincidencias):
                fin = coincidencias[i + 1].start()
            else:
                fin = len(texto)
            
            bloque = texto[inicio:fin].strip()
            bloques.append(bloque)
        
        return bloques
    
    def _extraer_medico_comun(self, texto: str) -> Optional[str]:
        """
        Extrae el médico solicitante que aparece al final del email
        (común para todos los estudios).
        
        Args:
            texto: Texto completo del email
        
        Returns:
            Nombre del médico o None
        """
        # Buscar médico en la firma/final del email
        # Típicamente después de "Gracias," o "Saludos,"
        patron_firma = r'(?:gracias|saludos|atentamente|atte)[\s,]*\n\s*(dra?\.?\s+[a-záéíóúñ][a-záéíóúñ\s]+?)(?=\s*\n)'
        
        match = re.search(patron_firma, texto.lower(), re.IGNORECASE)
        if match:
            medico = self._limpiar_valor(match.group(1))
            # Eliminar palabras que no forman parte del nombre
            medico = re.sub(r'\s+(servicio|interno|int|cl[ií]nica)\b.*$', '', medico, flags=re.IGNORECASE)
            return medico
        
        return None
    
    def _obtener_texto_limpio(self, email_data: Dict) -> str:
        """
        Obtiene el texto limpio del email (sin HTML).
        
        Args:
            email_data: Datos del email
        
        Returns:
            Texto limpio
        """
        # Preferir texto plano si está disponible
        texto = email_data.get('cuerpo_texto', '')
        
        # Si no hay texto plano, extraer de HTML
        if not texto:
            html = email_data.get('cuerpo_html', '')
            if html:
                try:
                    soup = BeautifulSoup(html, 'html.parser')
                    texto = soup.get_text(separator='\n', strip=True)
                except Exception as e:
                    logger.error(f"Error al parsear HTML: {e}")
                    self.errores.append(f"Error al extraer texto de HTML: {e}")
        
        return texto
    
    def _extraer_datos_paciente(self, texto: str) -> Dict[str, Optional[str]]:
        """
        Extrae información del paciente del texto.
        
        Args:
            texto: Texto del email
        
        Returns:
            Diccionario con datos del paciente
        """
        datos = {
            'nombre_completo': None,
            'dni': None,
            'historia_clinica': None,
            'habitacion': None,
            'cama': None,
            'piso': None,
            'obra_social': None,
        }
        
        texto_busqueda = texto.lower()
        
        for campo, patrones in self.PATRONES.items():
            if campo in datos:
                for patron in patrones:
                    match = re.search(patron, texto_busqueda, re.IGNORECASE)
                    if match:
                        valor = match.group(1).strip()
                        # Limpieza específica por campo
                        if campo == 'dni':
                            # Eliminar puntos y espacios del DNI
                            valor = re.sub(r'[.\s]', '', valor)
                        elif campo == 'historia_clinica':
                            # Normalizar formato HC
                            valor = valor.upper().replace('HC-', '').replace('HC', '')
                        datos[campo] = self._limpiar_valor(valor)
                        break
        
        return datos
    
    def _extraer_datos_estudio(self, texto: str, email_data: Dict) -> Dict[str, Any]:
        """
        Extrae información del estudio solicitado.
        
        Args:
            texto: Texto del email
            email_data: Datos completos del email
        
        Returns:
            Diccionario con datos del estudio
        """
        datos = {
            'descripcion_estudio': None,
            'medico_solicitante': None,
            'tipo_estudio_sugerido': None,
            'indicacion_clinica': None,
        }
        
        texto_busqueda = texto.lower()
        
        # Extraer con patrones
        for patron in self.PATRONES['estudio']:
            match = re.search(patron, texto_busqueda, re.IGNORECASE)
            if match:
                datos['descripcion_estudio'] = match.group(1).strip()
                break
        
        for patron in self.PATRONES['medico_solicitante']:
            match = re.search(patron, texto_busqueda, re.IGNORECASE)
            if match:
                medico = self._limpiar_valor(match.group(1))
                # Eliminar palabras que no forman parte del nombre del médico
                medico = re.sub(r'\s+(servicio|interno|int|cl[ií]nica)\b.*$', '', medico, flags=re.IGNORECASE)
                datos['medico_solicitante'] = medico
                break
        
        # Extraer indicación clínica
        for patron in self.PATRONES.get('indicacion_clinica', []):
            match = re.search(patron, texto_busqueda, re.IGNORECASE)
            if match:
                datos['indicacion_clinica'] = self._limpiar_valor(match.group(1))
                break
        
        # Si no se encontró descripción, usar el asunto del email
        if not datos['descripcion_estudio']:
            asunto = email_data.get('asunto', '')
            if asunto:
                datos['descripcion_estudio'] = asunto
                self.errores.append("Descripción tomada del asunto del email")
        
        # Intentar clasificar el tipo de estudio
        datos['tipo_estudio_sugerido'] = self._clasificar_tipo_estudio(
            datos['descripcion_estudio'] or ''
        )
        
        return datos
    
    def _clasificar_tipo_estudio(self, descripcion: str) -> Optional[str]:
        """
        Intenta clasificar el tipo de estudio basándose en palabras clave.
        
        Devuelve el nombre específico del tipo de estudio para coincidir
        con los nombres en la base de datos TipoEstudio.
        
        La estrategia es evaluar desde los más específicos a los más generales.
        
        Args:
            descripcion: Descripción del estudio
        
        Returns:
            Nombre específico del tipo de estudio o None
        """
        descripcion_lower = descripcion.lower()
        
        # NIVEL 1: Patrones muy específicos anatómicos/técnicos
        # Orden: de más específico a más general
        
        # Carotídeo y/o Vertebral
        if any(k in descripcion_lower for k in ['carotideo', 'carotídeo', 'carotida', 'carótida', 'vertebral', 'tsa', 'troncos supraaorticos']):
            return "Ecodoppler Carotídeo y Vertebral"
        
        # Renal
        if any(k in descripcion_lower for k in ['renal', 'riñon', 'riñón']):
            return "Ecodoppler Renal"
        
        # Aorta
        if any(k in descripcion_lower for k in ['aorta', 'aórtica']):
            return "Ecodoppler de Aorta Abdominal"
        
        # Testicular
        if any(k in descripcion_lower for k in ['testicular', 'testiculo', 'testículo', 'escrotal']):
            return "Ecodoppler Testicular"
        
        # Peneano
        if any(k in descripcion_lower for k in ['peneano', 'pene', 'peniano']):
            return "Ecodoppler Peneano"
        
        # NIVEL 2: Ecodoppler de extremidades con especificidad arterial/venoso
        
        # MMII - Arterial
        if any(k in descripcion_lower for k in ['mmii', 'miembro inferior', 'miembros inferiores', 'pierna']):
            if any(k in descripcion_lower for k in ['arterial', 'arterias']):
                return "Ecodoppler Arterial de MMII"
            elif any(k in descripcion_lower for k in ['venoso', 'venas', 'venosa']):
                return "Ecodoppler Venoso de MMII"
            else:
                # Por defecto, si solo menciona MMII sin especificar, asumir el tipo genérico
                return "Ecodoppler de Miembros Inferiores"
        
        # MMSS
        if any(k in descripcion_lower for k in ['mmss', 'miembro superior', 'miembros superiores', 'brazo']):
            return "Ecodoppler de Miembros Superiores"
        
        # NIVEL 3: Ecocardiogramas
        
        # Ecocardiograma con variantes TT/TEE/ETE
        if any(k in descripcion_lower for k in [
            'ecocardio', 'eco cardio', 'ecocardiograma', 'eco-cardio',
            'transtoracico', 'transtorácico', 'tt ', ' tt',
            'transesofagico', 'transesofágico', 'tee', 'ete',
            'doppler cardiaco', 'doppler color'
        ]):
            return "Ecocardiograma Doppler Color"
        
        # NIVEL 4: Genéricos
        
        # Ecodoppler genérico (si no coincidió con nada más específico)
        if any(k in descripcion_lower for k in [
            'doppler', 'eco doppler', 'ecodoppler', 'ecd ',
            'arterial', 'venoso', 'vascular'
        ]):
            return "ecodoppler"  # Genérico para que el procesador busque por descripción
        
        # Ecografía genérica
        if any(k in descripcion_lower for k in ['eco ', 'ecograf', 'ultrason', 'us ']):
            return "ecografía"
        
        return None
    
    def _detectar_prioridad(self, texto: str, email_data: Dict) -> str:
        """
        Detecta la prioridad del estudio.
        
        Args:
            texto: Texto del email
            email_data: Datos del email
        
        Returns:
            Prioridad: 'URGENTE', 'ALTA', 'NORMAL', 'BAJA'
        """
        texto_completo = (texto + ' ' + email_data.get('asunto', '')).lower()
        
        # Buscar palabras de urgencia
        if any(palabra in texto_completo for palabra in self.PALABRAS_URGENCIA):
            return 'URGENTE'
        
        # Buscar patrones de prioridad explícitos
        for patron in self.PATRONES['prioridad']:
            match = re.search(patron, texto_completo, re.IGNORECASE)
            if match:
                prioridad_texto = match.group(1).lower()
                if prioridad_texto in ['urgente', 'urgent']:
                    return 'URGENTE'
                elif prioridad_texto == 'alta':
                    return 'ALTA'
        
        return 'NORMAL'
    
    def _limpiar_valor(self, valor: str) -> str:
        """
        Limpia un valor extraído (elimina espacios extra, etc.).
        
        Args:
            valor: Valor a limpiar
        
        Returns:
            Valor limpio
        """
        # Eliminar espacios múltiples
        valor = re.sub(r'\s+', ' ', valor)
        
        # Capitalizar nombres propios
        if valor and not valor.isupper():
            valor = valor.title()
        
        return valor.strip()
    
    def validar_datos_extraidos(self, datos: Dict) -> List[str]:
        """
        Valida que los datos extraídos sean suficientes para crear un pedido.
        
        Args:
            datos: Datos parseados
        
        Returns:
            Lista de errores/advertencias de validación
        """
        advertencias = []
        
        paciente = datos.get('paciente', {})
        estudio = datos.get('estudio', {})
        
        # Validaciones de paciente
        if not paciente.get('nombre_completo'):
            advertencias.append("No se pudo extraer el nombre del paciente")
        
        if not paciente.get('habitacion') and not paciente.get('historia_clinica'):
            advertencias.append("No se encontró habitación ni historia clínica")
        
        # Validaciones de estudio
        if not estudio.get('descripcion_estudio'):
            advertencias.append("No se pudo extraer la descripción del estudio")
        
        if not estudio.get('medico_solicitante'):
            advertencias.append("No se identificó el médico solicitante")
        
        return advertencias


# Funciones helper

def parsear_email_completo(email_data: Dict) -> Dict[str, Any]:
    """
    Helper function para parsear un email completo.
    
    Args:
        email_data: Datos del email desde GmailService
    
    Returns:
        Datos parseados y validados
    """
    parser = EmailParser()
    datos = parser.parsear_email(email_data)
    
    # Validar datos extraídos
    advertencias = parser.validar_datos_extraidos(datos)
    datos['advertencias_validacion'] = advertencias
    
    return datos


def extraer_informacion_basica(texto: str) -> Dict[str, Optional[str]]:
    """
    Extrae información básica de un texto libre (útil para testing).
    
    Args:
        texto: Texto a procesar
    
    Returns:
        Diccionario con datos extraídos
    """
    parser = EmailParser()
    email_simulado = {
        'cuerpo_texto': texto,
        'asunto': '',
        'adjuntos': [],
    }
    
    return parser.parsear_email(email_simulado)
