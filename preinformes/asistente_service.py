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
import unicodedata

logger = logging.getLogger(__name__)


def _strip_html(html_content: str) -> str:
    """Remueve tags HTML y entidades básicas, retorna texto plano."""
    if not html_content:
        return ''
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _normalizar_para_busqueda(texto: str) -> str:
    texto = str(texto or '').lower()
    return ''.join(
        char
        for char in unicodedata.normalize('NFD', texto)
        if unicodedata.category(char) != 'Mn'
    )


def _es_recomendacion_demografica(texto: str) -> bool:
    texto_normalizado = _normalizar_para_busqueda(texto)
    return any(
        termino in texto_normalizado
        for termino in ['edad', 'sexo', 'genero', 'demografic']
    )


def _es_observacion_clinica_no_evaluable(texto: str) -> bool:
    texto_normalizado = _normalizar_para_busqueda(texto)
    return any(
        termino in texto_normalizado
        for termino in [
            'contexto clinico',
            'datos clinicos',
            'informacion clinica',
            'antecedentes clinicos',
        ]
    )


def limpiar_resumen_pre_revision(resumen):
    """
    Normaliza el resumen IA y quita sugerencias que pidan incluir datos
    demograficos en el cuerpo del informe.
    """
    if not isinstance(resumen, dict):
        return {}

    def _limpiar_lista(items, limite):
        elementos = []
        for item in items or []:
            texto = str(item).strip()
            if not texto or _es_recomendacion_demografica(texto):
                continue
            elementos.append(texto[:220])
            if len(elementos) >= limite:
                break
        return elementos

    prioridad = resumen.get('prioridad')
    return {
        'resumen': str(resumen.get('resumen') or '').strip()[:700],
        'puntos_clave': _limpiar_lista(resumen.get('puntos_clave'), 4),
        'posibles_fricciones': _limpiar_lista(resumen.get('posibles_fricciones'), 3),
        'prioridad': prioridad if prioridad in ['baja', 'media', 'alta'] else 'media',
    }


VERSION_RUBRICA_EVALUACION_FINAL = 2


