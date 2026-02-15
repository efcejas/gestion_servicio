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
    
    def improve_medical_text(self, texto_original, tipo_estudio, contexto=None, usuario=None):
        """
        Mejora el texto dictado usando GPT-4 para darle formato médico profesional
        🚀 OPTIMIZADO: Caché multicapa con hash inteligente
        
        Args:
            texto_original: Texto transcrito del audio
            tipo_estudio: Tipo de estudio (RES, TOM, etc.)
            contexto: Contexto adicional (dict con datos del paciente, plantilla, etc.)
        
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
            ejemplos_estilo = self._get_ejemplos_estilo_cached(usuario) if modo == 'FIEL' else None
            
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
▶ Ejemplo CORRECTO:
  Hallazgo 1.
  Hallazgo 2.
  Hallazgo 3.
▶ Ejemplo INCORRECTO:
  Hallazgo 1. Hallazgo 2. Hallazgo 3.

🎯 REGLAS:
1. FORMATO: Títulos en MAYÚSCULAS sin asteriscos. Una línea por hallazgo SIN viñetas (-) ni bullets.

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
                
                prompt += "\n\nGenera el informe profesional en texto plano:"

        try:
            # 🎯 System message dinámico según modo
            if modo == 'FIEL':
                system_message = "Eres un corrector ortográfico médico. Tu ÚNICA función es corregir ortografía, acentos y mayúsculas sin modificar el contenido ni la estructura del texto. NO agregues, elimines o reorganices información. NO crees plantillas ni secciones."
            else:
                system_message = "Eres un médico radiólogo experto especializado en redacción de informes médicos profesionales. IMPORTANTE: 1) Escribe cada hallazgo en su propia línea con salto después, nunca todo junto en un párrafo. 2) Usa texto plano sin markdown. 3) CONSERVA todas las líneas normales de la plantilla para estructuras que NO fueron mencionadas en el dictado. Solo reemplaza lo que fue dictado explícitamente."
            
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
                temperature=0.2,  # Optimizado para modo FIEL: permite puntuación inteligente manteniendo fidelidad
                max_tokens=1500
            )
            
            texto_mejorado = response.choices[0].message.content.strip()
            modo_usado = "PLANTILLA" if plantilla else modo
            
            logger.info(f"✅ Texto mejorado con {self.llm_provider.upper()} ({self.llm_model})")
            
            # Calcular "confianza" basada en la longitud y coherencia
            confianza = min(0.95, len(texto_mejorado) / max(len(texto_original), 1))
            
            result = {
                'texto_mejorado': texto_mejorado,
                'confianza': confianza,
                'sugerencias': self._extract_suggestions(texto_original, texto_mejorado),
                'tokens_used': response.usage.total_tokens,
                'modo': modo_usado,
                'from_cache': False
            }
            
            # 🚀 GUARDAR EN CACHÉ (30 minutos)
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
                    modo_usado = "PLANTILLA" if plantilla else modo
                    
                    logger.info("✅ Texto mejorado con Groq (fallback)")
                    
                    confianza = min(0.95, len(texto_mejorado) / max(len(texto_original), 1))
                    
                    result = {
                        'texto_mejorado': texto_mejorado,
                        'confianza': confianza,
                        'sugerencias': self._extract_suggestions(texto_original, texto_mejorado),
                        'tokens_used': response.usage.total_tokens,
                        'modo': modo_usado,
                        'from_cache': False
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


# Instancia global del servicio
ai_service = AIService()
