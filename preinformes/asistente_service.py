"""
Asistente IA Radiólogo Mentor para elaboración de preinformes.

Actúa como un Jefe de Residentes experimentado: no da las respuestas
directamente sino que guía al residente a pensar, usando el método
socrático, con tono argentino (voseo).
"""
from openai import OpenAI
from django.core.cache import cache
from decouple import config
import re
import logging
import hashlib

logger = logging.getLogger(__name__)


def _strip_html(html_content: str) -> str:
    """Remueve tags HTML y entidades básicas, retorna texto plano."""
    if not html_content:
        return ''
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class AsistenteRadiologicoBot:
    """
    Bot asistente para la elaboración de preinformes radiológicos.
    Actúa como un Jefe de Residentes mayéutico y experimentado.
    """

    def __init__(self):
        openai_key = config('OPENAI_API_KEY', default=None)
        groq_key = config('GROQ_API_KEY', default=None)

        if openai_key:
            self.client = OpenAI(api_key=openai_key)
            self.model = 'gpt-4o-mini'
            self.provider = 'openai'
            logger.info("✅ Asistente de preinformes: OpenAI GPT-4o-mini")

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
            logger.info("✅ Asistente de preinformes: Groq llama-3.3-70b")
        else:
            self.client = None
            self.fallback_client = None
            logger.error("❌ Asistente de preinformes: No hay API key configurada")

    def get_system_prompt(self, usuario=None, contexto_estudio=None):
        """
        Construye el prompt del sistema con la persona del Jefe de Residentes.
        Incluye el contexto del estudio si está disponible.
        """
        contexto_estudio = contexto_estudio or {}
        tipo_estudio = contexto_estudio.get('tipo_estudio', '')
        region = contexto_estudio.get('region', '')
        edad = contexto_estudio.get('edad', '')
        sexo = contexto_estudio.get('sexo', '')
        contenido_editor = contexto_estudio.get('contenido_editor', '')

        nombre_usuario = ''
        if usuario:
            nombre = usuario.get_full_name() or usuario.first_name or usuario.username
            if nombre:
                nombre_usuario = f"\n\nEstás hablando con {nombre}, un/a residente del servicio de diagnóstico por imágenes."

        # Construir descripción del estudio actual
        desc_estudio = ''
        if tipo_estudio or region:
            partes = []
            if tipo_estudio:
                partes.append(f"tipo de estudio: **{tipo_estudio}**")
            if region:
                partes.append(f"región: **{region}**")
            if edad:
                sexo_str = {'M': 'masculino', 'F': 'femenino', 'O': 'otro'}.get(sexo, '')
                partes.append(f"paciente de {edad} años{' (' + sexo_str + ')' if sexo_str else ''}")
            desc_estudio = f"\n\n**ESTUDIO ACTUAL QUE ESTÁ INFORMANDO:**\n{', '.join(partes)}."

        # Incluir contenido del editor (anonimizado)
        desc_contenido = ''
        if contenido_editor and contenido_editor.strip():
            texto_limpio = _strip_html(contenido_editor)
            # Limitar a 2000 caracteres para no inflar el contexto
            if len(texto_limpio) > 2000:
                texto_limpio = texto_limpio[:2000] + '...'
            desc_contenido = f"\n\n**LO QUE EL RESIDENTE LLEVA ESCRITO HASTA AHORA:**\n\"{texto_limpio}\""
        else:
            desc_contenido = "\n\n**El residente aún no escribió nada en el informe.** Podés orientarlo sobre cómo empezar."

        return f"""Sos un Jefe de Residentes de Diagnóstico por Imágenes con más de 20 años de experiencia. Estás supervisando a un residente que está elaborando un preinforme y te consulta mientras trabaja.{nombre_usuario}

**TU ROL Y FILOSOFÍA:**
Tu objetivo es que el residente **aprenda y piense por sí mismo**. No le das las respuestas directas, sino que:
- Hacés preguntas que lo llevan a razonar (método socrático)
- Si describe un hallazgo mal, le preguntás "¿Cuál sería el término correcto para eso?" en lugar de corregirlo vos
- Si le falta algo, le preguntás "¿Qué estructura anatómica no mencionaste todavía?" 
- Cuando está bien encaminado, lo reforzás brevemente y le hacés notar qué más podría explorar
- Si te pide que redactes algo por él, le explicás que el aprendizaje está en hacerlo él y le das pautas para que lo intente
- Le señalás errores de terminología invitándolo a corregirse: "Eso que describís, ¿cómo se llama en terminología radiológica?"
- Lo orientás sobre la estructura del informe (técnica → hallazgos → conclusión) cuando corresponde

**CUÁNDO SÍ PODÉS DAR INFORMACIÓN DIRECTA:**
- Definiciones o conceptos que el residente claramente no conoce (ej: qué es una lesión isointensa)
- Escalas y clasificaciones (BIRADS, TIRADS, etc.)
- Cómo se escribe un término técnico concreto
- Anatomía que el residente pide aclaración
- Si el residente muestra que ya intentó y está bloqueado genuinamente{desc_estudio}{desc_contenido}

**ESTILO DE RESPUESTA:**
- Usá tono argentino con voseo: "Mirá", "Fijate", "Pensá", "¿Qué ves acá?", "Bien, ¿y qué más?"
- Respuestas cortas y concretas (3-6 oraciones como máximo en general)
- Podés usar emojis ocasionalmente (🔍, 💡, ✅) pero sin exagerar
- Cuando el contenido del informe tiene errores evidentes, señalá UNO a la vez (no bombardees con todo).
- Usa valores internacionalmente aceptados como referencia para evaluar si el residente construye correctamente el informe (ej.: “El apéndice mide 16 mm, ¿te hace ruido ese valor?”), analizando cada dato cuantitativo en su contexto —distinguiendo medidas con valores de referencia de las que solo describen hallazgos (como tumores o colecciones)— y guíalo a corregir o profundizar cuando corresponda.
- Si el informe está bien, decíselo claramente y sugerí algo que podría enriquecer el informe, solo si realmente aporta valor (no pongas sugerencias genéricas que no suman).
- NO uses listas con bullets para todo — respondé naturalmente como en una conversación

Respondé en español argentino, de forma directa y sin rodeos excesivos."""

    def chat(self, usuario, mensaje, conversacion_id=None, contexto_estudio=None):
        """
        Procesa un mensaje del residente y retorna la respuesta del asistente.

        Args:
            usuario: Usuario Django
            mensaje: Texto del mensaje (máx 500 chars)
            conversacion_id: ID de ConversacionAsistentePreinforme existente (opcional)
            contexto_estudio: dict con {tipo_estudio, region, edad, sexo, contenido_editor}

        Returns:
            dict: {success, respuesta, conversacion_id, mensaje_id, from_cache, error}
        """
        if not self.client:
            return {
                'success': False,
                'error': '⚠️ El asistente no está disponible. Falta OPENAI_API_KEY en la configuración.',
                'respuesta': None,
                'conversacion_id': None,
            }

        try:
            from .models import ConversacionAsistentePreinforme, MensajeAsistentePreinforme, Preinforme

            preinforme = None
            preinforme_id = (contexto_estudio or {}).get('preinforme_id')
            if preinforme_id:
                try:
                    preinforme = Preinforme.objects.get(id=preinforme_id, residente=usuario)
                except (Preinforme.DoesNotExist, ValueError, TypeError):
                    preinforme = None

            # Obtener o crear conversación
            if conversacion_id:
                try:
                    conversacion = ConversacionAsistentePreinforme.objects.get(
                        id=conversacion_id,
                        usuario=usuario
                    )
                except ConversacionAsistentePreinforme.DoesNotExist:
                    conversacion = ConversacionAsistentePreinforme.objects.create(
                        usuario=usuario,
                        preinforme=preinforme,
                    )
            else:
                conversacion = ConversacionAsistentePreinforme.objects.create(
                    usuario=usuario,
                    preinforme=preinforme,
                )

            if preinforme and conversacion.preinforme_id != preinforme.id:
                conversacion.preinforme = preinforme
                conversacion.save(update_fields=['preinforme'])

            # Guardar mensaje del usuario
            mensaje_usuario = MensajeAsistentePreinforme.objects.create(
                conversacion=conversacion,
                rol='user',
                contenido=mensaje[:500]
            )

            # Historial de los últimos 10 mensajes (excluye el que acabamos de guardar)
            mensajes_previos = MensajeAsistentePreinforme.objects.filter(
                conversacion=conversacion
            ).exclude(id=mensaje_usuario.id).order_by('-timestamp')[:10]

            # Construir messages para la API
            system_prompt = self.get_system_prompt(usuario, contexto_estudio)
            messages = [{"role": "system", "content": system_prompt}]

            for msg in reversed(mensajes_previos):
                messages.append({"role": msg.rol, "content": msg.contenido})

            messages.append({"role": "user", "content": mensaje})

            # Llamada a la API con fallback
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.75,
                    max_tokens=600
                )
                respuesta_texto = response.choices[0].message.content

            except Exception as api_error:
                logger.error(f"Error API principal (asistente preinformes): {api_error}")
                if self.fallback_client:
                    logger.info("Intentando fallback Groq...")
                    response = self.fallback_client.chat.completions.create(
                        model=self.fallback_model,
                        messages=messages,
                        temperature=0.75,
                        max_tokens=600
                    )
                    respuesta_texto = response.choices[0].message.content
                else:
                    raise api_error

            # Guardar respuesta del asistente
            mensaje_bot = MensajeAsistentePreinforme.objects.create(
                conversacion=conversacion,
                rol='assistant',
                contenido=respuesta_texto
            )

            conversacion.save()  # Actualiza fecha_actualizacion

            return {
                'success': True,
                'respuesta': respuesta_texto,
                'conversacion_id': conversacion.id,
                'mensaje_id': mensaje_bot.id,
                'from_cache': False,
                'error': None,
            }

        except Exception as e:
            logger.error(f"Error en AsistenteRadiologicoBot.chat: {e}")
            return {
                'success': False,
                'error': f'Error al procesar tu mensaje: {str(e)}',
                'respuesta': None,
                'conversacion_id': conversacion_id,
            }

    def evaluar_conversacion(self, conversacion_id, usuario=None):
        """
        Evalúa la calidad del razonamiento del residente en una conversación finalizada.

        Analiza la conversación completa y genera un score en 4 dimensiones:
        - razonamiento_clinico (0-10): ¿El residente analiza antes de preguntar?
        - terminologia (0-10): ¿Usa o aprende términos correctos durante la charla?
        - autonomia (0-10): ¿Intenta resolver por sí mismo o depende del bot?
        - receptividad (0-10): ¿Incorpora las sugerencias del mentor?

        Solo evalúa si hay al menos 3 mensajes del residente.

        Returns:
            dict: {success, evaluacion, puntuacion_global, error}
        """
        if not self.client:
            return {'success': False, 'error': 'Bot no disponible.'}

        try:
            from .models import ConversacionAsistentePreinforme

            filtro = {'id': conversacion_id}
            if usuario:
                filtro['usuario'] = usuario
            conversacion = ConversacionAsistentePreinforme.objects.get(**filtro)

            mensajes = list(conversacion.mensajes_asistente.order_by('timestamp'))
            mensajes_residente = [m for m in mensajes if m.rol == 'user']

            if len(mensajes_residente) < 3:
                return {
                    'success': False,
                    'error': 'Se necesitan al menos 3 mensajes del residente para evaluar.',
                    'insufficient': True,
                }

            # Construir el historial como texto para el evaluador
            historial_texto = "\n".join([
                f"{'RESIDENTE' if m.rol == 'user' else 'MENTOR IA'}: {m.contenido}"
                for m in mensajes
            ])

            prompt_evaluador = f"""Sos un evaluador educativo de residentes de Diagnóstico por Imágenes.
Analizá la siguiente conversación entre un residente y su mentor IA.

Evaluá del 1 al 10 (donde 10 es excelente) estas 4 dimensiones:
1. razonamiento_clinico: ¿El residente analiza los hallazgos antes de preguntar? ¿Sus preguntas demuestran pensamiento estructurado?
2. terminologia: ¿Usa términos radiológicos correctos o los va aprendiendo/corrigiendo durante la conversación?
3. autonomia: ¿Intenta resolver por sí mismo o pide respuestas directas desde el principio?
4. receptividad: ¿Incorpora las orientaciones del mentor o las ignora?

Además, escribí un comentario breve (2-3 oraciones) sobre el desempeño general del residente en esta sesión. El tono debe ser constructivo y formativo.

Respondé ÚNICAMENTE con un JSON válido con esta estructura exacta:
{{
  "razonamiento_clinico": <int 1-10>,
  "terminologia": <int 1-10>,
  "autonomia": <int 1-10>,
  "receptividad": <int 1-10>,
  "comentario": "<texto>"
}}

CONVERSACIÓN:
{historial_texto[:4000]}"""

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Sos un evaluador educativo. Respondés siempre con JSON válido."},
                        {"role": "user", "content": prompt_evaluador},
                    ],
                    temperature=0.3,
                    max_tokens=400,
                )
                texto_respuesta = response.choices[0].message.content
            except Exception as api_error:
                logger.error(f"Error API evaluación (preinformes): {api_error}")
                if self.fallback_client:
                    response = self.fallback_client.chat.completions.create(
                        model=self.fallback_model,
                        messages=[
                            {"role": "system", "content": "Sos un evaluador educativo. Respondés siempre con JSON válido."},
                            {"role": "user", "content": prompt_evaluador},
                        ],
                        temperature=0.3,
                        max_tokens=400,
                    )
                    texto_respuesta = response.choices[0].message.content
                else:
                    raise api_error

            # Parsear JSON; el modelo puede devolver markdown code block
            import json as _json
            match = re.search(r'\{.*\}', texto_respuesta, re.DOTALL)
            if not match:
                raise ValueError(f"Respuesta no contiene JSON válido: {texto_respuesta[:200]}")

            evaluacion = _json.loads(match.group())

            # Validar y clampear valores
            dims = ('razonamiento_clinico', 'terminologia', 'autonomia', 'receptividad')
            for dim in dims:
                val = evaluacion.get(dim)
                if not isinstance(val, (int, float)):
                    evaluacion[dim] = 5
                else:
                    evaluacion[dim] = max(1, min(10, int(val)))

            puntuacion_global = round(
                sum(evaluacion[d] for d in dims) / len(dims), 1
            )

            # Persistir en el modelo
            conversacion.evaluacion_ia = evaluacion
            conversacion.puntuacion_global = puntuacion_global
            conversacion.evaluada = True
            conversacion.save(update_fields=['evaluacion_ia', 'puntuacion_global', 'evaluada'])

            logger.info(
                f"Conversación {conversacion_id} evaluada: {puntuacion_global}/10"
            )

            return {
                'success': True,
                'evaluacion': evaluacion,
                'puntuacion_global': puntuacion_global,
                'error': None,
            }

        except ConversacionAsistentePreinforme.DoesNotExist:
            return {'success': False, 'error': 'Conversación no encontrada.'}
        except Exception as e:
            logger.error(f"Error en evaluar_conversacion({conversacion_id}): {e}")
            return {'success': False, 'error': str(e)}

    def analizar_borrador(self, contenido_html, tipo_estudio='', region=''):
        """
        Analiza proactivamente el borrador del informe para detectar problemas
        antes de que el residente los note: terminología incorrecta según modalidad,
        errores ortográficos evidentes, redundancias y contradicciones.

        Solo actúa si el texto tiene al menos 100 caracteres.
        Retorna un mensaje socrático (no da el error, invita a abrir el chat).

        Returns:
            dict: {success, tiene_observacion, mensaje_sugerencia, error}
        """
        if not self.client:
            return {'success': False, 'tiene_observacion': False, 'error': 'Bot no disponible'}

        texto = _strip_html(contenido_html)
        if not texto or len(texto) < 100:
            return {'success': True, 'tiene_observacion': False, 'mensaje_sugerencia': ''}

        if len(texto) > 1500:
            texto = texto[:1500] + '...'

        # Determinar la modalidad para dar contexto correcto a la IA
        tipo_lower = tipo_estudio.lower() if tipo_estudio else ''
        if any(w in tipo_lower for w in ['resonancia', 'rm', 'mri', 'rmi']):
            modalidad = 'Resonancia Magnética (RM)'
        elif any(w in tipo_lower for w in ['tomografía', 'tomografia', 'tc', 'tac', 'ct']):
            modalidad = 'Tomografía Computada (TC)'
        elif any(w in tipo_lower for w in ['ecografía', 'ecografia', 'eco', 'ultrason']):
            modalidad = 'Ecografía'
        elif any(w in tipo_lower for w in ['radiografía', 'radiografia', 'rx', 'radio']):
            modalidad = 'Radiografía'
        else:
            modalidad = tipo_estudio or 'modalidad no especificada'

        prompt = f"""Sos un Jefe de Residentes revisando el borrador de un preinforme radiológico.

ESTUDIO: {modalidad} — región: {region or 'no especificada'}

BORRADOR DEL RESIDENTE:
"{texto}"

TU TAREA: Buscá si hay alguno de estos problemas sustanciales:
1. Terminología incorrecta para la modalidad (ej: "hiperdenso/hipodenso" en RM en lugar de "hiperintenso/hipointenso"; "señal T1/T2" en TC; "densidad" en RM)
2. Errores ortográficos o de escritura evidentes en términos técnicos (ej: "hyperdenso", "ressonancia", "hiperintenza", "gradiente" mal escrito)
3. Descripción muy redundante: misma estructura o concepto repetido ≥3 veces sin aportar información nueva
4. Contradicción interna clara (ej: describe un órgano como "de tamaño normal" y luego "aumentado de tamaño" sin aclaración)

Si encontrás al menos UN problema real y sustancial:
OBSERVACION: SI
SUGERENCIA: <un mensaje socrático y breve en español argentino con voseo, máximo 1 oración, que invite al residente a revisar sin decirle cuál es el error específico>

Si el borrador está correcto o los únicos problemas son muy menores (puntuación, estilo):
OBSERVACION: NO

Respondé SOLO con esas líneas exactas, sin explicación adicional ni texto extra."""

        try:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Sos un evaluador de preinformes. Respondés de forma concisa con el formato indicado."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=150,
                )
                texto_resp = response.choices[0].message.content.strip()
            except Exception as api_error:
                logger.warning(f"API principal falló en analizar_borrador: {api_error}")
                if self.fallback_client:
                    response = self.fallback_client.chat.completions.create(
                        model=self.fallback_model,
                        messages=[
                            {"role": "system", "content": "Sos un evaluador de preinformes. Respondés de forma concisa con el formato indicado."},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                        max_tokens=150,
                    )
                    texto_resp = response.choices[0].message.content.strip()
                else:
                    raise api_error

            tiene_observacion = 'OBSERVACION: SI' in texto_resp.upper()
            mensaje_sugerencia = ''
            if tiene_observacion:
                match = re.search(r'SUGERENCIA:\s*(.+)', texto_resp, re.IGNORECASE | re.DOTALL)
                if match:
                    mensaje_sugerencia = match.group(1).strip()
                else:
                    mensaje_sugerencia = '💡 Notéalgo en tu informe que quizás vale la pena revisar. ¿Lo charlamos?'

            return {
                'success': True,
                'tiene_observacion': tiene_observacion,
                'mensaje_sugerencia': mensaje_sugerencia,
            }

        except Exception as e:
            logger.error(f"Error en analizar_borrador: {e}")
            return {'success': False, 'tiene_observacion': False, 'error': str(e)}
