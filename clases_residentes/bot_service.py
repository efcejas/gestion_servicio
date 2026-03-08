"""
Servicio de IA para bot de asistencia en presentaciones
"""
from openai import OpenAI
from django.core.cache import cache
from django.utils import timezone
from decouple import config
import logging
import re
import hashlib

logger = logging.getLogger(__name__)


class PresentacionesBot:
    """Bot de IA para asistencia en presentaciones académicas"""
    
    def __init__(self):
        """Inicializa el cliente OpenAI usando la misma configuración que dictado_informes"""
        openai_key = config('OPENAI_API_KEY', default=None)
        groq_key = config('GROQ_API_KEY', default=None)
        
        if openai_key:
            self.client = OpenAI(api_key=openai_key)
            self.model = 'gpt-4o-mini'
            self.provider = 'openai'
            logger.info("✅ Bot de presentaciones configurado con OpenAI GPT-4o-mini")
            
            # Groq como fallback
            if groq_key:
                self.fallback_client = OpenAI(
                    api_key=groq_key,
                    base_url="https://api.groq.com/openai/v1"
                )
                self.fallback_model = 'llama-3.3-70b-versatile'
            else:
                self.fallback_client = None
                
        elif groq_key:
            self.client = OpenAI(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.model = 'llama-3.3-70b-versatile'
            self.provider = 'groq'
            self.fallback_client = None
            logger.info("✅ Bot de presentaciones configurado con Groq (gratuito)")
        else:
            self.client = None
            self.fallback_client = None
            logger.error("❌ No hay API key configurada para el bot")
    
    def get_system_prompt(self, usuario=None):
        """
        Construye el prompt del sistema con todo el contexto de la guía de presentaciones.
        """
        nombre_usuario = ""
        if usuario:
            nombre = usuario.get_full_name() or usuario.first_name or usuario.username
            if nombre:
                nombre_usuario = f"\n\nEstás conversando con {nombre}, un/a residente del servicio de diagnóstico por imágenes. Podés usar su nombre de forma natural cuando sea apropiado (especialmente al inicio de la conversación o cuando des consejos personalizados)."
        
        return f"""Sos un asistente experto en presentaciones médicas académicas, especializado en ateneos clínicos y clases para residentes de diagnóstico por imágenes.{nombre_usuario}

Tu objetivo es ayudar a los residentes a crear mejores presentaciones respondiendo sus preguntas sobre:
- Estructura de ateneos y clases
- Citación de imágenes y bibliografía (formato Vancouver)
- Diseño visual de diapositivas
- Tips de presentación oral
- Buenas prácticas académicas
- Que acudan al Dr. Cejas o a la Dra. Avalo para consultas específicas de casos clínicos o imágenes. Obviamente, que deben saber que antes cuentan con el/la instructor/a para resolver dudas generales.

**CONTEXTO - ESTRUCTURA DE ATENEOS:**
- Portada: Título, nombre, fecha, institución
- Caso Clínico: Motivo de consulta, antecedentes, examen físico
- Estudios Complementarios: Análisis de laboratorio e imágenes con hallazgos principales
- Diagnósticos Diferenciales: Lista razonada de posibles diagnósticos
- Diagnóstico Final: Diagnóstico definitivo con justificación
- Discusión: Revisión bibliográfica, particularidades del caso
- Bibliografía: Referencias en Vancouver

Tips clave: Guardá el suspenso diagnóstico, mostrá las imágenes progresivamente, incluí hallazgos positivos y negativos.

**CONTEXTO - ESTRUCTURA DE CLASES:**
- Portada, Objetivos, Introducción, Desarrollo, Casos Ilustrativos, Conclusiones, Bibliografía
Tips: Dividí el contenido claramente, usá casos reales, incluí preguntas de repaso.

**CITACIÓN DE IMÁGENES (Vancouver):**
1. **De bases de datos/artículos:**
   Autor(es). Título [Tipo]. En: Fuente; Año. Disponible en: URL
   Ejemplo: Smith J. TC tórax COVID-19 [Imagen TC]. En: Radiopaedia; 2023. https://...
   💡 Acordate: ATE-FUA (Autor, Título, En, Fuente, URL, Año)

2. **Propias de la institución:**
   Fuente: Archivo personal del Servicio de Diagnóstico por Imágenes, Hospital X
   💡 Acordate: Siempre citá la fuente aunque sea interna
3. **Dominio público:**
   Imagen de dominio público. Fuente: Wikimedia Commons
   💡 Aunque sea gratis, citá la fuente igual

**CITACIÓN BIBLIOGRÁFICA (Vancouver):**
- Artículo: Autor. Título. Revista. Año;Vol(Num):págs.
- Libro: Autor. Título. Ed. Ciudad: Editorial; Año.
- Web: Autor. Título [Internet]. Ciudad: Editor; Año [citado Fecha]. URL

**DISEÑO VISUAL - REGLAS CLAVE:**
- Regla 6×6: Máx 6 líneas por diapo, 6 palabras por línea
- Fuentes: Sans-serif (Arial, Calibri) mín 24pt
- Contraste alto: Fondo oscuro + texto claro O viceversa
- Imágenes: Min 1024×768px, alta resolución
- Animaciones: Moderadas, solo si agregan valor

**PRESENTACIÓN ORAL:**
- Practicá 3 veces completas antes, medí el tiempo
- Contacto visual con audiencia, no leas la pantalla
- Explicá las imágenes, no asumas que todos ven lo mismo
- Respetá el tiempo, mejor terminar antes que pasarte
- Si no sabés algo, admitilo: "Buena pregunta, lo voy a investigar"

**ESTILO DE RESPUESTA:**
- Usá tono argentino (voseo): "Guardá", "Mostrá", "Dividí", "Usá", "Practicá"
- En los saludos inciales, usa el nombre del usuario si está disponible: "¡Hola [nombre]! ¿En qué puedo ayudarte con tu presentación?"
- Sé conciso pero completo
- Usá emojis de vez en cuando (💡, ✅, 📊, 🎯) para hacer más amigable
- Si te preguntan algo específico, dá el ejemplo concreto
- Si es pregunta general, dá overview con tips prácticos
- Siempre preguntá si necesitan aclaración o más detalles

Respondé en español argentino, de manera amigable y profesional."""

    def _normalize_question(self, mensaje):
        """
        Normaliza una pregunta para cache: lowercase, sin puntuación.
        """
        # Convertir a minúsculas
        normalized = mensaje.lower()
        # Remover puntuación y caracteres especiales
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Remover espacios múltiples
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _get_cache_key(self, mensaje):
        """
        Genera una clave de cache basada en el hash de la pregunta normalizada.
        """
        normalized = self._normalize_question(mensaje)
        hash_object = hashlib.md5(normalized.encode())
        return f"bot_response_{hash_object.hexdigest()}"

    def chat(self, usuario, mensaje, conversacion_id=None):
        """
        Procesa un mensaje del usuario y retorna la respuesta del bot.
        
        Args:
            usuario: Usuario de Django que envía el mensaje
            mensaje: Texto del mensaje
            conversacion_id: ID de conversación existente (opcional)
            
        Returns:
            dict con {respuesta, conversacion_id, success, error}
        """
        if not self.client:
            return {
                'success': False,
                'error': '⚠️ El bot no está configurado. Falta OPENAI_API_KEY en el .env',
                'respuesta': None,
                'conversacion_id': None
            }
        
        # Verificar cache primero
        cache_key = self._get_cache_key(mensaje)
        cached_response = cache.get(cache_key)
        
        if cached_response:
            logger.info(f"Respuesta obtenida del cache para: {mensaje[:50]}...")
            # Aún necesitamos guardar el mensaje en BD para el historial
            try:
                from .models import ConversacionBot, MensajeBot
                
                # Obtener o crear conversación
                if conversacion_id:
                    try:
                        conversacion = ConversacionBot.objects.get(id=conversacion_id, usuario=usuario)
                    except ConversacionBot.DoesNotExist:
                        conversacion = ConversacionBot.objects.create(usuario=usuario)
                else:
                    conversacion = ConversacionBot.objects.create(usuario=usuario)
                
                # Guardar mensaje del usuario
                MensajeBot.objects.create(
                    conversacion=conversacion,
                    rol='user',
                    contenido=mensaje[:500]
                )
                
                # Guardar respuesta del bot (desde cache)
                mensaje_bot = MensajeBot.objects.create(
                    conversacion=conversacion,
                    rol='assistant',
                    contenido=cached_response['respuesta']
                )
                
                return {
                    'success': True,
                    'respuesta': cached_response['respuesta'],
                    'conversacion_id': conversacion.id,
                    'mensaje_id': mensaje_bot.id,
                    'from_cache': True,
                    'error': None
                }
            except Exception as e:
                logger.error(f"Error guardando mensaje en cache: {e}")
                # Si falla guardar, continuar con flujo normal
        
        try:
            # Importar modelos aquí para evitar circular imports
            from .models import ConversacionBot, MensajeBot
            
            # Obtener o crear conversación
            if conversacion_id:
                try:
                    conversacion = ConversacionBot.objects.get(id=conversacion_id, usuario=usuario)
                except ConversacionBot.DoesNotExist:
                    conversacion = ConversacionBot.objects.create(usuario=usuario)
            else:
                conversacion = ConversacionBot.objects.create(usuario=usuario)
            
            # Guardar mensaje del usuario
            mensaje_usuario = MensajeBot.objects.create(
                conversacion=conversacion,
                rol='user',
                contenido=mensaje[:500]  # Limitar a 500 caracteres
            )
            
            # Obtener historial de últimos 10 mensajes para contexto
            mensajes_previos = MensajeBot.objects.filter(
                conversacion=conversacion
            ).order_by('-timestamp')[:10]
            
            # Construir lista de mensajes para la API (orden cronológico)
            messages = [{"role": "system", "content": self.get_system_prompt(usuario)}]
            
            # Agregar mensajes previos en orden cronológico
            for msg in reversed(mensajes_previos):
                if msg.id != mensaje_usuario.id:  # No incluir el mensaje actual aún
                    messages.append({
                        "role": msg.rol,
                        "content": msg.contenido
                    })
            
            # Agregar mensaje actual
            messages.append({"role": "user", "content": mensaje})
            
            # Llamar a la API
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=500
                )
                
                respuesta_texto = response.choices[0].message.content
                
            except Exception as api_error:
                logger.error(f"Error en API principal: {api_error}")
                
                # Intentar fallback si está disponible
                if self.fallback_client:
                    logger.info("Intentando con fallback (Groq)...")
                    response = self.fallback_client.chat.completions.create(
                        model=self.fallback_model,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=500
                    )
                    respuesta_texto = response.choices[0].message.content
                else:
                    raise api_error
            
            # Guardar respuesta del bot
            mensaje_bot = MensajeBot.objects.create(
                conversacion=conversacion,
                rol='assistant',
                contenido=respuesta_texto
            )
            
            # Actualizar timestamp de conversación
            conversacion.save()
            
            # Guardar en cache (TTL de 15 minutos)
            cache.set(cache_key, {
                'respuesta': respuesta_texto,
                'timestamp': timezone.now().isoformat()
            }, 900)  # 15 minutos
            
            return {
                'success': True,
                'respuesta': respuesta_texto,
                'conversacion_id': conversacion.id,
                'mensaje_id': mensaje_bot.id,
                'from_cache': False,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Error en bot de presentaciones: {e}")
            return {
                'success': False,
                'error': f'Error al procesar tu mensaje: {str(e)}',
                'respuesta': None,
                'conversacion_id': conversacion_id
            }
