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
        
        # MODO LIBRE O FIEL: No usar plantilla
        else:
            # Obtener ejemplos de aprendizaje del usuario (con caché)
            ejemplos_aprendizaje = self._get_ejemplos_aprendizaje_cached(usuario)
            ejemplos_estilo = self._get_ejemplos_estilo_cached(usuario) if modo == 'FIEL' else None
            
            if modo == 'FIEL':
                logger.info("✏️ Modo FIEL AL DICTADO - solo corrección ortográfica")
                # MODO FIEL: Corregir ortografía + aplicar estilo del usuario
                
                if ejemplos_estilo:
                    logger.info(f"🎨 Aplicando estilo personal del usuario")
                    prompt_base = f"""Eres un corrector ortográfico ESTRICTO. Tu ÚNICA tarea es corregir ortografía sin cambiar nada más.

TEXTO DICTADO (SOLO CORRIGE ESTO):
{texto_original}

════════════════════════════════════════════════
EJEMPLOS DE ESTILO DEL USUARIO (solo referencia):
════════════════════════════════════════════════

{ejemplos_estilo}

════════════════════════════════════════════════

REGLAS ABSOLUTAS:
1. ✅ Corrige SOLO ortografía: acentos, mayúsculas, términos médicos
2. ❌ NO agregues información que no fue dictada
3. ❌ NO crees secciones (TÉCNICA, CONCLUSIÓN, etc.) si no fueron dictadas
4. ❌ NO repitas información de diferentes formas
5. ❌ NO inventes hallazgos adicionales
6. ✅ Si la oración termina sin punto, agrégalo
7. ✅ Respeta EXACTAMENTE lo que fue dictado, solo corrígelo

IMPORTANTE: El texto dictado es UNA SOLA ORACIÓN o fragmento. NO lo expandes en un informe completo.
Los ejemplos de estilo son solo para ver terminología, NO para copiar su estructura.

Devuelve SOLO el texto corregido, sin agregar nada más:"""
                else:
                    # Sin ejemplos de estilo, usar prompt básico
                    prompt_base = f"""Corrector ortográfico médico ESTRICTO. SOLO corrige ortografía del texto dictado.

TEXTO DICTADO:
{texto_original}

REGLAS ABSOLUTAS:
1. ✅ Corrige SOLO ortografía: acentos, mayúsculas, términos médicos
2. ❌ NO agregues información nueva
3. ❌ NO crees secciones ni estructura
4. ❌ NO repitas el texto de diferentes formas
5. ✅ Si termina sin punto, agrégalo
6. ✅ Respeta EXACTAMENTE lo dictado

Devuelve SOLO el texto corregido, una sola vez:"""
                
                # Agregar ejemplos de aprendizaje si existen (pero con advertencia)
                if ejemplos_aprendizaje:
                    prompt = f"""{prompt_base}

NOTA: Los siguientes son ejemplos de correcciones previas del usuario (NO los copies, solo aprende la terminología):
{ejemplos_aprendizaje}"""
                else:
                    prompt = prompt_base

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
                            'Cabeza femoral de morfología y señal normales.',
                            'Acetábulo sin alteraciones.',
                            'Labrum acetabular íntegro.',
                            'Músculos periarticulares sin signos de lesión.',
                            'No se observa aumento del líquido articular.',
                            'Estructuras óseas sin lesiones evidentes.'
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
                
                prompt = f"""Eres un médico radiólogo experto. Analiza el texto dictado y genera un informe radiológico profesional.

════════════════════════════════════════════════
TEXTO DICTADO:
════════════════════════════════════════════════
{texto_original}

════════════════════════════════════════════════
PLANTILLA BASE DE REFERENCIA:
════════════════════════════════════════════════
{plantilla_actual['titulo']}

INFORMACIÓN CLÍNICA
[Extraer del dictado]

TÉCNICA
{plantilla_actual['seccion_tecnica']}

COMENTARIO
{comentarios_str}

CONCLUSIÓN
[Impresión diagnóstica]

════════════════════════════════════════════════
INSTRUCCIONES PARA GENERAR EL INFORME:
════════════════════════════════════════════════

1️⃣ INFORMACIÓN CLÍNICA:
   • Incluye SOLO síntomas/antecedentes del paciente
   • ✅ Correcto: "Paciente con omalgia derecha", "Antecedente de trauma"
   • ❌ Prohibido: "tendinopatía", "desgarro" (son hallazgos radiológicos)

2️⃣ TÉCNICA:
   • Usa EXACTAMENTE la técnica de la plantilla
   • Reemplaza [<DERECHO/IZQUIERDO>] → DERECHO (sin corchetes)
   • Reemplaza [<lado>] → derecho (sin corchetes)

3️⃣ COMENTARIO - REGLAS INTELIGENTES:
   
   📋 FORMATO: Una línea por hallazgo/estructura (con saltos de línea)
   
   A) Si el usuario DICTA HALLAZGOS ESPECÍFICOS:
      • Usa exactamente lo que dictó
      • Una línea por hallazgo
      Ejemplo:
      Desgarro del ligamento cruzado anterior con avulsión cortical.
      Edema óseo en cóndilo femoral externo.
      Menisco externo con desgarro de rampa posterior.
   
   B) Si DICTA PATOLOGÍA GENÉRICA ("artrosis", "tendinopatía"):
      • Expande con hallazgos típicos razonables
      Ejemplo dictado "tendinopatía del supraespinoso":
      Tendinopatía del supraespinoso con señal aumentada.
      Desgarro parcial en su porción intrasustancial.
   
   C) Para estructuras NO mencionadas:
      • Usa las líneas normales de la plantilla. Deja las que no apliquen si ya se describió patología.
      
   D) Si dice que es estudio comparativo:
        • Agrega línea inicial en COMENTARIO: "Estudio comparativo con RM de [<FECHA>]."
        • Usa hallazgos dictados para diferencias. Si no hay diferencias, indica "No se observan diferencias significativas respecto al estudio previo."
   
   D) 🚫 ELIMINACIÓN DE CONTRADICCIONES (CRÍTICO):
      
      REGLA: Si describes patología en una estructura → ELIMINA su línea "sin alteraciones"
      
      ❌ Prohibido:
      • "Desgarro del LCA" + "Ligamentos cruzados conservados"
      • "Derrame articular" + "No se observa aumento del líquido articular"
      • "Tendinopatía de epicondilia" + "Epicóndilos sin epicondilitis"
      
      🗺️ MAPEO ANATÓMICO (sinónimos):
      • "desgarro del LCA" contradice "ligamentos cruzados conservados"
      • "derrame articular" contradice "no se observa aumento del líquido articular"
      • "tendinopatía de epicondilia" = "epicondilitis"
      • "supraespinoso" pertenece al "manguito rotador"
      • "edema óseo" contradice "estructuras óseas sin alteraciones"
      
      Si mencionas patología, NO puede existir línea normal de esa estructura.
   
   E) 🏁 CIERRE PROFESIONAL:
      • Después de listar TODAS las patologías
      • Conserva aquellas lineas normales que NO se contradigan. Indican normalidad residual.

4️⃣ CONCLUSIÓN:
   • Resumen diagnóstico breve pero que no omita hallazgos patológicos importantes. 
   • NO repitas todo el comentario

════════════════════════════════════════════════
EJEMPLO COMPLETO:
════════════════════════════════════════════════

Dictado: "Rodilla derecha con trauma. Desgarro del LCA con avulsión. Edema en cóndilo femoral externo y platillos tibiales. Desgarro meniscal externo. Derrame articular."

Informe correcto:

RM DE RODILLA DERECHA

INFORMACIÓN CLÍNICA
Paciente con antecedente de trauma de rodilla derecha.

TÉCNICA
Se exploró la rodilla derecha con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.

COMENTARIO
Desgarro con avulsión cortical en la inserción distal del ligamento cruzado anterior.
Edema óseo contusivo en el cóndilo femoral externo y en el margen posterior de ambos platillos tibiales.
Menisco externo muestra hallazgo compatible con desgarro de su rampa posterior inferior.
Marcado derrame articular a predominio del receso suprapatelar.
No se observan otras lesiones tendinosas ni ligamentarias.

CONCLUSIÓN
Desgarro con avulsión cortical del ligamento cruzado anterior y desgarro meniscal externo. Edema óseo contusivo.

════════════════════════════════════════════════

⚠️ REGLAS CRÍTICAS:
✓ Una línea por hallazgo (no todo junto)
✓ NO contradecirse internamente
✓ NO inventar hallazgos no dictados
✓ Eliminar completamente corchetes [<...>]
✓ Cierre profesional indicando normalidad residual
✓ Lenguaje técnico conciso y profesional

Genera el informe siguiendo estas reglas:"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
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
            modo_usado = "PLANTILLA" if plantilla else modo
            
            logger.info(f"✅ Texto mejorado con {self.llm_provider.upper()} ({self.llm_model})")
            
            # Calcular "confianza" basada en la longitud y coherencia
            confianza = min(0.95, len(texto_mejorado) / max(len(texto_original), 1))
            
            return {
                'texto_mejorado': texto_mejorado,
                'confianza': confianza,
                'sugerencias': self._extract_suggestions(texto_original, texto_mejorado),
                'tokens_used': response.usage.total_tokens,
                'modo': modo_usado
            }
        
        except Exception as e:
            logger.error(f"❌ Error en mejora de texto con {self.llm_provider}: {str(e)}")
            
            # 🔄 FALLBACK: Intentar con Groq (gratis) si OpenAI falló
            if self.llm_provider == 'openai' and self.groq_fallback:
                logger.info("🔄 OpenAI falló, intentando fallback gratuito con Groq...")
                try:
                    response = self.groq_fallback.chat.completions.create(
                        model='llama-3.3-70b-versatile',
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
                        temperature=0.2,
                        max_tokens=1500
                    )
                    
                    texto_mejorado = response.choices[0].message.content.strip()
                    modo_usado = "PLANTILLA" if plantilla else modo
                    
                    logger.info("✅ Texto mejorado con Groq (fallback)")
                    
                    confianza = min(0.95, len(texto_mejorado) / max(len(texto_original), 1))
                    
                    return {
                        'texto_mejorado': texto_mejorado,
                        'confianza': confianza,
                        'sugerencias': self._extract_suggestions(texto_original, texto_mejorado),
                        'tokens_used': response.usage.total_tokens,
                        'modo': modo_usado
                    }
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback Groq también falló: {str(fallback_error)}")
            
            return {
                'texto_mejorado': texto_original,
                'confianza': 0.0,
                'sugerencias': [],
                'error': str(e)
            }
    
    def _get_ejemplos_aprendizaje_cached(self, usuario):
        """Obtiene ejemplos de aprendizaje con caché por usuario (20 min)"""
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
            cache.set(cache_key, ejemplos, timeout=1200)  # 20 minutos
            cantidad = len(ejemplos.split('\n'))
            logger.info(f"🧠 Sistema de aprendizaje: {cantidad} ejemplos activos")
        
        return ejemplos
    
    def _get_ejemplos_estilo_cached(self, usuario):
        """Obtiene ejemplos de estilo completo con caché por usuario (30 min)"""
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
            cache.set(cache_key, ejemplos, timeout=1800)  # 30 minutos
            logger.info(f"🎨 Ejemplos de estilo cargados (3 textos completos)")
        
        return ejemplos
    
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
