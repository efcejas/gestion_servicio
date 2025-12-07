"""
Servicios de IA para dictado y mejora de informes médicos
"""
from openai import OpenAI
from django.conf import settings
from decouple import config
import logging

logger = logging.getLogger(__name__)


class AIService:
    """Servicio para integración con OpenAI y Groq"""
    
    def __init__(self):
        # Configurar AMBOS proveedores si están disponibles
        groq_key = config('GROQ_API_KEY', default=None)
        openai_key = config('OPENAI_API_KEY', default=None)
        
        # Cliente Groq para mejora de texto (gratis, 14,400 req/día)
        if groq_key:
            self.groq_client = OpenAI(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.groq_enabled = True
            self.model = 'llama-3.3-70b-versatile'
            logger.info("✅ Groq API configurada para mejora de texto (Gratis)")
        else:
            self.groq_client = None
            self.groq_enabled = False
        
        # Cliente OpenAI para Whisper (transcripción de audio)
        if openai_key:
            self.openai_client = OpenAI(api_key=openai_key)
            self.openai_enabled = True
            logger.info("✅ OpenAI API configurada para Whisper (transcripción)")
        else:
            self.openai_client = None
            self.openai_enabled = False
        
        # Prioridad: Groq para texto, OpenAI para audio
        if self.groq_enabled:
            self.client = self.groq_client
            self.enabled = True
            self.provider = 'groq'
        elif self.openai_enabled:
            self.client = self.openai_client
            self.enabled = True
            self.provider = 'openai'
            self.model = 'gpt-4o-mini'
        else:
            self.client = None
            self.enabled = False
            self.provider = None
            self.model = None
            logger.warning("⚠️ Ninguna API de IA configurada. Servicios deshabilitados.")
    
    def get_api_info(self):
        """Retorna información sobre el proveedor de IA y límites"""
        if not self.enabled:
            return {
                'provider': None,
                'model': None,
                'enabled': False,
                'limits': {}
            }
        
        info = {
            'provider': self.provider,
            'model': self.model,
            'enabled': True
        }
        
        # Límites según proveedor
        if self.provider == 'groq':
            info['limits'] = {
                'requests_per_day': 14400,
                'requests_per_minute': 30,
                'tokens_per_minute': 20000,
                'cost': 'GRATIS',
                'description': 'Plan gratuito de Groq con límite diario generoso'
            }
        elif self.provider == 'openai':
            info['limits'] = {
                'cost': 'PAGO',
                'description': 'Plan de pago según uso de OpenAI'
            }
        
        return info
    
    def transcribe_audio(self, audio_file):
        """
        Transcribe audio usando Whisper de OpenAI
        
        Args:
            audio_file: Archivo de audio (ContentFile o FileField)
        
        Returns:
            dict: {'text': str, 'confidence': float}
        """
        if not self.openai_enabled:
            return {
                'text': '',
                'confidence': 0.0,
                'error': '⚠️ Necesitas configurar OPENAI_API_KEY en el .env para usar Whisper. Crea una cuenta en https://platform.openai.com (incluye $5 gratis)'
            }
        
        try:
            # Leer el contenido del archivo
            if hasattr(audio_file, 'read'):
                audio_file.seek(0)  # Asegurar que estamos al inicio
                audio_content = audio_file.read()
            else:
                with audio_file.open('rb') as audio:
                    audio_content = audio.read()
            
            # Crear una tupla con el formato esperado
            file_tuple = ("audio.webm", audio_content, "audio/webm")
            
            # Prompt para guiar a Whisper en contexto médico
            # Optimizado para informes radiológicos con separación automática de conceptos
            prompt_whisper = (
                "Informe radiológico estructurado. Terminología médica especializada. "
                "Pausa breve = coma. Pausa media = punto. Pausa larga = punto y salto de línea. "
                "Cada hallazgo o estructura anatómica en línea separada. "
                "Detecta pausas del hablante para separar conceptos automáticamente."
            )
            
            # Transcribir con OpenAI Whisper
            transcript = self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=file_tuple,
                language="es",  # Español
                prompt=prompt_whisper,  # Contexto para mejorar precisión
                temperature=0.8,  # 0-1: MÁS sensible a pausas = más puntuación automática (aumentado de 0.5 → 0.8)
                response_format="verbose_json"
            )
            
            logger.info(f"✅ Whisper transcripción exitosa: {len(transcript.text)} caracteres")
            
            return {
                'text': transcript.text,
                'confidence': 0.95,
                'duration': getattr(transcript, 'duration', None),
                'provider': 'openai'
            }
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Error en transcripción Whisper: {error_msg}")
            logger.exception("Traceback completo:")
            
            # Mensaje específico según el error
            if 'model_not_found' in error_msg or '404' in error_msg:
                error_msg = "⚠️ Tu API key de OpenAI no tiene acceso a Whisper o está inválida. Verifica en https://platform.openai.com"
            elif 'insufficient_quota' in error_msg:
                error_msg = "⚠️ Se agotaron los créditos gratuitos de OpenAI. Agrega créditos en https://platform.openai.com/account/billing"
            
            return {
                'text': '',
                'confidence': 0.0,
                'error': error_msg
            }
    
    def improve_medical_text(self, texto_original, tipo_estudio, contexto=None, usuario=None):
        """
        Mejora el texto dictado usando GPT-4 para darle formato médico profesional
        
        Args:
            texto_original: Texto transcrito del audio
            tipo_estudio: Tipo de estudio (RES, TOM, etc.)
            contexto: Contexto adicional (dict con datos del paciente, plantilla, etc.)
        
        Returns:
            dict: {'texto_mejorado': str, 'confianza': float, 'sugerencias': list}
        """
        if not self.enabled:
            return {
                'texto_mejorado': texto_original,
                'confianza': 0.0,
                'sugerencias': [],
                'error': 'API de OpenAI no configurada'
            }
        
        # Mapeo de tipos de estudio
        tipos_estudios = {
            'RES': 'Resonancia Magnética',
            'TOM': 'Tomografía',
            'RAD': 'Radiografía',
            'ECO': 'Ecografía',
            'MAM': 'Mamografía',
            'DEN': 'Densitometría',
            'OTR': 'Otro'
        }
        
        # Templates de técnica según tipo de estudio
        templates_tecnica = {
            'RES': 'Se exploró la región solicitada con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos del espacio.',
            'TOM': 'Se realizó estudio tomográfico de la región solicitada con cortes axiales de espesor fino, con y sin contraste endovenoso.',
            'ECO': 'Se realizó estudio ecográfico de la región solicitada utilizando transductor lineal de alta frecuencia.',
            'RAD': 'Se obtuvieron radiografías en proyecciones estándar de la región anatómica solicitada.',
            'MAM': 'Se realizó estudio mamográfico bilateral en proyecciones cráneo-caudal y oblicua medio-lateral.',
            'DEN': 'Se realizó densitometría ósea mediante técnica DXA en columna lumbar y cadera.',
            'OTR': 'Se realizó estudio de la región solicitada según protocolo estándar.'
        }
        
        tipo_nombre = tipos_estudios.get(tipo_estudio, 'estudio médico')
        template_tecnica = templates_tecnica.get(tipo_estudio, templates_tecnica['OTR'])
        
        # Detectar si hay plantilla activa
        plantilla = contexto.get('plantilla') if contexto else None
        
        # MODO PLANTILLA: Completar campos específicos respetando estructura
        if plantilla:
            logger.info(f"🎯 Modo PLANTILLA activado: {plantilla.get('nombre', 'sin nombre')}")
            
            campos = plantilla.get('campos_actuales', {})
            prompt = f"""Eres un médico radiólogo experto. Un colega está completando un informe usando una plantilla predefinida y ha dictado información adicional.

PLANTILLA ACTIVA: {plantilla.get('nombre', 'Plantilla estándar')}

CAMPOS ACTUALES DE LA PLANTILLA:
- Indicación Clínica: {campos.get('indicacion_clinica', '(vacío)')}
- Técnica: {campos.get('tecnica', '(vacío)')}
- Hallazgos: {campos.get('hallazgos', '(vacío)')}
- Conclusión: {campos.get('conclusion', '(vacío)')}

TEXTO DICTADO:
{texto_original}

TU TAREA:
1. Analiza el texto dictado e identifica qué información corresponde a cada sección
2. RESPETA la estructura de la plantilla - NO modifiques campos que ya tienen contenido
3. COMPLETA solo los campos que están vacíos o agrega información relevante
4. Mantén el formato y estilo de la plantilla
5. Si un campo de la plantilla tiene contenido técnico (como Técnica), respétalo exactamente
6. NO inventes información - solo estructura lo dictado

FORMATO DE RESPUESTA (USA EXACTAMENTE ESTE FORMATO):

INDICACIÓN CLÍNICA:
[Completar con información dictada sobre síntomas, región, patología sospechada]

TÉCNICA:
[SI YA EXISTE EN PLANTILLA: mantener exactamente igual. SI ESTÁ VACÍO: usar descripción técnica apropiada]

HALLAZGOS:
[Completar con observaciones dictadas, usando terminología médica precisa]

CONCLUSIÓN:
[Resumir hallazgos principales del texto dictado]

IMPORTANTE: 
- USA MAYÚSCULAS para nombres de secciones
- NO modifiques contenido pre-existente de la plantilla
- Si la Técnica ya está completa, devuélvela SIN CAMBIOS
- Cada sección debe terminar con línea en blanco"""
        
        # MODO LIBRE: Generar estructura completa
        else:
            logger.info("📝 Modo LIBRE - generando estructura completa")
            
            # Verificar si el usuario quiere solo corrección o estructura completa
            modo = contexto.get('modo', 'LIBRE') if contexto else 'LIBRE'
            
            # Obtener ejemplos de aprendizaje del usuario
            from .models import CorreccionAprendizaje
            ejemplos_aprendizaje = CorreccionAprendizaje.obtener_ejemplos_aprendizaje(
                usuario=usuario,
                limite=10
            )
            
            if ejemplos_aprendizaje:
                cantidad_ejemplos = len(ejemplos_aprendizaje.split('\n'))
                logger.info(f"🧠 Sistema de aprendizaje: {cantidad_ejemplos} ejemplos activos para {usuario}")
            
            if modo == 'FIEL':
                # MODO FIEL: Solo corregir ortografía SIN inventar estructura ni agregar texto
                prompt_base = f"""Eres un corrector ortográfico ESTRICTO. Tu ÚNICA tarea es corregir errores de ortografía SIN MODIFICAR NADA MÁS.

TEXTO ORIGINAL:
{texto_original}

INSTRUCCIONES ESTRICTAS:
1. Corrige ÚNICAMENTE ortografía: acentos, mayúsculas iniciales, términos médicos mal escritos
2. NO agregues comas donde no hay
3. NO agregues puntos donde no hay  
4. NO agregues saltos de línea donde no hay
5. NO quites comas que ya existen
6. NO quites puntos que ya existen
7. NO quites saltos de línea que ya existen
8. NO cambies el orden de las palabras
9. NO reorganices las frases
10. Capitaliza SOLO la primera letra después de punto o salto de línea

PROHIBIDO ABSOLUTAMENTE:
❌ Agregar o quitar puntuación
❌ Agregar o quitar saltos de línea
❌ Cambiar la estructura del texto
❌ Agregar palabras o frases
❌ Quitar palabras o frases

EJEMPLO DE LO QUE DEBES HACER:
ORIGINAL: "la rotula presenta implantacion alta"
CORRECTO: "La rótula presenta implantación alta"
INCORRECTO: "La rótula presenta implantación alta." ← NO agregues punto si no había

RESPONDE ÚNICAMENTE CON EL TEXTO CORREGIDO, SIN EXPLICACIONES:"""
                
                # Agregar ejemplos de aprendizaje si existen
                if ejemplos_aprendizaje:
                    prompt = f"""{prompt_base}

CORRECCIONES PREVIAS DEL USUARIO (aprende estos patrones):
{ejemplos_aprendizaje}
"""
                else:
                    prompt = prompt_base

            else:
                # MODO ESTRUCTURADO: Crear informe completo con secciones
                prompt = f"""Eres un médico radiólogo experto. Analiza el siguiente texto dictado de un informe de {tipo_nombre} y estructura la información en 4 secciones.

TEXTO DICTADO:
{texto_original}

INSTRUCCIONES ESPECÍFICAS:

1. INDICACIÓN CLÍNICA:
   - Extrae del texto la razón del estudio (síntomas, región anatómica, patología sospechada)
   - Ejemplos: "Gonalgia derecha", "Trauma de rodilla", "Control post-quirúrgico"
   - Si no está explícita, infiere de los hallazgos la indicación probable
   - Usa terminología médica concisa

2. TÉCNICA:
   - Usa EXACTAMENTE este texto (adaptado al estudio):
   "{template_tecnica}"
   - NO inventes detalles técnicos
   - Mantén la descripción estándar

3. HALLAZGOS:
   - Describe detalladamente lo observado
   - Usa terminología médica precisa
   - Corrige errores de transcripción
   - Mantén la información original sin inventar

4. CONCLUSIÓN:
   - Resume los hallazgos principales
   - Usa lenguaje clínico profesional
   - Sé conciso y claro

FORMATO DE RESPUESTA (USA EXACTAMENTE ESTE FORMATO):

INDICACIÓN CLÍNICA:
[Indicación extraída o inferida del texto]

TÉCNICA:
{template_tecnica}

HALLAZGOS:
[Descripción detallada]

CONCLUSIÓN:
[Resumen clínico]

IMPORTANTE: 
- NO incluyas títulos generales como "Informe Radiológico"
- USA MAYÚSCULAS para los nombres de secciones
- Cada sección debe terminar con una línea en blanco"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,  # Usar el modelo configurado (Groq o OpenAI)
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un médico radiólogo experto especializado en redacción de informes médicos profesionales."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # MUY baja para máxima fidelidad en modo FIEL (reducido de 0.3)
                max_tokens=1500
            )
            
            texto_mejorado = response.choices[0].message.content.strip()
            
            modo = "PLANTILLA" if plantilla else "LIBRE"
            logger.info(f"✅ Texto mejorado con {self.provider.upper()} en modo {modo} ({self.model})")
            
            # Calcular "confianza" basada en la longitud y coherencia
            confianza = min(0.95, len(texto_mejorado) / max(len(texto_original), 1))
            
            return {
                'texto_mejorado': texto_mejorado,
                'confianza': confianza,
                'sugerencias': self._extract_suggestions(texto_original, texto_mejorado),
                'tokens_used': response.usage.total_tokens,
                'modo': modo
            }
        
        except Exception as e:
            logger.error(f"Error en mejora de texto: {str(e)}")
            return {
                'texto_mejorado': texto_original,
                'confianza': 0.0,
                'sugerencias': [],
                'error': str(e)
            }
    
    def _extract_suggestions(self, original, mejorado):
        """Extrae sugerencias comparando texto original y mejorado"""
        sugerencias = []
        
        # Análisis simple de diferencias
        if len(mejorado) > len(original) * 1.2:
            sugerencias.append("Se amplió la descripción para mayor claridad")
        
        if "TÉCNICA:" in mejorado.upper() and "TÉCNICA:" not in original.upper():
            sugerencias.append("Se añadió sección de Técnica")
        
        if "CONCLUSIÓN:" in mejorado.upper() and "CONCLUSIÓN:" not in original.upper():
            sugerencias.append("Se estructuró con Conclusión clara")
        
        return sugerencias


# Instancia global del servicio
ai_service = AIService()