def normalizar_evaluacion_ia_final(
    evaluacion,
    *,
    puntuacion_staff=None,
    aceptado_sin_cambios=False,
):
    if not isinstance(evaluacion, dict):
        return {}

    dimensiones_validas = [
        'interpretacion_diagnostica',
        'priorizacion_clinica',
        'redaccion_radiologica',
        'estructura_informe',
        'precision_terminologica',
        'autonomia',
    ]
    tipos_correccion = [
        'redaccion',
        'interpretacion',
        'omision',
        'jerarquizacion',
        'estructura',
        'terminologia',
        'minima',
    ]

    def _puntaje(valor, default=6):
        try:
            numero = int(round(float(valor)))
        except (TypeError, ValueError):
            numero = default
        return max(1, min(10, numero))

    def _texto(valor, limite):
        return str(valor or '').strip()[:limite]

    def _texto_evaluable(valor, limite):
        texto = str(valor or '').strip()
        fragmentos = re.split(r'(?<=[.!?])\s+', texto)
        texto_limpio = ' '.join(
            fragmento
            for fragmento in fragmentos
            if fragmento and not _es_observacion_clinica_no_evaluable(fragmento)
        )
        return texto_limpio[:limite]

    def _lista(valor, limite, largo_item=220, filtrar_no_evaluable=False):
        salida = []
        for item in valor or []:
            texto = _texto(item, largo_item)
            if texto and not (
                filtrar_no_evaluable
                and _es_observacion_clinica_no_evaluable(texto)
            ):
                salida.append(texto)
            if len(salida) >= limite:
                break
        return salida

    dimensiones = evaluacion.get('dimensiones') or {}
    dimensiones_normalizadas = {}
    for clave in dimensiones_validas:
        dato = dimensiones.get(clave) if isinstance(dimensiones, dict) else {}
        if isinstance(dato, dict):
            dimensiones_normalizadas[clave] = {
                'puntaje': _puntaje(dato.get('puntaje')),
                'comentario': _texto_evaluable(dato.get('comentario'), 260),
            }
        else:
            dimensiones_normalizadas[clave] = {
                'puntaje': _puntaje(dato),
                'comentario': '',
            }

    puntaje_global = _puntaje(evaluacion.get('puntaje_global'))
    if puntuacion_staff is not None:
        puntaje_staff = _puntaje(puntuacion_staff)
        puntaje_global = max(puntaje_staff - 1, min(puntaje_staff + 1, puntaje_global))
        criterio_puntaje = 'anclado_nota_staff'
    elif aceptado_sin_cambios:
        puntaje_global = max(8, puntaje_global)
        for dimension in dimensiones_normalizadas.values():
            dimension['puntaje'] = max(8, dimension['puntaje'])
        criterio_puntaje = 'aceptado_sin_cambios'
    else:
        criterio_puntaje = 'magnitud_correcciones_staff'

    confianza = evaluacion.get('confianza_evaluacion')
    if puntuacion_staff is not None:
        confianza = 'alta'
    elif confianza not in ['limitada', 'media', 'alta']:
        confianza = 'media'

    tipo = evaluacion.get('tipo_correccion_predominante')
    return {
        'puntaje_global': puntaje_global,
        'dimensiones': dimensiones_normalizadas,
        'fortalezas': _lista(evaluacion.get('fortalezas'), 3),
        'aspectos_a_mejorar': _lista(
            evaluacion.get('aspectos_a_mejorar'),
            4,
            filtrar_no_evaluable=True,
        ),
        'tipo_correccion_predominante': tipo if tipo in tipos_correccion else 'redaccion',
        'impacto_correccion_staff': _texto_evaluable(
            evaluacion.get('impacto_correccion_staff'),
            360,
        ),
        'uso_mentor': _texto(evaluacion.get('uso_mentor'), 280),
        'devolucion_docente': _texto_evaluable(
            evaluacion.get('devolucion_docente'),
            520,
        ),
        'version_rubrica': VERSION_RUBRICA_EVALUACION_FINAL,
        'criterio_puntaje': criterio_puntaje,
        'confianza_evaluacion': confianza,
        'advertencia': (
            'Evalua la calidad y coherencia del informe escrito y su concordancia '
            'con la revision docente. No evalua las imagenes ni confirma el diagnostico.'
        ),
    }


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
        contexto_clinico = contexto_estudio.get('contexto_clinico', '')
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
            if contexto_clinico and contexto_clinico.strip():
                contexto_limpio = _strip_html(contexto_clinico)
                if len(contexto_limpio) > 1000:
                    contexto_limpio = contexto_limpio[:1000] + '...'
                desc_estudio += f"\nContexto clinico aportado por el residente: \"{contexto_limpio}\". Usalo solo para orientar el razonamiento; no lo trates como texto obligatorio del informe."

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

    def generar_resumen_pre_revision(self, preinforme):
        """
        Genera una guía breve para el staff antes de corregir un preinforme.

        Returns:
            dict: {success, resumen, error}
        """
        if not self.client:
            return {'success': False, 'resumen': {}, 'error': 'Bot no disponible.'}

        try:
            import json as _json

            texto_informe = _strip_html(preinforme.get_informe_html_or_legacy())
            if len(texto_informe) > 3500:
                texto_informe = texto_informe[:3500] + '...'

            sexo = ''
            if preinforme.sexo_paciente:
                sexo = {'M': 'masculino', 'F': 'femenino', 'O': 'otro'}.get(preinforme.sexo_paciente, '')

            prompt = f"""Sos un médico staff de Diagnóstico por Imágenes ayudando a otro staff antes de revisar un preinforme de un residente.

Tu tarea NO es corregir el informe completo ni reemplazar al revisor. Tenés que dar una orientación breve sobre con qué se va a encontrar y qué conviene mirar primero.

Norma del servicio: muchos staff no usan una sección formal titulada "Conclusión". No consideres la ausencia de esa sección como un defecto por sí misma. Evaluá si el informe comunica adecuadamente el cierre diagnóstico, la impresión o la priorización de hallazgos relevantes, aunque estén integrados en el texto. Solo señalá este punto si el informe queda ambiguo, incompleto o clínicamente poco claro.

DATOS DEL ESTUDIO:
- Tipo: {preinforme.tipo_estudio.nombre}
- Región: {preinforme.region.nombre}
- Edad: {preinforme.edad_paciente or 'no informada'}
- Sexo: {sexo or 'no informado'}
- Sistema destino: {preinforme.get_sistema_destino_display()}
- Contexto clinico aportado por el residente: {preinforme.contexto_clinico or 'no informado'}

Edad y sexo son solo contexto clinico para tu analisis. No sugieras que edad, sexo, genero ni otros datos demograficos deban mencionarse en el cuerpo del informe. En este servicio esos datos no se escriben alli; tampoco los marques como omision, friccion o punto de atencion.
Si el sistema destino es NetTerm/NETTER, no marques como error la falta de acentos, signos de apertura ni caracteres especiales: puede ser una adaptacion tecnica deliberada.

PREINFORME DEL RESIDENTE:
\"{texto_informe}\"

Respondé ÚNICAMENTE con JSON válido con esta estructura exacta:
{{
  "resumen": "<1 o 2 frases sobre el contenido general>",
  "puntos_clave": ["<máximo 4 puntos concretos para revisar>"],
  "posibles_fricciones": ["<máximo 3 inconsistencias, omisiones o dudas; si no hay, lista vacía>"],
  "prioridad": "baja|media|alta"
}}

Usá español rioplatense natural, sobrio, clínico y útil para un revisor.
Usá tildes y signos de apertura cuando correspondan. No escribas texto sin acentos.
Evitá datos identificatorios del paciente."""

            messages = [
                {"role": "system", "content": "Sos un asistente clínico para revisión docente. Respondés siempre JSON válido, en español natural y con tildes."},
                {"role": "user", "content": prompt},
            ]

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=500,
                )
                texto_respuesta = response.choices[0].message.content
            except Exception as api_error:
                logger.error(f"Error API resumen pre-revision: {api_error}")
                if self.fallback_client:
                    response = self.fallback_client.chat.completions.create(
                        model=self.fallback_model,
                        messages=messages,
                        temperature=0.2,
                        max_tokens=500,
                    )
                    texto_respuesta = response.choices[0].message.content
                else:
                    raise api_error

            match = re.search(r'\{.*\}', texto_respuesta, re.DOTALL)
            if not match:
                raise ValueError(f"Respuesta no contiene JSON válido: {texto_respuesta[:200]}")

            resumen = _json.loads(match.group())
            resumen_normalizado = limpiar_resumen_pre_revision(resumen)

            if not resumen_normalizado['resumen'] and not resumen_normalizado['puntos_clave']:
                raise ValueError('La IA devolvió un resumen vacío.')

            return {'success': True, 'resumen': resumen_normalizado, 'error': None}

        except Exception as e:
            logger.error(f"Error en generar_resumen_pre_revision({preinforme.pk}): {e}")
            return {'success': False, 'resumen': {}, 'error': str(e)}

    def generar_evaluacion_final_revision(self, revision):
        """
        Genera una evaluacion formativa del trabajo escrito del residente,
        tomando la correccion del staff como referencia docente.

        Returns:
            dict: {success, evaluacion, error}
        """
        if not self.client:
            return {'success': False, 'evaluacion': {}, 'error': 'Bot no disponible.'}

        try:
            import json as _json
            from .models import ConversacionAsistentePreinforme

            preinforme = revision.preinforme
            informe_residente = _strip_html(revision.informe_residente_snapshot or preinforme.get_informe_html_or_legacy())
            informe_final = _strip_html(revision.informe_final_html or '')
            comentarios_staff = _strip_html(revision.comentarios_generales or '')
            contexto_clinico = _strip_html(preinforme.contexto_clinico or '')
            aceptado_sin_cambios = bool(
                informe_residente
                and informe_final
                and _normalizar_para_busqueda(informe_residente)
                == _normalizar_para_busqueda(informe_final)
            )

            for nombre, valor in [
                ('informe_residente', informe_residente),
                ('informe_final', informe_final),
                ('comentarios_staff', comentarios_staff),
                ('contexto_clinico', contexto_clinico),
            ]:
                if len(valor) > 3500:
                    if nombre == 'informe_residente':
                        informe_residente = valor[:3500] + '...'
                    elif nombre == 'informe_final':
                        informe_final = valor[:3500] + '...'
                    elif nombre == 'comentarios_staff':
                        comentarios_staff = valor[:1800] + '...'
                    elif nombre == 'contexto_clinico':
                        contexto_clinico = valor[:1000] + '...'

            conversaciones = ConversacionAsistentePreinforme.objects.filter(
                preinforme=preinforme,
                usuario=preinforme.residente,
            ).prefetch_related('mensajes_asistente').order_by('-fecha_actualizacion')[:3]

            resumen_mentor = []
            for conversacion in conversaciones:
                evaluacion = conversacion.evaluacion_ia or {}
                partes = []
                if conversacion.puntuacion_global is not None:
                    partes.append(f"puntaje mentor {conversacion.puntuacion_global}/10")
                if evaluacion:
                    partes.append(f"evaluacion mentor: {evaluacion}")
                mensajes = list(conversacion.mensajes_asistente.order_by('timestamp')[:8])
                if mensajes:
                    texto_mensajes = ' | '.join(
                        f"{m.rol}: {_strip_html(m.contenido)[:180]}"
                        for m in mensajes
                    )
                    partes.append(f"fragmentos: {texto_mensajes}")
                if partes:
                    resumen_mentor.append(' ; '.join(partes)[:1200])

            sexo = ''
            if preinforme.sexo_paciente:
                sexo = {'M': 'masculino', 'F': 'femenino', 'O': 'otro'}.get(preinforme.sexo_paciente, '')

            prompt = f"""Sos un especialista docente senior en Diagnostico por Imagenes. Tenes que generar una evaluacion formativa del preinforme de un residente luego de la correccion final del staff.

La evaluacion debe estimar la calidad profesional del informe escrito: coherencia radiologico-diagnostica interna, calidad descriptiva, jerarquizacion y sintesis, adecuacion al metodo, claridad y autonomia. No reemplaza al docente ni debe ser punitiva.

LIMITACION CENTRAL: no ves las imagenes del estudio y no podes juzgar por cuenta propia si los hallazgos son verdaderos, adecuados, completos o correctamente interpretados. La unica referencia diagnostica disponible es la intervencion del staff: diferencias entre el preinforme original y el informe final, comentarios y puntaje manual.

Reglas importantes:
- Fundamenta cada valoracion en cambios concretos realizados por el staff o en comentarios del staff. Usa expresiones como "el staff conservo", "el staff agrego", "el staff modifico" o "el staff senalo".
- Nunca afirmes "hallazgos adecuados/correctos", "interpretacion correcta", "estudio normal" ni equivalentes como una conclusion propia. Tampoco inventes omisiones que el staff no haya corregido o mencionado.
- Si el staff finalizo sin cambiar el texto y no puso nota, interpretalo como aceptacion docente del preinforme. La referencia es 9/10 y el rango justo es 8 a 10. No bajes dimensiones por falta de acceso a las imagenes: esa limitacion debe expresarse en la confianza, no transformarse en castigo.
- Si el staff puso nota, esa nota es el ancla docente. Tu puntaje global debe quedar como maximo a un punto de distancia, hacia arriba o hacia abajo.
- Si hubo cambios y no hay nota, evalua la magnitud y naturaleza de las correcciones. Los cambios de formato o estilo pesan poco; los cambios descriptivos, de jerarquizacion o de impresion pesan progresivamente mas.
- Evalua si la descripcion permite que otro especialista comprenda que entidad o proceso se esta comunicando y si los descriptores son internamente coherentes con la impresion expresada. Esto es coherencia del texto, no confirmacion de la imagen.
- El puntaje mide calidad del informe escrito, concordancia con la revision y grado de correccion requerido. No mide capacidad para detectar hallazgos en las imagenes.
- Pondera orientativamente: coherencia radiologico-diagnostica 30%, calidad descriptiva 25%, jerarquizacion y sintesis 20%, adecuacion al metodo 15%, claridad profesional 10%.
- Si el sistema destino es NetTerm/NETTER, NO penalices ausencia de acentos, signos de apertura ni caracteres especiales. Puede ser una adaptacion tecnica deliberada.
- Muchos staff no usan seccion formal de Conclusion. No penalices esa ausencia si el cierre diagnostico o la impresion quedan claros en el texto.
- Edad y sexo son contexto clinico, no texto obligatorio del informe. No los marques como omision.
- El contexto clinico es opcional y externo al cuerpo del informe. No penalices que no haya sido aportado, no pidas incluirlo y no reduzcas interpretacion, priorizacion ni autonomia por su ausencia.
- Una conclusion puede sintetizar o reiterar el hallazgo principal. No exijas que agregue informacion nueva si comunica con claridad la impresion diagnostica.
- No propongas agregar descriptores o datos que no esten respaldados por el texto, la correccion del staff o el contexto disponible.
- Considera las correcciones del staff: si el informe final cambia mucho respecto del original, eso debe reflejarse como necesidad de mayor supervision o correccion.
- Si hubo Mentor IA, usalo como contexto secundario: no premies ni castigues por usarlo mucho, evalua si ayudo al razonamiento.

DATOS:
- Tipo: {preinforme.tipo_estudio.nombre}
- Region: {preinforme.region.nombre}
- Sistema destino: {preinforme.get_sistema_destino_display()}
- Edad: {preinforme.edad_paciente or 'no informada'}
- Sexo: {sexo or 'no informado'}
- Contexto clinico: {contexto_clinico or 'no informado'}
- Puntaje manual del staff: {revision.puntuacion or 'no informado'}
- Aceptado sin cambios por el staff: {'si' if aceptado_sin_cambios else 'no'}

PREINFORME ORIGINAL DEL RESIDENTE:
\"{informe_residente}\"

INFORME FINAL CORREGIDO POR STAFF:
\"{informe_final}\"

COMENTARIOS DEL STAFF:
\"{comentarios_staff or 'sin comentarios'}\"

INTERACCION CON MENTOR IA:
\"{chr(10).join(resumen_mentor) if resumen_mentor else 'sin uso registrado'}\"

Responde UNICAMENTE con JSON valido con esta estructura exacta:
{{
  "puntaje_global": <int 1-10>,
  "dimensiones": {{
    "interpretacion_diagnostica": {{"puntaje": <int 1-10>, "comentario": "<breve>"}},
    "priorizacion_clinica": {{"puntaje": <int 1-10>, "comentario": "<breve>"}},
    "redaccion_radiologica": {{"puntaje": <int 1-10>, "comentario": "<breve>"}},
    "estructura_informe": {{"puntaje": <int 1-10>, "comentario": "<breve>"}},
    "precision_terminologica": {{"puntaje": <int 1-10>, "comentario": "<breve>"}},
    "autonomia": {{"puntaje": <int 1-10>, "comentario": "<breve>"}}
  }},
  "fortalezas": ["<maximo 3>"],
  "aspectos_a_mejorar": ["<maximo 4>"],
  "tipo_correccion_predominante": "redaccion|interpretacion|omision|jerarquizacion|estructura|terminologia|minima",
  "impacto_correccion_staff": "<1 o 2 frases sobre cuanto cambio necesito>",
  "uso_mentor": "<si no hubo uso, indicarlo sin penalizar>",
  "devolucion_docente": "<mensaje breve, especifico y formativo para el residente>",
  "confianza_evaluacion": "limitada|media|alta"
}}"""

            messages = [
                {"role": "system", "content": "Sos un evaluador docente de textos radiologicos. No ves imagenes: toda inferencia diagnostica debe apoyarse exclusivamente en la correccion del staff. Respondes siempre JSON valido, sobrio y formativo."},
                {"role": "user", "content": prompt},
            ]

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=1100,
                )
                texto_respuesta = response.choices[0].message.content
            except Exception as api_error:
                logger.error(f"Error API evaluacion final revision: {api_error}")
                if self.fallback_client:
                    response = self.fallback_client.chat.completions.create(
                        model=self.fallback_model,
                        messages=messages,
                        temperature=0.2,
                        max_tokens=1100,
                    )
                    texto_respuesta = response.choices[0].message.content
                else:
                    raise api_error

            match = re.search(r'\{.*\}', texto_respuesta, re.DOTALL)
            if not match:
                raise ValueError(f"Respuesta no contiene JSON valido: {texto_respuesta[:200]}")

            evaluacion = normalizar_evaluacion_ia_final(
                _json.loads(match.group()),
                puntuacion_staff=revision.puntuacion,
                aceptado_sin_cambios=aceptado_sin_cambios,
            )
            if not evaluacion:
                raise ValueError('La IA devolvio una evaluacion vacia.')

            return {'success': True, 'evaluacion': evaluacion, 'error': None}

        except Exception as e:
            logger.error(f"Error en generar_evaluacion_final_revision({revision.pk}): {e}")
            return {'success': False, 'evaluacion': {}, 'error': str(e)}

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
3. Descripción muy redundante: misma estructura o concepto repetido ≥2 veces sin aportar información nueva
4. Contradicción interna clara (ej: describe un órgano como "de tamaño normal" y luego "aumentado de tamaño" sin aclaración)

Si encontrás al menos UN problema real y sustancial:
OBSERVACION: SI
SUGERENCIA: <un mensaje socrático y breve en español argentino con voseo, máximo 1 oración, que invite al residente a revisar orienandolo a qué mirar o qué corregir, sin dar la respuesta directa>

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
                    mensaje_sugerencia = '💡 Noté algo en tu informe que quizás vale la pena revisar. ¿Lo charlamos?'

            return {
                'success': True,
                'tiene_observacion': tiene_observacion,
                'mensaje_sugerencia': mensaje_sugerencia,
            }

        except Exception as e:
            logger.error(f"Error en analizar_borrador: {e}")
            return {'success': False, 'tiene_observacion': False, 'error': str(e)}
