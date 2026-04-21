"""
Servicios de IA para dictado y mejora de informes médicos
"""
from openai import OpenAI
from django.conf import settings
from django.core.cache import cache
from decouple import config
import logging
import hashlib
import re
import difflib

logger = logging.getLogger(__name__)


class AIService:
    """Servicio para integración con OpenAI y Groq"""
    
    def __init__(self):
        # Configurar AMBOS proveedores si están disponibles
        groq_key = config('GROQ_API_KEY', default=None)
        openai_key = config('OPENAI_API_KEY', default=None)
        
        # Cliente OpenAI para STT (Whisper)
        if openai_key:
            self.stt_client = OpenAI(api_key=openai_key)
            self.stt_enabled = True
            logger.info("✅ OpenAI Whisper configurado para transcripción")
        else:
            self.stt_client = None
            self.stt_enabled = False
        
        # 🎯 PRIORIDAD: OpenAI GPT-4o-mini para LLM (mejor calidad médica)
        if openai_key:
            self.llm_client = OpenAI(api_key=openai_key)
            self.llm_enabled = True
            self.llm_model = 'gpt-4o-mini'
            self.llm_provider = 'openai'
            logger.info("✅ OpenAI GPT-4o-mini configurado para mejora de texto (PRIORITARIO)")
            
            # Groq como fallback gratuito si OpenAI falla
            if groq_key:
                self.groq_fallback = OpenAI(
                    api_key=groq_key,
                    base_url="https://api.groq.com/openai/v1"
                )
                logger.info("✅ Groq disponible como fallback gratuito")
            else:
                self.groq_fallback = None
                
        elif groq_key:
            # Solo Groq disponible (fallback total)
            self.llm_client = OpenAI(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.llm_enabled = True
            self.llm_model = 'llama-3.3-70b-versatile'
            self.llm_provider = 'groq'
            self.groq_fallback = None
            logger.info("✅ Groq LLM configurado (solo Groq disponible)")
        else:
            self.llm_client = None
            self.llm_enabled = False
            self.llm_model = None
            self.llm_provider = None
            self.groq_fallback = None
        
        # Compatibilidad con código existente
        self.enabled = self.stt_enabled or self.llm_enabled
        if not self.enabled:
            logger.warning("⚠️ Ninguna API de IA configurada. Servicios deshabilitados.")
    
    def _get_plantilla_estructurada(self, tipo_plantilla, usuario=None):
        """
        Obtiene plantilla estructurada desde BD con fallback a hardcode.
        
        Args:
            tipo_plantilla (str): Código de plantilla (ej. 'RODILLA', 'CADERA')
        
        Returns:
            dict: {'titulo', 'seccion_tecnica', 'comentarios'} con fallback a hardcode
        """
        from .models import PlantillaEstructurada
        
        try:
            # Intentar leer desde BD (prioridad 1)
            queryset = PlantillaEstructurada.visibles_para_usuario(usuario, solo_activas=True)
            plantilla_obj = queryset.get(codigo=tipo_plantilla)
            logger.info(f"📋 Plantilla '{tipo_plantilla}' cargada desde BD (origen: {plantilla_obj.origen})")
            return {
                'titulo': plantilla_obj.titulo,
                'seccion_tecnica': plantilla_obj.seccion_tecnica,
                'comentarios': plantilla_obj.comentarios_base or []
            }
        except PlantillaEstructurada.DoesNotExist:
            logger.warning(f"⚠️ Plantilla '{tipo_plantilla}' no encontrada en BD, usando hardcode")
            return self._get_plantilla_hardcode(tipo_plantilla)
        except Exception as e:
            logger.error(f"❌ Error al leer plantilla desde BD: {str(e)}. Fallback a hardcode.")
            return self._get_plantilla_hardcode(tipo_plantilla)
    
    def _get_plantilla_hardcode(self, tipo_plantilla):
        """
        Diccionario hardcodeado de plantillas (fallback durante transición).
        
        TODO: Eliminar este método 1-2 semanas después de confirmar BD funcionando.
        """
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
                    'No se observan alteraciones en los tendones que conforman el manguito rotador ni en el tendón de la porción larga del bíceps.',
                    'Labrum de forma y señal normales.',
                    'No se visualiza aumento del liquido articular glenohumeral ni bursal.',
                    'Articulación acromioclavicular sin alteraciones.'
                ]
            },
            'CODO': {
                'titulo': 'RM DE CODO [<DERECHO/IZQUIERDO>]',
                'seccion_tecnica': 'Se exploró el codo [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                'comentarios': [
                    'Tendones epicondíleos y epitrocleares normales.',
                    'Resto de tendones y ligamentos de la articulación del codo sin alteraciones.',
                    'No se observa aumento del liquido articular.',
                    'No se visualizan lesiones óseas.'
                ]
            },
            'TOBILLO': {
                'titulo': 'RM DE TOBILLO [<DERECHO/IZQUIERDO>]',
                'seccion_tecnica': 'Se exploró el tobillo [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                'comentarios': [
                    'Tendones retromaleolares internos, retromaleolares externos y tendones flexores del pie sin alteraciones.',
                    'No se observa aumento del líquido articular.',
                    'Fascia plantar  y tendón de Aquiles de espesor y señal normales.',
                    'No se visualizan lesiones óseas.'
                ]
            },
            'ANTEBRAZO': {
                'titulo': 'RM DE ANTEBRAZO [<DERECHO/IZQUIERDO>]',
                'seccion_tecnica': 'Se exploró el antebrazo [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                'comentarios': [
                    'Estructuras óseas del radio y cúbito sin alteraciones.',
                    'Músculos del antebrazo de morfología y señal normales.',
                    'Tendones flexores y extensores conservados.',
                    'Nervios mediano, radial y cubital sin signos de compresión.',
                    'No se observa aumento del líquido articular.',
                    'No se visualizan lesiones óseas.'
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
                    'Espacio articular coxo-femoral conservado.',
                    'Labrum sin alteraciones.',
                    'No se visualiza aumento del líquido articular.',
                    'No se observan lesiones óseas.'
                ]
            },
            'MUSLO': {
                'titulo': 'RM DE MUSLO [<DERECHO/IZQUIERDO>]',
                'seccion_tecnica': 'Se exploró el muslo [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                'comentarios': [
                    'Músculos del muslo de morfología y señal normales.',
                    'Tendones y ligamentos sin alteraciones.',
                    'No se observan colecciones ni masas.',
                    'No se visualizan lesiones óseas.'
                ]
            },
            'ATM': {
                'titulo': 'RM DE ARTICULACIÓN TEMPOROMANDIBULAR [<DERECHA/IZQUIERDA>]',
                'seccion_tecnica': 'Se exploró la articulación temporomandibular [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.',
                'comentarios': [
                    'Disco articular de morfología y señal normales.',
                    'En fase de apertura, correcta translación del cóndilo mandibular y recaptura del disco.',
                    'Músculos masticatorios sin alteraciones.',
                    'Articulación sin signos de inflamación.',
                    'No se visualizan lesiones óseas.'
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
            },
            'ABDOMEN C/G': {
                'titulo': 'RM DE ABDOMEN CON GADOLINIO',
                'seccion_tecnica': 'Se realizó resonancia magnética de abdomen y pelvis, mediante secuencias que ponderan tiempos de relajación T1 y T2 en los diferentes planos. Se inyectó gadolinio endovenoso.',
                'comentarios': [
                    'Fondos de saco pleurales libres.',
                    'El hígado y el bazo presentan morfología e intensidad de señal respetadas.',
                    'Vesícula biliar presente, de contenido homogéneo. No se observa dilatación de la vía biliar intra ni extra hepática.',
                    'Páncreas bien delimitado y sin lesión visible.',
                    'Glándulas suprarrenales de configuración habitual.',
                    'Ambos riñones de forma y tamaño normal, sin signos de hidronefrosis.',
                    'El retroperitoneo prevertebral se halla libre de adenomegalias.',
                    'No se constatan procesos expansivos ni líquido libre en cavidad al momento del examen.'
                ]
            },
            'TORAX S/G': {
                'titulo': 'RM DE TÓRAX SIN CONTRASTE',
                'seccion_tecnica': 'Se realizó resonancia magnética de tórax, mediante secuencias que ponderan tiempos de relajación T1 y T2 en los diferentes planos, sin administración de contraste endovenoso.',
                'comentarios': [
                    'No se identifican procesos ocupantes ni áreas de consolidación parenquimatosa, dentro de las limitaciones del método.',
                    'Mediastino, hilios y axilas libres de imágenes adenomegálicas.',
                    'No se observa derrame pleural ni pericárdico.'
                ]
            }
        }
        
        return plantillas.get(tipo_plantilla, plantillas['RODILLA'])
    
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
            'provider': self.llm_provider,
            'model': self.llm_model,
            'enabled': True,
            'fallback': 'Groq (gratis)' if self.groq_fallback else None
        }
        
        # Límites según proveedor
        if self.llm_provider == 'openai':
            info['limits'] = {
                'cost': 'PAGO',
                'model': 'GPT-4o-mini',
                'input_cost': '$0.15 / 1M tokens',
                'output_cost': '$0.60 / 1M tokens',
                'estimated_per_report': '~$0.0003 USD',
                'estimated_monthly': '~$5-10 USD (30 informes/día)',
                'description': 'Calidad superior para terminología médica, con fallback gratuito a Groq'
            }
        elif self.llm_provider == 'groq':
            info['limits'] = {
                'requests_per_day': 14400,
                'requests_per_minute': 30,
                'tokens_per_minute': 20000,
                'cost': 'GRATIS',
                'description': 'Plan gratuito de Groq con límite diario generoso'
            }
        elif self.llm_provider == 'openai':
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
        if not self.stt_enabled:
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
            transcript = self.stt_client.audio.transcriptions.create(
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
    
    def improve_medical_text(self, texto_original, tipo_estudio, contexto=None, usuario=None, custom_prompt=None):
        """
        Mejora el texto dictado usando GPT-4 para darle formato médico profesional
        🚀 OPTIMIZADO: Caché multicapa con hash inteligente
        🤖 FASE 2: Soporte para custom_prompt (sistema conversacional)
        
        Args:
            texto_original: Texto transcrito del audio
            tipo_estudio: Tipo de estudio (RES, TOM, etc.)
            contexto: Contexto adicional (dict con datos del paciente, plantilla, etc.)
            usuario: Usuario que realiza la solicitud
            custom_prompt: (Opcional) Prompt personalizado pre-construido. Si se provee, 
                          se usa en lugar de generar el prompt internamente.
        
        Returns:
            dict: {'texto_mejorado': str, 'confianza': float, 'sugerencias': list}
        """
        if not self.llm_enabled:
            return {
                'texto_mejorado': texto_original,
                'confianza': 0.0,
                'sugerencias': [],
                'error': 'API de LLM no configurada'
            }
        
        # Normalizar contexto
        contexto = contexto or {}
        modo = contexto.get('modo', 'LIBRE')
        
        # 🚀 CACHÉ: Generar hash único para esta mejora
        # NOTA: Si usa custom_prompt, NO usar caché (siempre único en modo conversacional)
        if custom_prompt:
            cache_key = None  # Deshabilitar caché en modo conversacional
            logger.info("🤖 Modo conversacional activo - caché deshabilitado")
        else:
            cache_key_parts = [
                texto_original,
                tipo_estudio,
                modo,
                str(usuario.id if usuario and hasattr(usuario, 'id') else 'anonimo')
            ]
            cache_key_str = '|'.join(cache_key_parts)
            cache_hash = hashlib.md5(cache_key_str.encode()).hexdigest()
            cache_key = f'mejora_texto_{cache_hash}'
            
            # Verificar caché
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.info(f"⚡ Texto mejorado recuperado del caché (hash: {cache_hash[:8]}...)")
                cached_result['from_cache'] = True
                return cached_result
        
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
        plantilla_actual = None
        
        # Detectar si hay plantilla activa (SOLO si NO es modo FIEL)
        plantilla = contexto.get('plantilla') if modo != 'FIEL' else None
        
        # MODO PLANTILLA: Completar campos específicos respetando estructura
        if plantilla and modo != 'FIEL':
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

INDICACIÓN CLÍNICA
[Completar con información dictada sobre síntomas, región, patología sospechada]

TÉCNICA
[SI YA EXISTE EN PLANTILLA: mantener exactamente igual. SI ESTÁ VACÍO: usar descripción técnica apropiada]

HALLAZGOS
[Completar con observaciones dictadas, usando terminología médica precisa]

CONCLUSIÓN
[Resumir hallazgos patológicos encontrados]

IMPORTANTE: 
- Títulos en MAYÚSCULAS, sin asteriscos ni markdown
- CADA hallazgo en su propia línea con SALTO DE LÍNEA después
- NO escribir todos los hallazgos en un solo párrafo
- SIN viñetas ni guiones
- NO modifiques contenido pre-existente de la plantilla
- Si la Técnica ya está completa, devuélvela SIN CAMBIOS
- Cada sección debe terminar con línea en blanco

CONCLUSIÓN - REGLAS OBLIGATORIAS:
1. JERARQUIZAR: patología principal → asociados → secundarios
2. REDACCIÓN DIRECTA: "Desgarro del LCA" (NO "se observa desgarro")
3. TEXTO CORRIDO narrativo (NO ítems ni viñetas en conclusión)
4. TERMINOLOGÍA ESTÁNDAR: gonartrosis, meniscopatía, tendinopatía, condromalacia
5. 2-4 líneas máximo, sin repetir frases literales
6. NO describir estructuras normales, NO sugerencias clínicas
7. Si TODO normal → "Estudio dentro de los parámetros normales."

EJEMPLO DE FORMATO CORRECTO EN HALLAZGOS:
Hallazgo estructural número 1.
Hallazgo estructural número 2.
Hallazgo estructural número 3.

NO HACER (todo junto):
Hallazgo 1. Hallazgo 2. Hallazgo 3."""
        
        # MODO LIBRE O FIEL: No usar plantilla
        else:
            # 🧠 Obtener ejemplos de aprendizaje del usuario (SIEMPRE)
            ejemplos_aprendizaje = self._get_ejemplos_aprendizaje_cached(usuario)
            ejemplos_estilo = self._get_ejemplos_estilo_cached(usuario) if modo != 'FIEL' else None
            
            if modo == 'FIEL':
                logger.info("✏️ Modo FIEL AL DICTADO - solo corrección ortográfica")
                # 🚀 PROMPT OPTIMIZADO: 60% más corto, misma efectividad
                
                # Construir secciones del prompt de forma modular
                prompt_partes = [f"""CORRECTOR ORTOGRÁFICO ESTRICTO

Tu ÚNICA tarea: Corregir ortografía del siguiente texto SIN modificar nada más.

TEXTO A CORREGIR:
{texto_original}

INSTRUCCIONES CRÍTICAS:
❌ NO agregues estructura (TÉCNICA, COMENTARIO, CONCLUSIÓN, etc.)
❌ NO crees plantillas ni secciones
❌ NO expandes el texto ni agregas información
❌ NO reorganices ni reformules
✅ SOLO corrige: ortografía, acentos, mayúsculas, términos médicos
✅ Mantén EXACTAMENTE el mismo formato y longitud
✅ Respeta saltos de línea originales

Devuelve ÚNICAMENTE el texto corregido, tal como está, solo con ortografía mejorada:"""]
                
                if ejemplos_estilo:
                    logger.info(f"🎨 Aplicando estilo personal del usuario")
                    # Extracto compacto de ejemplos (máximo 200 caracteres)
                    estilo_compacto = ejemplos_estilo[:200] + "..." if len(ejemplos_estilo) > 200 else ejemplos_estilo
                    prompt_partes.append(f"\n(Referencia de terminología: {estilo_compacto})")
                
                if ejemplos_aprendizaje:
                    # Limitar ejemplos a 5 líneas
                    lineas_ejemplos = ejemplos_aprendizaje.split('\n')[:5]
                    ejemplos_compactos = '\n'.join(lineas_ejemplos)
                    prompt_partes.append(f"\n(Correcciones previas: {ejemplos_compactos})")
                
                prompt = "\n".join(prompt_partes)

            else:
                # MODO ESTRUCTURADO: Crear informe con plantilla específica según tipo
                tipo_plantilla = contexto.get('tipo_plantilla', 'RODILLA')
                tipo_plantilla_alias = {
                    'TORAX_SG': 'TORAX S/G',
                }
                tipo_plantilla = tipo_plantilla_alias.get(tipo_plantilla, tipo_plantilla)
                logger.info(f"📋 Generando plantilla tipo: {tipo_plantilla}")
                
                # 🔄 LEER PLANTILLA DESDE BD (con fallback a hardcode)
                plantilla_actual = self._get_plantilla_estructurada(tipo_plantilla, usuario=usuario)
                comentarios_str = '\n'.join(plantilla_actual['comentarios'])
                
                # 🚀 PROMPT OPTIMIZADO: 50% más corto usando formato compacto
                prompt = f"""Radiólogo experto: Genera informe de {tipo_nombre} según dictado.

📝 DICTADO:
{texto_original}

📋 ESTRUCTURA:
{plantilla_actual['titulo']}

INFORMACIÓN CLÍNICA
[Síntomas/antecedentes del dictado]

TÉCNICA
{plantilla_actual['seccion_tecnica']}

COMENTARIO
[Hallazgos - 1 línea por estructura]

CONCLUSIÓN
[Resumen diagnóstico]

🎯 REGLAS CRÍTICAS DE FORMATO:
▶ CADA hallazgo debe estar en su PROPIA LÍNEA
▶ Termina cada oración con punto y NUEVA LÍNEA
▶ NO escribas todo en un solo párrafo
▶ Si un mismo hallazgo afecta múltiples espacios/regiones, escribir UNA sola línea agrupando localizaciones con comas y "y"
▶ Ejemplo CORRECTO:
  Hallazgo 1.
  Hallazgo 2.
  Hallazgo 3.
▶ Ejemplo INCORRECTO:
  Hallazgo 1. Hallazgo 2. Hallazgo 3.

🎯 REGLAS:
1. FORMATO: Títulos en MAYÚSCULAS sin asteriscos. Una línea por hallazgo SIN viñetas (-) ni bullets.
1.1 FIDELIDAD AL DICTADO: Mantener la idea clínica original y su relación causal/anatómica. No reformular en frases telegráficas.
1.2 NO FRAGMENTAR: Si el dictado expresa una misma patología con complemento (ej. "lesión ... con edema adyacente"), mantenerlo en UNA sola línea.

2. COMENTARIO - LÓGICA DE REEMPLAZO:
   ⚠️ CRÍTICO: SOLO reemplaza las líneas de estructuras que DICTÓ el usuario.
   ✅ CONSERVA todas las líneas normales de estructuras NO mencionadas.
   
   Base normal: {comentarios_str}
   
   EJEMPLO DE LÓGICA:
   Si dicta: "desgarro menisco interno, quiste de Baker"
   
   CORRECTO ✅:
   Desgarro del menisco interno.
   Menisco externo de configuración normal.
   Ligamentos cruzados de trayecto y morfología conservados. ← CONSERVÓ (no mencionado)
   Resto de tendones y ligamentos sin alteraciones. ← CONSERVÓ (no mencionado)
   Rótula centrada, sin lesión visible. ← CONSERVÓ (no mencionado)
   Quiste de Baker de [tamaño].
   No se observa aumento del líquido articular. ← CONSERVÓ (no mencionado)
   No se visualizan lesiones óseas. ← CONSERVÓ (no mencionado)
   
   INCORRECTO ❌:
   Desgarro del menisco interno.
   Menisco externo normal.
   Quiste de Baker.
   ← ELIMINÓ ligamentos, tendones, rótula (MAL!)
   
3. Si dice "el resto normal" / "el resto sin alteraciones":
   → Mantén TODAS las líneas normales de la plantilla para estructuras no mencionadas
   → Al final agrega: "Resto de estructuras sin particularidades."
   
4. Si dicta "desgarro LCA" → elimina "ligamentos conservados", coloca en posición anatómica correspondiente
4. Si dicta "desgarro LCA" → elimina "ligamentos conservados", coloca en posición anatómica correspondiente
5. Lenguaje coloquial → terminología médica precisa
6. NO inventes hallazgos no dictados
7. Elimina contradicciones (ej: patología + "sin alteraciones" de misma estructura)
8. ⚠️ NO ELIMINES líneas normales de estructuras no mencionadas

💡 EJEMPLO COMPLETO:
Dictado: "rodilla derecha, trauma, desgarro LCA, derrame articular"

RM DE RODILLA DERECHA

INFORMACIÓN CLÍNICA
Antecedente de trauma.

TÉCNICA
Se exploró la rodilla derecha con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.

COMENTARIO
Desgarro del ligamento cruzado anterior.
Ligamento cruzado posterior conservado.
Meniscos de altura y señal normales.
Resto de tendones y ligamentos de la rodilla sin alteraciones.
Rótula centrada, sin lesión visible.
Derrame articular a predominio del receso suprapatelar.
No se visualizan lesiones óseas.

CONCLUSIÓN
Desgarro del ligamento cruzado anterior con derrame articular asociado.

🎯 CONCLUSIÓN - ESTILO RADIÓLOGO PROFESIONAL:

PRINCIPIOS FUNDAMENTALES:
1. JERARQUIZACIÓN CLÍNICA - Ordenar por relevancia médica:
   • Primero: Lesión principal o diagnóstico clave (desgarro, fractura, masa)
   • Segundo: Hallazgos directamente relacionados (edema óseo asociado, extrusión meniscal)
   • Tercero: Hallazgos secundarios/inflamatorios (derrame, sinovitis, edema de partes blandas)
   • Cierre (si aplica): "Resto de estructuras sin particularidades" o frase equivalente

2. TERMINOLOGÍA RADIOLÓGICA ESTÁNDAR - Usar lenguaje profesional preciso:
   ✅ USAR: meniscopatía degenerativa, desgarro complejo, gonartrosis tricompartimental
   ✅ USAR: condromalacia grado III-IV, tendinopatía, entesitis, extrusión meniscal
   ✅ USAR: edema óseo subcondral, contusión ósea, cambios degenerativos
   ✅ USAR: derrame articular, sinovitis, tenosinovitis, bursitis
   ❌ EVITAR: "alteraciones inespecíficas", "cambios", "hallazgos"
   ❌ EVITAR: lenguaje vago o genérico

3. REDACCIÓN DIRECTA Y PROFESIONAL:
   ✅ Estilo afirmativo: "Desgarro del ligamento cruzado anterior"
   ❌ Evitar: "Se observa desgarro del LCA", "Se evidencia", "Se visualiza"
   ✅ Sustantivos y adjetivos, no verbos innecesarios
   ✅ Conectores naturales: "con", "asociado a", "que compromete"
   
4. FORMATO Y EXTENSIÓN:
   • Texto CORRIDO narrativo - UNA SOLA PIEZA de prosa
   • NO usar viñetas, ítems, ni listas numeradas en la conclusión
   • Longitud: 2-4 líneas máximo (conciso pero completo)
   • NO repetir frases textuales del COMENTARIO (parafrasear si es necesario)
   • Usar comas y puntos para separar hallazgos relacionados

5. COMPLETITUD Y PRECISIÓN:
   ✅ Incluir TODOS los hallazgos patológicos del COMENTARIO
   ✅ Especificar localización anatómica cuando sea relevante
   ✅ Mencionar lateralidad si es pertinente (medial/lateral, interno/externo)
   ❌ NO describir estructuras normales (salvo relevancia clínica específica)
   ❌ NO agregar recomendaciones clínicas ni correlación clínica
   ❌ NO omitir patología descrita en el COMENTARIO

6. CASOS ESPECIALES:
   • Estudio NORMAL → "Estudio dentro de los parámetros normales."
   • Estudio con hallazgo único → ser igualmente conciso y directo
   • Múltiples hallazgos → jerarquizar y agrupar lógicamente

EJEMPLOS DE CONCLUSIONES CORRECTAS:

Ejemplo 1 (lesión meniscal + edema):
"Meniscopatía determinada por desgarro horizontal que compromete el cuerpo y cuerno posterior del menisco interno, con edema óseo de aspecto contusivo en el cóndilo femoral medial asociado. Derrame articular leve."

Ejemplo 2 (manguito rotador):
"Tendinopatía del supraespinoso y tenosinovitis del tendón de la porción larga del bíceps, con edema óseo en la articulación acromioclavicular."

Ejemplo 3 (gonartrosis):
"Gonartrosis tricompartimental con condromalacia rotuliana grado III-IV. Meniscopatía degenerativa con desgarro complejo del menisco interno y extrusión meniscal asociada."

Ejemplo 4 (normal):
"Estudio dentro de los parámetros normales."

EJEMPLOS DE CONCLUSIONES INCORRECTAS:

❌ "Se observa desgarro del menisco interno. También se visualiza derrame articular."
   (Problema: verbos innecesarios, estructura fragmentada)

❌ "- Desgarro meniscal
    - Derrame articular  
    - Edema óseo"
   (Problema: formato de lista, no es prosa narrativa)

❌ "Meniscos normales. Ligamentos normales. Derrame articular presente."
   (Problema: menciona estructuras normales innecesariamente)

❌ "Hallazgos compatibles con cambios degenerativos inespecíficos."
   (Problema: lenguaje vago, poco profesional)

INSTRUCCIÓN FINAL:
Genera una conclusión que sea un párrafo narrativo profesional, jerarquizado, usando terminología radiológica precisa, sin verbos de observación innecesarios, que sintetice los hallazgos patológicos principales del COMENTARIO en 2-4 líneas máximo.

Ejemplo de estudio normal:
COMENTARIO
Meniscos de altura y señal normales.
Ligamentos cruzados de trayecto y morfología conservados.
[...todas las líneas normales...]

CONCLUSIÓN
Estudio dentro de los parámetros normales.

�🚫 PROHIBIDO:
- Usar asteriscos (**) en títulos
- Usar viñetas (-) o bullets (•) en COMENTARIO
- Markdown de cualquier tipo
- Escribir todo el COMENTARIO en un solo párrafo
- ELIMINAR líneas normales de la plantilla que no fueron mencionadas

✅ FORMATO CORRECTO: Texto plano profesional
✅ CRÍTICO: CADA hallazgo en su propia línea con SALTO DE LÍNEA después
✅ NO escribir todo junto: Cada oración termina con punto y NUEVA LÍNEA
✅ CONSERVAR líneas normales de estructuras no dictadas

9. CONCLUSIÓN (RADIÓLOGO PROFESIONAL):
   • Texto corrido, narrativo (NO ítems ni viñetas en la conclusión)
   • Redacción directa: "Desgarro del LCA" (NO "se observa desgarro")
   • Jerarquía: patología principal → asociados → secundarios → cierre
   • Terminología estándar (gonartrosis, meniscopatía, tendinopatía, etc.)
   • 2-4 líneas máximo, sin repetir frases literales del comentario
   • NO describir estructuras normales, NO agregar sugerencias clínicas
   • Si todo normal → "Estudio dentro de los parámetros normales."

10. Estudio comparativo → Primera línea COMENTARIO: "Comparativo con [fecha]"
11. Frases "el resto normal" → usa líneas normales plantilla (no la frase literal)"""
                
                # 🧠 AGREGAR EJEMPLOS DE APRENDIZAJE al prompt
                if ejemplos_aprendizaje:
                    prompt += f"""

🧠 SISTEMA DE APRENDIZAJE ACTIVO:
El usuario ha corregido previamente estos errores. Aplícalos automáticamente:

{ejemplos_aprendizaje}

Estos ejemplos tienen prioridad sobre cualquier otra consideración ortográfica o terminológica."""

                if ejemplos_estilo:
                    estilo_resumen = self._resumir_estilo_comentario(ejemplos_estilo)
                    if estilo_resumen:
                        prompt += f"""

🎨 GUÍA DE ESTILO PERSONAL (solo forma/orden, nunca contenido inventado):
{estilo_resumen}

Usa esta guía únicamente para ordenar y redactar el COMENTARIO con el estilo habitual del usuario."""
                
                prompt += "\n\nGenera el informe profesional en texto plano:"

        try:
            # 🤖 FASE 2: Si hay custom_prompt, usarlo directamente (modo conversacional)
            if custom_prompt:
                prompt = custom_prompt
                logger.info("🤖 Usando prompt conversacional personalizado")
                # En modo conversacional, usar system message genérico
                system_message = "Eres un médico radiólogo experto especializado en redacción de informes médicos profesionales. Sé preciso, profesional y conciso."
            else:
                # 🎯 System message dinámico según modo
                if modo == 'FIEL':
                    system_message = "Eres un corrector ortográfico médico. Tu ÚNICA función es corregir ortografía, acentos y mayúsculas sin modificar el contenido ni la estructura del texto. NO agregues, elimines o reorganices información. NO crees plantillas ni secciones."
                else:
                    system_message = "Eres un médico radiólogo experto especializado en redacción de informes médicos profesionales. IMPORTANTE: 1) Escribe cada hallazgo en su propia línea con salto después, nunca todo junto en un párrafo. 2) Usa texto plano sin markdown. 3) CONSERVA todas las líneas normales de la plantilla para estructuras que NO fueron mencionadas en el dictado. Solo reemplaza lo que fue dictado explícitamente."
            
            # 🎯 Temperature dinámico según modo
            if modo == 'FIEL':
                temperature = 0.05  # Máxima fidelidad - solo correcciones ortográficas
            elif custom_prompt:
                temperature = 0.2  # Modo conversacional - algo de flexibilidad
            else:
                temperature = 0.3  # Modo estructurado - permite creatividad en redacción
            
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": system_message
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                max_tokens=1500
            )
            
            texto_mejorado = response.choices[0].message.content.strip()
            guardrails_aplicados = []
            if modo != 'FIEL' and not custom_prompt and plantilla_actual:
                texto_mejorado, guardrails_aplicados = self._aplicar_guardrails_estructurado(
                    texto_original=texto_original,
                    texto_mejorado=texto_mejorado,
                    plantilla_actual=plantilla_actual
                )
            modo_usado = "PLANTILLA" if plantilla else modo
            analisis_invencion = self._detectar_posible_invencion_estructurada(
                texto_original=texto_original,
                texto_mejorado=texto_mejorado,
                plantilla_actual=plantilla_actual,
                modo=modo,
            )
            evaluacion_confianza = self._evaluar_confianza_resultado(
                texto_original=texto_original,
                texto_mejorado=texto_mejorado,
                modo=modo,
                analisis_invencion=analisis_invencion,
            )
            
            logger.info(f"✅ Texto mejorado con {self.llm_provider.upper()} ({self.llm_model})")
            
            # Calcular "confianza" basada en la longitud y coherencia
            confianza = min(0.95, len(texto_mejorado) / max(len(texto_original), 1))
            
            result = {
                'texto_mejorado': texto_mejorado,
                'confianza': confianza,
                'sugerencias': self._extract_suggestions(texto_original, texto_mejorado),
                'tokens_used': response.usage.total_tokens,
                'modo': modo_usado,
                'from_cache': False,
                'score_confianza': evaluacion_confianza['score'],
                'requiere_confirmacion': evaluacion_confianza['requiere_confirmacion'],
                'motivo_confianza': evaluacion_confianza['motivo'],
                'guardrails_aplicados': guardrails_aplicados,
                'posible_invencion': analisis_invencion['detectada'],
                'terminos_sospechosos': analisis_invencion['terminos_sospechosos'],
            }
            
            # 🚀 GUARDAR EN CACHÉ (30 minutos) - SOLO si NO es modo conversacional
            if cache_key:  # cache_key es None en modo conversacional
                cache.set(cache_key, result, timeout=1800)
                logger.info(f"💾 Resultado guardado en caché (hash: {cache_hash[:8]}...)")
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Error en mejora de texto con {self.llm_provider}: {str(e)}")
            
            # 🔄 FALLBACK: Intentar con Groq (gratis) si OpenAI falló
            if self.llm_provider == 'openai' and self.groq_fallback:
                logger.info("🔄 OpenAI falló, intentando fallback gratuito con Groq...")
                try:
                    # Reutilizar el mismo system_message
                    if modo == 'FIEL':
                        system_message = "Eres un corrector ortográfico médico. Tu ÚNICA función es corregir ortografía, acentos y mayúsculas sin modificar el contenido ni la estructura del texto. NO agregues, elimines o reorganices información. NO crees plantillas ni secciones."
                    else:
                        system_message = "Eres un médico radiólogo experto especializado en redacción de informes médicos profesionales. IMPORTANTE: 1) Escribe cada hallazgo en su propia línea con salto después, nunca todo junto en un párrafo. 2) Usa texto plano sin markdown. 3) CONSERVA todas las líneas normales de la plantilla para estructuras que NO fueron mencionadas en el dictado. Solo reemplaza lo que fue dictado explícitamente."
                    
                    response = self.groq_fallback.chat.completions.create(
                        model='llama-3.3-70b-versatile',
                        messages=[
                            {
                                "role": "system",
                                "content": system_message
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        temperature=0.2,
                        max_tokens=1500
                    )
                    
                    texto_mejorado = response.choices[0].message.content.strip()
                    guardrails_aplicados = []
                    if modo != 'FIEL' and not custom_prompt and plantilla_actual:
                        texto_mejorado, guardrails_aplicados = self._aplicar_guardrails_estructurado(
                            texto_original=texto_original,
                            texto_mejorado=texto_mejorado,
                            plantilla_actual=plantilla_actual
                        )
                    modo_usado = "PLANTILLA" if plantilla else modo
                    analisis_invencion = self._detectar_posible_invencion_estructurada(
                        texto_original=texto_original,
                        texto_mejorado=texto_mejorado,
                        plantilla_actual=plantilla_actual,
                        modo=modo,
                    )
                    evaluacion_confianza = self._evaluar_confianza_resultado(
                        texto_original=texto_original,
                        texto_mejorado=texto_mejorado,
                        modo=modo,
                        analisis_invencion=analisis_invencion,
                    )
                    
                    logger.info("✅ Texto mejorado con Groq (fallback)")
                    
                    confianza = min(0.95, len(texto_mejorado) / max(len(texto_original), 1))
                    
                    result = {
                        'texto_mejorado': texto_mejorado,
                        'confianza': confianza,
                        'sugerencias': self._extract_suggestions(texto_original, texto_mejorado),
                        'tokens_used': response.usage.total_tokens,
                        'modo': modo_usado,
                        'from_cache': False,
                        'score_confianza': evaluacion_confianza['score'],
                        'requiere_confirmacion': evaluacion_confianza['requiere_confirmacion'],
                        'motivo_confianza': evaluacion_confianza['motivo'],
                        'guardrails_aplicados': guardrails_aplicados,
                        'posible_invencion': analisis_invencion['detectada'],
                        'terminos_sospechosos': analisis_invencion['terminos_sospechosos'],
                    }
                    
                    # 🚀 GUARDAR EN CACHÉ (30 minutos)
                    cache.set(cache_key, result, timeout=1800)
                    logger.info(f"💾 Fallback guardado en caché (hash: {cache_hash[:8]}...)")
                    
                    return result
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback Groq también falló: {str(fallback_error)}")
            
            return {
                'texto_mejorado': texto_original,
                'confianza': 0.0,
                'sugerencias': [],
                'error': str(e)
            }
    
    def _get_ejemplos_aprendizaje_cached(self, usuario):
        """Óbtiene ejemplos de aprendizaje con caché por usuario (10 min)"""
        if not usuario:
            return None
        
        cache_key = f'ejemplos_aprendizaje_{usuario.id if hasattr(usuario, "id") else usuario}'
        cached = cache.get(cache_key)
        
        if cached:
            logger.info(f"📦 Ejemplos de aprendizaje recuperados del caché")
            return cached
        
        from .models import CorreccionAprendizaje
        ejemplos = CorreccionAprendizaje.obtener_ejemplos_aprendizaje(
            usuario=usuario,
            limite=10
        )
        
        if ejemplos:
            cache.set(cache_key, ejemplos, timeout=600)  # 🚀 Reducido a 10 min (antes 20)
            cantidad = len(ejemplos.split('\n'))
            logger.info(f"🧠 Sistema de aprendizaje: {cantidad} ejemplos activos")
        
        return ejemplos
    
    def _get_ejemplos_estilo_cached(self, usuario):
        """Óbtiene ejemplos de estilo completo con caché por usuario (15 min)"""
        if not usuario:
            return None
        
        cache_key = f'ejemplos_estilo_{usuario.id if hasattr(usuario, "id") else usuario}'
        cached = cache.get(cache_key)
        
        if cached:
            logger.info(f"📦 Ejemplos de estilo recuperados del caché")
            return cached
        
        from .models import CorreccionAprendizaje
        ejemplos = CorreccionAprendizaje.obtener_ejemplos_estilo_completo(
            usuario=usuario,
            limite=3
        )
        
        if ejemplos:
            cache.set(cache_key, ejemplos, timeout=900)  # 🚀 Reducido a 15 min (antes 30)
            logger.info(f"🎨 Ejemplos de estilo cargados (3 textos completos)")
        
        return ejemplos
    
    @staticmethod
    def invalidar_cache_usuario(usuario):
        """
        🚀 NUEVO: Invalida todo el caché de un usuario cuando se agregan nuevas correcciones
        
        Args:
            usuario: Usuario cuyo caché se debe invalidar
        """
        if not usuario:
            return
        
        usuario_id = usuario.id if hasattr(usuario, 'id') else usuario
        
        # Invalidar ejemplos de aprendizaje y estilo
        cache_keys = [
            f'ejemplos_aprendizaje_{usuario_id}',
            f'ejemplos_estilo_{usuario_id}'
        ]
        
        for key in cache_keys:
            cache.delete(key)
        
        logger.info(f"🧼 Caché de usuario {usuario_id} invalidado (nuevas correcciones)")
    
    @staticmethod
    def get_cache_stats():
        """
        🚀 NUEVO: Obtiene estadísticas del caché
        
        Returns:
            dict: Estadísticas del uso del caché
        """
        # Django cache no expone estadísticas directamente, pero podemos rastrear hits/miss
        # Esta es una implementación básica que se puede expandir
        return {
            'backend': 'django.core.cache',
            'strategy': 'multicapa',
            'layers': [
                'transcripciones_audio (1h)',
                'mejora_texto (30min)',
                'ejemplos_aprendizaje (10min)',
                'ejemplos_estilo (15min)'
            ]
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

    def _aplicar_guardrails_estructurado(self, texto_original, texto_mejorado, plantilla_actual):
        """
        Guardrail MVP para estructurado:
        - Preserva líneas normales de plantilla no mencionadas en el dictado.
        - No toca líneas donde el dictado ya mencionó explícitamente la estructura.
        """
        comentarios_base = (plantilla_actual or {}).get('comentarios', [])
        if not comentarios_base:
            return texto_mejorado, []

        lineas = (texto_mejorado or '').splitlines()
        idx_comentario = self._buscar_indice_header(lineas, {'COMENTARIO'})
        if idx_comentario is None:
            return texto_mejorado, []

        idx_fin = self._buscar_siguiente_header(
            lineas,
            idx_comentario + 1,
            {'CONCLUSION', 'CONCLUSIÓN', 'IMPRESION', 'IMPRESIÓN'}
        )
        if idx_fin is None:
            idx_fin = len(lineas)

        bloque_comentario = lineas[idx_comentario + 1:idx_fin]
        comentario_lineas = [l.strip() for l in bloque_comentario if l.strip()]
        dictado_lower = (texto_original or '').lower()

        # Consolidar fragmentación excesiva de una misma patología en líneas separadas.
        comentario_lineas, consolidado = self._consolidar_hallazgos_relacionados(
            comentario_lineas,
            texto_original,
        )

        restauradas = []
        for linea_base in comentarios_base:
            if self._linea_mencionada_en_dictado(linea_base, dictado_lower):
                continue

            if self._linea_equivalente_en_lista(linea_base, comentario_lineas):
                continue

            comentario_lineas.append(linea_base)
            restauradas.append(linea_base)

        if not restauradas and not consolidado:
            return texto_mejorado, []

        nuevas_lineas = []
        nuevas_lineas.extend(lineas[:idx_comentario + 1])
        nuevas_lineas.extend(comentario_lineas)
        nuevas_lineas.extend(lineas[idx_fin:])

        return '\n'.join(nuevas_lineas).strip(), restauradas

    def _consolidar_hallazgos_relacionados(self, comentario_lineas, texto_original):
        """
        Evita que una misma idea patológica se parta en frases telegráficas.

        Ejemplo:
        - "Lesión osteocondral en la rótula."
        - "Edema óseo adyacente en patelar."
        -> "Lesión osteocondral en la rótula, con edema óseo adyacente."
        """
        if len(comentario_lineas) < 2:
            return comentario_lineas, False

        patologias = {
            'lesion', 'lesión', 'edema', 'desgarro', 'ruptura', 'rotura', 'fractura',
            'contusion', 'contusión', 'derrame', 'sinovitis', 'bursitis', 'quiste',
            'tendinopatia', 'tendinopatía', 'tenosinovitis', 'condropatia', 'condropatía',
            'osteocondral', 'flogosis', 'elongacion', 'elongación'
        }
        conectores = {
            'adyacente', 'asociado', 'asociada', 'asociados', 'asociadas', 'concomitante',
            'a nivel', 'en', 'sobre', 'del mismo', 'ipsilateral'
        }
        stopwords = {
            'de', 'del', 'la', 'el', 'los', 'las', 'en', 'a', 'y', 'con', 'sin', 'por',
            'que', 'se', 'no', 'un', 'una', 'al', 'nivel', 'espacio', 'espacios'
        }

        dictado_norm = self._normalizar_texto_simple(texto_original)

        def contiene_patologia(linea):
            lnorm = self._normalizar_texto_simple(linea)
            return any(p in lnorm for p in patologias)

        def es_linea_normal(linea):
            lnorm = self._normalizar_texto_simple(linea)
            patrones_normales = [
                'sin alteraciones', 'sin lesiones', 'conservad', 'normal',
                'no se observa', 'no se visualiza', 'sin evidencia'
            ]
            return any(p in lnorm for p in patrones_normales)

        def tokens_anatomicos(linea):
            tokens = re.findall(r'[a-záéíóúñ]+', (linea or '').lower())
            resultado = []
            for t in tokens:
                if len(t) < 5 or t in stopwords:
                    continue
                if t in patologias:
                    continue
                resultado.append(t)
            return set(resultado)

        def linea_relacionada(l1, l2):
            n1 = self._normalizar_texto_simple(l1)
            n2 = self._normalizar_texto_simple(l2)
            if not contiene_patologia(l1) or not contiene_patologia(l2):
                return False
            if es_linea_normal(l1) or es_linea_normal(l2):
                return False

            anatomia_1 = tokens_anatomicos(l1)
            anatomia_2 = tokens_anatomicos(l2)
            comparte_anatomia = len(anatomia_1 & anatomia_2) > 0
            tiene_conector = any(c in n2 for c in conectores)
            tiene_huella_dictado = (n1 in dictado_norm and n2 in dictado_norm)

            return comparte_anatomia or (tiene_conector and (comparte_anatomia or tiene_huella_dictado))

        def fusionar(l1, l2):
            base = (l1 or '').strip().rstrip('.')
            extra = (l2 or '').strip().rstrip('.')
            extra_lower = extra[:1].lower() + extra[1:] if extra else extra
            if re.match(r'^(edema|derrame|sinovitis|bursitis|tenosinovitis|flogosis)\b', extra_lower, re.IGNORECASE):
                return f"{base}, con {extra_lower}."
            return f"{base}, {extra_lower}."

        nuevas = []
        i = 0
        consolidado = False

        while i < len(comentario_lineas):
            actual = comentario_lineas[i].strip()
            if i + 1 < len(comentario_lineas) and linea_relacionada(actual, comentario_lineas[i + 1]):
                unificada = fusionar(actual, comentario_lineas[i + 1])
                nuevas.append(unificada)
                consolidado = True
                i += 2
                continue

            nuevas.append(actual)
            i += 1

        return nuevas, consolidado

    def _normalizar_texto_simple(self, texto):
        tabla = str.maketrans('áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')
        return (texto or '').translate(tabla).lower()

    def _formatear_lista_es(self, elementos):
        if not elementos:
            return ''
        if len(elementos) == 1:
            return elementos[0]
        if len(elementos) == 2:
            return f"{elementos[0]} y {elementos[1]}"
        return f"{', '.join(elementos[:-1])} y {elementos[-1]}"

    def _resumir_estilo_comentario(self, ejemplos_estilo):
        """Extrae pocas líneas útiles del bloque COMENTARIO para guiar estilo sin contaminar contenido."""
        if not ejemplos_estilo:
            return ''

        texto = ejemplos_estilo.replace('\r\n', '\n')
        bloque = ''

        patron = re.compile(
            r'COMENTARIO\s*\n(?P<bloque>.*?)(?:\n\s*CONCLUSI[ÓO]N\s*\n|\n\s*---\s*\n|\Z)',
            re.IGNORECASE | re.DOTALL,
        )
        match = patron.search(texto)
        if match:
            bloque = match.group('bloque')
        else:
            bloque = texto

        lineas = [l.strip() for l in bloque.split('\n') if l.strip()]
        lineas = [l for l in lineas if not l.upper().startswith('EJEMPLO ')]
        if not lineas:
            return ''

        # Mantener resumen corto para no inflar tokens.
        lineas = lineas[:5]
        return '\n'.join(f"- {l}" for l in lineas)

    def _buscar_indice_header(self, lineas, headers):
        headers_norm = {h.upper() for h in headers}
        for i, linea in enumerate(lineas):
            limpia = linea.strip().upper().rstrip(':')
            if limpia in headers_norm:
                return i
        return None

    def _buscar_siguiente_header(self, lineas, start_idx, headers):
        headers_norm = {h.upper() for h in headers}
        for i in range(start_idx, len(lineas)):
            limpia = lineas[i].strip().upper().rstrip(':')
            if limpia in headers_norm:
                return i
        return None

    def _linea_mencionada_en_dictado(self, linea_base, dictado_lower):
        stopwords = {
            'de', 'del', 'la', 'el', 'los', 'las', 'sin', 'con', 'para', 'por',
            'que', 'una', 'uno', 'sus', 'sobre', 'signos', 'alteraciones', 'normal',
            'normales', 'conservado', 'conservados', 'observa', 'visualiza', 'lesiones'
        }

        tokens = re.findall(r'[a-záéíóúñ]+', (linea_base or '').lower())
        claves = [t for t in tokens if len(t) >= 5 and t not in stopwords]
        if not claves:
            return False

        for clave in claves:
            variantes = {clave}
            if clave.endswith('s'):
                variantes.add(clave[:-1])
            else:
                variantes.add(f'{clave}s')

            if any(variante and variante in dictado_lower for variante in variantes):
                return True

        return False

    def _linea_equivalente_en_lista(self, linea_base, lineas_generadas):
        base = (linea_base or '').strip().lower()
        if not base:
            return False

        for linea in lineas_generadas:
            ratio = difflib.SequenceMatcher(None, base, (linea or '').strip().lower()).ratio()
            if ratio >= 0.72:
                return True
        return False

    def _detectar_posible_invencion_estructurada(self, texto_original, texto_mejorado, plantilla_actual, modo):
        """
        Detector heurístico MVP de invención en modo estructurado.
        Marca términos clínicos relevantes en COMENTARIO que:
        - no aparecen en el dictado
        - no pertenecen a líneas normales de la plantilla base
        """
        if modo == 'FIEL' or not plantilla_actual:
            return {
                'detectada': False,
                'terminos_sospechosos': [],
            }

        lineas = (texto_mejorado or '').splitlines()
        idx_comentario = self._buscar_indice_header(lineas, {'COMENTARIO'})
        if idx_comentario is None:
            return {
                'detectada': False,
                'terminos_sospechosos': [],
            }

        idx_fin = self._buscar_siguiente_header(
            lineas,
            idx_comentario + 1,
            {'CONCLUSION', 'CONCLUSIÓN', 'IMPRESION', 'IMPRESIÓN'}
        )
        if idx_fin is None:
            idx_fin = len(lineas)

        comentario_lineas = [l.strip().lower() for l in lineas[idx_comentario + 1:idx_fin] if l.strip()]
        dictado_lower = (texto_original or '').lower()
        comentarios_base = [c.lower() for c in (plantilla_actual or {}).get('comentarios', [])]

        patologias_map = {
            'desgarro': ['desgarro', 'rotura', 'ruptura', 'fisura'],
            'fractura': ['fractura'],
            'edema': ['edema', 'edematoso'],
            'derrame': ['derrame', 'liquido articular', 'líquido articular'],
            'sinovitis': ['sinovitis'],
            'bursitis': ['bursitis'],
            'quiste': ['quiste'],
            'tendinopatia': ['tendinopatia', 'tendinopatía'],
            'tenosinovitis': ['tenosinovitis'],
            'condropatia': ['condropatia', 'condropatía', 'condromalacia'],
            'extrusion': ['extrusion', 'extrusión'],
            'lesion': ['lesion', 'lesión'],
        }

        estructuras_map = {
            'menisco': ['menisco', 'meniscal', 'meniscos'],
            'lca': ['lca', 'ligamento cruzado anterior'],
            'lcp': ['lcp', 'ligamento cruzado posterior'],
            'manguito_rotador': ['manguito rotador', 'supraespinoso', 'infraespinoso', 'subescapular'],
            'rotula': ['rotula', 'rótula', 'patela'],
            'labrum': ['labrum'],
            'cartilago': ['cartilago', 'cartílago'],
            'biceps': ['biceps', 'bíceps'],
            'bursa': ['bursa'],
            'ligamento': ['ligamento', 'ligamentos'],
        }

        dictado_patologias = self._detectar_tags(dictado_lower, patologias_map)
        dictado_estructuras = self._detectar_tags(dictado_lower, estructuras_map)

        sospechosos = []
        for linea in comentario_lineas:
            if self._linea_equivalente_en_lista(linea, comentarios_base):
                continue

            linea_patologias = self._detectar_tags(linea, patologias_map)
            if not linea_patologias:
                continue

            linea_estructuras = self._detectar_tags(linea, estructuras_map)
            patologias_no_dictadas = linea_patologias - dictado_patologias

            if not patologias_no_dictadas:
                continue

            estructura_soportada = bool(linea_estructuras & dictado_estructuras)

            # Heurística anti falso positivo: si la estructura está en dictado,
            # no forzar sospecha por diferencia terminológica de patología.
            if estructura_soportada:
                continue

            for termino in sorted(patologias_no_dictadas):
                if termino not in sospechosos:
                    sospechosos.append(termino)

        return {
            'detectada': len(sospechosos) > 0,
            'terminos_sospechosos': sospechosos[:5],
        }

    def _detectar_tags(self, texto, mapa_tags):
        texto_lower = (texto or '').lower()
        encontrados = set()
        for tag, aliases in mapa_tags.items():
            if any(alias in texto_lower for alias in aliases):
                encontrados.add(tag)
        return encontrados

    def _evaluar_confianza_resultado(self, texto_original, texto_mejorado, modo, analisis_invencion=None):
        """
        Evalúa si la salida requiere confirmación manual por baja confianza.

        Reglas iniciales MVP:
        - FIEL: muy estricto (si cambia estructura o se expande demasiado, baja confianza).
        - ESTRUCTURADO/LIBRE: alerta si la divergencia es muy alta.
        """
        original = (texto_original or '').strip()
        mejorado = (texto_mejorado or '').strip()

        if not original or not mejorado:
            return {
                'score': 0.0,
                'requiere_confirmacion': True,
                'motivo': 'Salida vacía o inválida'
            }

        ratio = difflib.SequenceMatcher(None, original.lower(), mejorado.lower()).ratio()
        score = round(ratio, 3)

        if modo == 'FIEL':
            headers_nuevos = re.search(r'\b(T[ÉE]CNICA|CONCLUSI[ÓO]N|COMENTARIO|INFORMACI[ÓO]N CL[ÍI]NICA)\b', mejorado, re.IGNORECASE)
            expansion_excesiva = len(mejorado) > (len(original) * 1.35)

            if headers_nuevos or expansion_excesiva or score < 0.78:
                motivo = 'Modo FIEL con cambios estructurales o expansión no esperada'
                return {
                    'score': score,
                    'requiere_confirmacion': True,
                    'motivo': motivo
                }

            return {
                'score': score,
                'requiere_confirmacion': False,
                'motivo': 'Modo FIEL consistente'
            }

        if analisis_invencion and analisis_invencion.get('detectada'):
            terminos = ', '.join(analisis_invencion.get('terminos_sospechosos', []))
            motivo = 'Posible invención detectada'
            if terminos:
                motivo = f'Posible invención detectada ({terminos})'
            return {
                'score': score,
                'requiere_confirmacion': True,
                'motivo': motivo
            }

        if score < 0.58:
            return {
                'score': score,
                'requiere_confirmacion': True,
                'motivo': 'Alta divergencia entre dictado y salida'
            }

        return {
            'score': score,
            'requiere_confirmacion': False,
            'motivo': 'Confianza suficiente'
        }

    def analizar_resultados_encuesta(self, datos_agregados: dict) -> dict:
        """
        Analiza los resultados de la encuesta de experiencia de residentes con IA.
        Genera texto listo para usar en un abstract de congreso (CADI 2026).

        Args:
            datos_agregados: dict con estructura:
                {
                  'n_respuestas': int,
                  'promedios': {p1..p10: float},
                  'promedio_global': float,
                  'respuestas_abiertas': {
                      'contexto_previo': [str, ...],
                      'util': [str, ...],
                      'mejora': [str, ...]
                  }
                }

        Returns:
            dict: {
                'resumen_ejecutivo': str,
                'hallazgos_por_dimension': dict,
                'cruce_contexto_vs_mejora': str,
                'citas_relevantes': [str],
                'texto_resultados_abstract': str,
                'texto_conclusiones_sugerido': str,
                'error': str|None
            }
        """
        if not self.llm_enabled:
            return {'error': 'API de LLM no configurada'}

        n = datos_agregados.get('n_respuestas', 0)
        promedios = datos_agregados.get('promedios', {})
        promedio_global = datos_agregados.get('promedio_global', 0)
        respuestas_abiertas = datos_agregados.get('respuestas_abiertas', {})

        contextos = respuestas_abiertas.get('contexto_previo', [])
        utiles = respuestas_abiertas.get('util', [])
        mejoras = respuestas_abiertas.get('mejora', [])

        # Construir resumen de respuestas abiertas para el prompt (máx 5 por cada una)
        def resumir_lista(lista, max_items=5):
            items = [r for r in lista if r and r.strip()][:max_items]
            return "\n".join(f"- \"{r}\"" for r in items) if items else "(sin respuestas)"

        prompt = f"""Sos un metodólogo médico experto en educación radiológica. 
        Analizá los resultados de la siguiente encuesta de satisfacción realizada a {n} residentes de diagnóstico por imágenes sobre un sistema digital de gestión de preinformes. El objetivo es preparar material para un E-Poster en el CADI 2026.

DATOS CUANTITATIVOS (escala 1-5):
- Usabilidad general: {promedios.get('p1', 0):.2f}
- Comodidad de acceso: {promedios.get('p2', 0):.2f}
- Utilidad del feedback del staff: {promedios.get('p3', 0):.2f}
- Oportunidad del feedback: {promedios.get('p4', 0):.2f}
- Mejora en redacción de informes: {promedios.get('p5', 0):.2f}
- Utilidad del banco de informes: {promedios.get('p6', 0):.2f}
- Mejora respecto al método anterior: {promedios.get('p7', 0):.2f}
- Utilidad del asistente IA: {promedios.get('p8', 0):.2f}
- Supervisión más estructurada: {promedios.get('p9', 0):.2f}
- Recomendaría a otros servicios: {promedios.get('p10', 0):.2f}
- PROMEDIO GLOBAL: {promedio_global:.2f}/5

FLUJO PREVIO AL SISTEMA (descripción de residentes):
{resumir_lista(contextos)}

LO MÁS ÚTIL DEL SISTEMA:
{resumir_lista(utiles)}

SUGERENCIAS DE MEJORA:
{resumir_lista(mejoras)}

Generá un análisis estructurado en formato JSON con las siguientes claves exactas:
{{
  "resumen_ejecutivo": "3-4 oraciones que resumen los hallazgos más importantes",
  "hallazgos_por_dimension": {{
    "usabilidad": "frase con el hallazgo",
    "feedback": "frase con el hallazgo",
    "aprendizaje": "frase con el hallazgo",
    "comparacion": "frase analizando el cruce entre el flujo previo descrito y la mejora percibida",
    "ia_y_supervision": "frase con el hallazgo",
    "recomendacion": "frase con el hallazgo"
  }},
  "cruce_contexto_vs_mejora": "Párrafo de 2-3 oraciones analizando la relación entre el flujo de trabajo previo descrito y la mejora percibida (pregunta 7)",
  "citas_relevantes": ["cita textual 1", "cita textual 2", "cita textual 3"],
  "texto_resultados_abstract": "Párrafo listo para la sección Resultados de un abstract de congreso médico (150-200 palabras, estilo científico en español)",
  "texto_conclusiones_sugerido": "Párrafo listo para la sección Conclusiones del abstract (60-80 palabras)"
}}

Respondé ÚNICAMENTE con el JSON válido, sin texto adicional."""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "Sos un metodólogo médico experto. Respondés siempre en JSON válido, en español argentino."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )
            resultado = response.choices[0].message.content
            import json as _json
            return _json.loads(resultado)
        except Exception as e:
            logger.error(f"Error en analizar_resultados_encuesta: {e}")
            return {'error': str(e)}


# Instancia global del servicio
ai_service = AIService()
