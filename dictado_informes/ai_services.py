"""
Servicios de IA para dictado y mejora de informes médicos
"""
from openai import OpenAI
from django.conf import settings
from django.core.cache import cache
from decouple import config
import logging
import hashlib

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
            
            logger.info(f"📁 Audio content size: {len(audio_content)} bytes")
            
            # Validar que tenemos contenido de audio
            if len(audio_content) < 100:  # Un archivo de audio válido debe tener al menos 100 bytes
                logger.error("❌ Audio content too small, probably invalid")
                return {
                    'text': '',
                    'confidence': 0.0,
                    'error': 'Archivo de audio demasiado pequeño o inválido'
                }
            
            # 🚀 CACHÉ: Verificar si ya transcribimos este audio
            audio_hash = hashlib.md5(audio_content).hexdigest()
            cache_key = f'whisper_transcription_{audio_hash}'
            cached_result = cache.get(cache_key)
            
            if cached_result:
                logger.info(f"✅ Transcripción recuperada del caché (hash: {audio_hash[:8]}...)")
                cached_result['from_cache'] = True
                return cached_result
            
            # Detectar el tipo de archivo basado en los primeros bytes (magic numbers)
            # WebM: starts with 0x1A, 0x45, 0xDF, 0xA3
            # WAV: starts with "RIFF"
            # OGG: starts with "OggS"
            magic_bytes = audio_content[:4]
            
            if magic_bytes.startswith(b'\x1a\x45\xdf\xa3'):
                file_extension = "webm"
                mime_type = "audio/webm"
            elif magic_bytes.startswith(b'RIFF'):
                file_extension = "wav"
                mime_type = "audio/wav"
            elif magic_bytes.startswith(b'OggS'):
                file_extension = "ogg"
                mime_type = "audio/ogg"
            else:
                # Default to webm if can't detect
                file_extension = "webm"
                mime_type = "audio/webm"
                logger.warning(f"⚠️ Unknown audio format, magic bytes: {magic_bytes.hex()}")
            
            logger.info(f"🎵 Detected audio format: {file_extension}")
            
            # Crear una tupla con el formato esperado por OpenAI
            file_tuple = (f"audio.{file_extension}", audio_content, mime_type)
            
            # Prompt optimizado para Whisper (más corto = menos latencia)
            prompt_whisper = (
                "Informe radiológico. Terminología médica. "
                "Pausas: breve=coma, media=punto, larga=salto. "
                "Separar estructuras anatómicas."
            )
            
            # Transcribir con OpenAI Whisper
            transcript = self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=file_tuple,
                language="es",  # Español
                prompt=prompt_whisper,  # Contexto para mejorar precisión
                temperature=0.6,  # Optimizado: balance entre precisión y velocidad (reducido de 0.8)
                response_format="verbose_json"
            )
            
            logger.info(f"✅ Whisper transcripción exitosa: {len(transcript.text)} caracteres")
            
            result = {
                'text': transcript.text,
                'confidence': 0.95,
                'duration': getattr(transcript, 'duration', None),
                'provider': 'openai',
                'from_cache': False
            }
            
            # 🚀 GUARDAR EN CACHÉ (1 hora de expiración)
            cache.set(cache_key, result, timeout=3600)
            logger.info(f"💾 Transcripción guardada en caché (hash: {audio_hash[:8]}...)")
            
            return result
            
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
                # MODO FIEL: Solo corregir ortografía y puntuación básica
                prompt_base = f"""Corrector ortográfico médico. Corrige ortografía y normaliza puntuación final.

TEXTO:
{texto_original}

REGLAS:
1. Corrige ortografía: acentos, mayúsculas, términos médicos
2. MANTÉN toda la puntuación existente (comas, puntos intermedios)
3. Si una oración completa NO termina en punto, agrégalo
4. Si termina en salto de línea, asegura que tenga punto antes
5. RESPETA saltos de línea existentes
6. NO agregues comas nuevas
7. NO reorganices frases
8. Capitaliza después de punto o inicio de línea

PUNTUACIÓN FINAL:
✅ "meniscos normales" → "Meniscos normales."
✅ "meniscos normales." → "Meniscos normales." (ya tenía punto)
✅ "rodilla derecha\nmeniscos normales" → "Rodilla derecha.\nMeniscos normales."
❌ "meniscos normales sin" → "Meniscos normales sin" (oración incompleta, no agregar punto)

Responde solo con el texto corregido:"""
                
                # Agregar ejemplos de aprendizaje si existen
                if ejemplos_aprendizaje:
                    prompt = f"""{prompt_base}

CORRECCIONES PREVIAS DEL USUARIO (aprende estos patrones):
{ejemplos_aprendizaje}
"""
                else:
                    prompt = prompt_base

            else:
                # MODO ESTRUCTURADO: Crear informe con plantilla específica según tipo
                tipo_plantilla = contexto.get('tipo_plantilla', 'RODILLA') if contexto else 'RODILLA'
                logger.info(f"📋 Generando plantilla tipo: {tipo_plantilla}")
                
                # Definir plantillas según tipo
                plantillas = {
                    'RODILLA': {
                        'titulo': 'RM DE RODILLA [<DERECHA/IZQUIERDA>]',
                        'seccion_tecnica': 'Se exploró la rodilla [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                        'comentarios': [
                            'Meniscos de altura y señal normales.',
                            'Ligamentos cruzados de trayecto y morfología conservados.',
                            'Resto de tendones y ligamentos de la rodilla sin alteraciones.',
                            'Rótula centrada, sin lesión visible.',
                            'No se observa aumento del líquido articular.',
                            'No se visualizan lesiones óseas.'
                        ]
                    },
                    'HOMBRO': {
                        'titulo': 'RM DE HOMBRO [<DERECHO/IZQUIERDO>]',
                        'seccion_tecnica': 'Se exploró el hombro [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                        'comentarios': [
                            'Manguito rotador de grosor y señal conservados.',
                            'Tendón del bíceps de trayecto y grosor normal.',
                            'Labrum glenoideo de morfología conservada.',
                            'Articulación acromioclavicular sin alteraciones.',
                            'No se observa aumento del líquido articular.',
                            'Estructuras óseas sin lesiones evidentes.'
                        ]
                    },
                    'CODO': {
                        'titulo': 'RM DE CODO [<DERECHO/IZQUIERDO>]',
                        'seccion_tecnica': 'Se exploró el codo [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                        'comentarios': [
                            'Tendón del bíceps distal de grosor y señal normales.',
                            'Tendón del tríceps de morfología conservada.',
                            'Ligamentos colaterales sin alteraciones.',
                            'Epicóndilos sin signos de epicondilitis.',
                            'Articulación radiocubital proximal conservada.',
                            'No se observa aumento del líquido articular.'
                        ]
                    },
                    'TOBILLO': {
                        'titulo': 'RM DE TOBILLO [<DERECHO/IZQUIERDO>]',
                        'seccion_tecnica': 'Se exploró el tobillo [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                        'comentarios': [
                            'Tendón de Aquiles de grosor y señal normales.',
                            'Tendones peroneos de trayecto conservado.',
                            'Ligamentos laterales sin alteraciones.',
                            'Ligamento deltoideo íntegro.',
                            'Tendón tibial posterior conservado.',
                            'No se observa aumento del líquido articular.'
                        ]
                    },
                    'MANO': {
                        'titulo': 'RM DE MANO [<DERECHA/IZQUIERDA>]',
                        'seccion_tecnica': 'Se exploró la mano [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                        'comentarios': [
                            'Tendones flexores y extensores de grosor y señal conservados.',
                            'Ligamentos intercarpianos sin alteraciones.',
                            'Túnel carpiano de calibre normal.',
                            'Nervio mediano sin compresión.',
                            'Articulaciones metacarpofalángicas conservadas.',
                            'No se observa aumento del líquido articular.'
                        ]
                    },
                    'MUÑECA': {
                        'titulo': 'RM DE MUÑECA [<DERECHA/IZQUIERDA>]',
                        'seccion_tecnica': 'Se exploró la muñeca [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                        'comentarios': [
                            'Fibrocartílago triangular íntegro.',
                            'Tendones flexores y extensores conservados.',
                            'Ligamentos escafo-lunares sin alteraciones.',
                            'Túnel carpiano de calibre normal.',
                            'Articulación radio-carpiana conservada.',
                            'No se observa aumento del líquido articular.'
                        ]
                    },
                    'PIE': {
                        'titulo': 'RM DE PIE [<DERECHO/IZQUIERDO>]',
                        'seccion_tecnica': 'Se exploró el pie [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                        'comentarios': [
                            'Estructuras óseas del pie sin alteraciones.',
                            'Articulaciones intertarsianas conservadas.',
                            'Tendones y ligamentos sin signos de lesión.',
                            'No se observa aumento del líquido articular.',
                            'No se visualizan lesiones óseas.'
                        ]
                    },
                    'CADERA': {
                        'titulo': 'RM DE CADERA [<DERECHA/IZQUIERDA>]',
                        'seccion_tecnica': 'Se exploró la cadera [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                        'comentarios': [
                            'Cabeza femoral de morfología y señal normales.',
                            'Acetábulo sin alteraciones.',
                            'Labrum acetabular íntegro.',
                            'Músculos periarticulares sin signos de lesión.',
                            'No se observa aumento del líquido articular.',
                            'Estructuras óseas sin lesiones evidentes.'
                        ]
                    },
                    'TC_MSK': {
                        'titulo': 'TC DE [<REGIÓN ANATÓMICA>]',
                        'seccion_tecnica': 'Se realizó estudio tomográfico de la región solicitada con reconstrucciones multiplanares, sin contraste endovenoso.',
                        'comentarios': [
                            'Estructuras óseas de la región sin alteraciones.',
                            'Articulaciones conservadas.',
                            'Tejidos blandos sin signos de lesión.',
                            'No se observan colecciones ni masas.',
                            'No se visualizan lesiones evidentes.'
                        ]
                    }
                }
                
                plantilla_actual = plantillas.get(tipo_plantilla, plantillas['RODILLA'])
                comentarios_str = '\n'.join(plantilla_actual['comentarios'])
                
                prompt = f"""Eres un médico radiólogo experto. Analiza el siguiente texto dictado y estructura la información usando ÚNICAMENTE la plantilla proporcionada.

⚠️ ADVERTENCIA CRÍTICA: NO mezcles plantillas de diferentes modalidades (RM vs TC). Usa SOLO la plantilla que te doy.

TEXTO DICTADO:
{texto_original}

════════════════════════════════════════════════
PLANTILLA A USAR (NO CAMBIES NADA DE ESTO):
════════════════════════════════════════════════

{plantilla_actual['titulo']}

INFORMACIÓN CLÍNICA
[<extraer indicación del dictado o poner "Sin datos clínicos disponibles.">]

TÉCNICA
{plantilla_actual['seccion_tecnica']}

COMENTARIO
{comentarios_str}

CONCLUSIÓN
[<resumir hallazgos principales del dictado>]

════════════════════════════════════════════════

INSTRUCCIONES OBLIGATORIAS:
1. Los corchetes [<...>] son MARCADORES que debes REEMPLAZAR y ELIMINAR completamente
2. Ejemplo: "[<DERECHO/IZQUIERDO>]" → "DERECHO" (sin corchetes)
3. Ejemplo: "[<lado>]" → "derecho" (sin corchetes)
4. USA LA TÉCNICA EXACTA que te di arriba (NO inventes otra)
5. Mantén TODAS las líneas del COMENTARIO (no agregues ni quites líneas)
6. Si el dictado menciona patología, REEMPLAZA solo esa línea específica
7. Si el dictado NO menciona una estructura, DEJA la línea normal intacta
8. NO uses términos de otras modalidades (ej: si es RM, no menciones "contraste endovenoso")

EJEMPLOS DE REEMPLAZO CORRECTO:
✅ "RM DE RODILLA [<DERECHA/IZQUIERDA>]" → "RM DE RODILLA DERECHA"
✅ "Se exploró la rodilla [<lado>]" → "Se exploró la rodilla derecha"
❌ "RM DE RODILLA [DERECHA]" (mal, dejó corchetes)
❌ "Se exploró la rodilla [derecha]" (mal, dejó corchetes)

FORMATO DE SALIDA:
Copia la estructura de arriba, completa los campos [<...>] y ELIMINA los corchetes."""

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
                temperature=0.2,  # Optimizado para modo FIEL: permite puntuación inteligente manteniendo fidelidad
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
