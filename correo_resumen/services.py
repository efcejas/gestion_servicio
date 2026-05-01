import email
import imaplib
import re
import unicodedata
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime, parseaddr

from django.conf import settings
from django.utils import timezone

from dictado_informes.ai_services import AIService

from .exceptions import ConfiguracionCorreoError, ConexionCorreoError, ResumenIAError
from .models import CorreoResumen, CorreoSincronizacion, CorreoHilo


KEYWORD_CATEGORIAS = {
    'AUDITORIA': ['auditoria', 'auditoría', 'calidad', 'hallazgo'],
    'SOPORTE': ['soporte', 'ticket', 'sistema', 'caido', 'caído', 'error'],
    'OPERATIVO': ['guardia', 'equipo', 'tomografo', 'tomógrafo', 'resonador', 'internacion'],
    'RRHH': ['rrhh', 'recursos humanos', 'licencia', 'legajo'],
    'DIRECCION': ['direccion', 'dirección', 'gerencia', 'jefatura'],
}


def _split_csv(raw_value):
    return [item.strip().lower() for item in raw_value.split(',') if item.strip()]


def get_correo_resumen_config():
    return getattr(settings, 'CORREO_RESUMEN_CONFIG', {})


def _normalizar_asunto(asunto):
    """
    Normaliza asunto de email para agrupación en hilos.
    "RE: Recorrida de Calidad" → "recorrida de calidad"
    "FW: Auditoría - seguimiento" → "auditoria seguimiento"
    """
    if not asunto:
        return ''
    
    # Remover prefijos comunes
    asunto = re.sub(r'^(re:|fwd:|fw:|re\[|fwd\[)', '', asunto, flags=re.IGNORECASE).strip()
    
    # Convertir a minúscula
    asunto = asunto.lower()
    
    # Remover tildes/acentos
    asunto = ''.join(
        c for c in unicodedata.normalize('NFD', asunto)
        if unicodedata.category(c) != 'Mn'
    )
    
    # Remover caracteres especiales pero mantener espacios
    asunto = re.sub(r'[^a-z0-9\s-]', '', asunto)
    
    # Remover espacios múltiples y espacios al inicio/final
    asunto = ' '.join(asunto.split())
    
    return asunto[:200]  # Limitar longitud


def _agrupar_correos_en_hilos(config):
    """
    Agrupa CorreoResumen en CorreoHilo basado en asunto normalizado.
    Ventana temporal: 3 días (configurable).
    
    Lógica:
    1. Para cada CorreoResumen sin hilo asignado
    2. Normalizar asunto
    3. Buscar CorreoHilo existente con mismo asunto
    4. Si existe Y último email < 3 días: agregar a hilo
    5. Si no: crear hilo nuevo
    6. Actualizar CorreoHilo con stats agregadas
    """
    ventana_dias = int(config.get('THREAD_WINDOW_DAYS', 3))
    cuenta = config.get('IMAP_USERNAME', 'inbox-principal')
    
    correos_sin_hilo = CorreoResumen.objects.filter(hilo__isnull=True).order_by('fecha_email')
    
    for correo in correos_sin_hilo:
        asunto_norm = _normalizar_asunto(correo.asunto)
        if not asunto_norm:
            continue
        
        # Buscar hilo existente dentro de ventana temporal
        fecha_limite = correo.fecha_email - timezone.timedelta(days=ventana_dias)
        
        hilo = CorreoHilo.objects.filter(
            cuenta=cuenta,
            asunto_normalizado=asunto_norm,
            fecha_ultimo_email__gte=fecha_limite
        ).first()
        
        if not hilo:
            # Crear hilo nuevo
            hilo = CorreoHilo.objects.create(
                cuenta=cuenta,
                asunto_normalizado=asunto_norm,
                fecha_primer_email=correo.fecha_email,
                fecha_ultimo_email=correo.fecha_email,
                requiere_respuesta=correo.requiere_respuesta,
                prioridad_hilo=correo.prioridad_sugerida,
                estado_hilo=correo.estado_atencion,
                fecha_compromiso=correo.fecha_compromiso,
            )
        
        # Agregar correo al hilo
        hilo.correos.add(correo)
        
        # Actualizar participantes
        if correo.remitente and correo.remitente not in hilo.participantes:
            hilo.participantes[correo.remitente] = correo.remitente_nombre or correo.remitente
        
        # Actualizar stats del hilo
        correos_hilo = hilo.correos.all()
        hilo.fecha_ultimo_email = correos_hilo.latest('fecha_email').fecha_email
        hilo.fecha_primer_email = correos_hilo.earliest('fecha_email').fecha_email
        hilo.requiere_respuesta = correos_hilo.filter(requiere_respuesta=True).exists()
        hilo.prioridad_hilo = max(
            correos_hilo.values_list('prioridad_sugerida', flat=True),
            key=lambda p: {'URGENTE': 3, 'ALTA': 2, 'NORMAL': 1, 'BAJA': 0}.get(p, 0)
        ) if correos_hilo.exists() else 'NORMAL'
        hilo.fecha_compromiso = correos_hilo.filter(
            fecha_compromiso__isnull=False
        ).earliest('fecha_compromiso').fecha_compromiso if correos_hilo.filter(fecha_compromiso__isnull=False).exists() else None
        hilo.resumen_hilo = _generar_resumen_hilo(hilo)

        # Si el hilo ya tenía resumen IA pero recibió correos nuevos, marcarlo para regenerar
        if hilo.resumen_ia_generado:
            hilo.resumen_ia_generado = False

        # Intentar enriquecer con IA si está habilitado
        config = get_correo_resumen_config()
        if config.get('ENABLE_AI_SUMMARY') and not hilo.resumen_ia_generado:
            try:
                resumen_ia = _generar_resumen_hilo_ia(hilo)
                if resumen_ia:
                    hilo.resumen_hilo = resumen_ia
                    hilo.resumen_ia_generado = True
            except ResumenIAError:
                pass  # fallback: queda el resumen local

        hilo.save()


def _generar_resumen_hilo(hilo):
    """
    Genera un resumen breve de la conversación del hilo.
    Ej: "3 correos: Auditoría sobre recorrida de calidad - requiere respuesta antes del viernes"
    """
    correos = hilo.correos.all().order_by('fecha_email')
    cantidad = correos.count()
    
    # Primer correo (tema)
    primer_correo = correos.first()
    tema = primer_correo.asunto[:50] if primer_correo else hilo.asunto_normalizado[:50]
    
    # Estado de la conversación
    partes = [f'{cantidad} correo{"s" if cantidad != 1 else ""}']
    if hilo.requiere_respuesta:
        partes.append('requiere respuesta')
    if hilo.fecha_seguimiento:
        dias_seguimiento = (hilo.fecha_seguimiento.date() - timezone.now().date()).days
        if dias_seguimiento < 0:
            partes.append('seguimiento vencido')
        elif dias_seguimiento == 0:
            partes.append('seguimiento hoy')
        elif dias_seguimiento == 1:
            partes.append('seguimiento mañana')
    if hilo.fecha_compromiso:
        dias_hasta = (hilo.fecha_compromiso.date() - timezone.now().date()).days
        if dias_hasta == 0:
            partes.append('vence hoy')
        elif dias_hasta == 1:
            partes.append('vence mañana')
        elif dias_hasta < 7:
            partes.append(f'vence en {dias_hasta} días')

    resumen = f"{tema}. {', '.join(partes)}."
    return resumen[:280]


def actualizar_estado_hilo(hilo, nuevo_estado):
    """Actualiza el estado operativo del hilo y de sus correos asociados."""
    estados_validos = {opcion[0] for opcion in CorreoHilo.ESTADOS_ATENCION}
    if nuevo_estado not in estados_validos:
        raise ValueError('Estado de hilo no válido')

    hilo.estado_hilo = nuevo_estado
    hilo.save(update_fields=['estado_hilo', 'actualizado_en'])

    hilo.correos.update(estado_atencion=nuevo_estado)

    return {
        'exito': True,
        'estado_hilo': hilo.estado_hilo,
        'correos_actualizados': hilo.correos.count(),
    }


def actualizar_seguimiento_hilo(hilo, fecha_seguimiento):
    """Programa o limpia una fecha de seguimiento operativa para un hilo."""
    estado_reabierto = False

    hilo.fecha_seguimiento = fecha_seguimiento

    if fecha_seguimiento and hilo.estado_hilo == 'resuelto':
        hilo.estado_hilo = 'pendiente'
        hilo.correos.update(estado_atencion='pendiente')
        estado_reabierto = True

    hilo.resumen_hilo = _generar_resumen_hilo(hilo)
    hilo.save(update_fields=['fecha_seguimiento', 'estado_hilo', 'resumen_hilo', 'actualizado_en'])

    return {
        'exito': True,
        'fecha_seguimiento': hilo.fecha_seguimiento,
        'estado_reabierto': estado_reabierto,
    }


def _decode_header_value(value):
    if not value:
        return ''
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _extract_text_from_message(message):
    text_parts = []
    attachment_count = 0

    if message.is_multipart():
        for part in message.walk():
            content_disposition = (part.get('Content-Disposition') or '').lower()
            content_type = part.get_content_type()
            if 'attachment' in content_disposition:
                attachment_count += 1
                continue
            if content_type == 'text/plain':
                payload = part.get_payload(decode=True) or b''
                charset = part.get_content_charset() or 'utf-8'
                text_parts.append(payload.decode(charset, errors='ignore'))
    else:
        payload = message.get_payload(decode=True) or b''
        charset = message.get_content_charset() or 'utf-8'
        text_parts.append(payload.decode(charset, errors='ignore'))

    body = '\n'.join(part.strip() for part in text_parts if part.strip())
    body = re.sub(r'\s+', ' ', body).strip()
    return body, attachment_count


def _build_snippet(text, max_length=220):
    if not text:
        return ''
    compact = re.sub(r'\s+', ' ', text).strip()
    return compact[:max_length]


def _parse_imap_date(raw_value):
    if not raw_value:
        return timezone.now()
    try:
        parsed = parsedate_to_datetime(raw_value)
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed.astimezone(timezone.get_current_timezone())
    except Exception:
        return timezone.now()


def _clasificar_correo(payload, config):
    remitente = (payload.get('remitente', '') or '').lower()
    asunto = (payload.get('asunto', '') or '').lower()
    snippet = (payload.get('snippet', '') or '').lower()
    texto = f'{asunto} {snippet}'
    remitentes_prioritarios = _split_csv(config.get('PRIORITY_SENDERS', ''))
    keywords_urgentes = _split_csv(config.get('URGENT_KEYWORDS', 'urgente,importante,asap,guardia,auditoria'))
    keywords_accion = _split_csv(config.get('ACTION_KEYWORDS', 'responder,respuesta,coordinar,pendiente,confirmar'))

    score = 10
    categoria = 'OTRO'

    if payload.get('tiene_adjuntos'):
        score += 10
    if not payload.get('leido', False):
        score += 15

    if any(sender in remitente for sender in remitentes_prioritarios):
        score += 30

    for categoria_nombre, palabras in KEYWORD_CATEGORIAS.items():
        if any(palabra in texto for palabra in palabras):
            categoria = categoria_nombre
            score += 15
            break

    urgencia_detectada = any(keyword in texto for keyword in keywords_urgentes)
    requiere_accion = any(keyword in texto for keyword in keywords_accion)

    if urgencia_detectada:
        score += 25
    if requiere_accion:
        score += 15

    if score >= 80:
        prioridad = 'URGENTE'
    elif score >= 60:
        prioridad = 'ALTA'
    elif score >= 35:
        prioridad = 'NORMAL'
    else:
        prioridad = 'BAJA'

    return {
        'score_importancia': min(score, 100),
        'prioridad_sugerida': prioridad,
        'categoria': categoria,
        'requiere_accion': requiere_accion or urgencia_detectada,
    }


def _extraer_fechas_y_acciones(payload):
    """
    Detecta fechas compromisos y si requiere respuesta en el email.
    Retorna:
    {
        'fecha_compromiso': datetime or None,
        'requiere_respuesta': bool,
        'evidencia_fecha': str (snippet del texto donde se detectó)
    }
    """
    asunto = payload.get('asunto', '').lower()
    snippet = payload.get('snippet', '').lower()
    texto_completo = f'{asunto} {snippet}'
    
    # Keywords que indican respuesta esperada (más específicas para evitar false positives)
    keywords_respuesta = [
        r'\bresponde\b', r'\bresponder\b', r'\brespuesta\b', r'\btu aporte\b', r'\btu entrada\b',
        r'\btu opinión\b', r'\bconfirma\b', r'\bconfirmar\b', r'\bconfirmación\b',
        r'\benvía\b', r'\benviar\b', r'\bcompleta\b', r'\bcompletar\b', r'\bcompletá\b',
        r'\bactualiza\b', r'\bactualizar\b',
        r'\brequiere tu\b', r'\bse requiere que\b', r'\bpor favor\s+responde\b', r'\bpor favor\s+completa\b',
        r'\bpor favor\s+envía\b', r'\bpor favor\s+confirma\b', r'\bsolicito tu\b',
        r'\bnecesito que\b', r'\brequerimos que\b', r'\bpedimos\b'
    ]
    
    requiere_respuesta = False
    for patron in keywords_respuesta:
        if re.search(patron, texto_completo):
            requiere_respuesta = True
            break
    
    # Patrones de fechas (simple pero efectivo)
    fecha_compromiso = None
    evidencia_fecha = ''
    
    # Hoy
    if 'vence hoy' in texto_completo or 'para hoy' in texto_completo or 'hasta hoy' in texto_completo:
        fecha_compromiso = timezone.now().replace(hour=23, minute=59, second=59)
        evidencia_fecha = 'Fecha crítica: hoy'
    
    # Mañana
    elif 'vence mañana' in texto_completo or 'para mañana' in texto_completo or 'hasta mañana' in texto_completo:
        fecha_compromiso = (timezone.now() + timezone.timedelta(days=1)).replace(hour=23, minute=59, second=59)
        evidencia_fecha = 'Fecha crítica: mañana'
    
    # Patrones de días (próximo lunes, próximo martes, etc.)
    else:
        dias_nombres = {
            'lunes': 0, 'martes': 1, 'miércoles': 2, 'miércoles': 2, 'jueves': 3,
            'viernes': 4, 'sábado': 5, 'sábado': 5, 'domingo': 6
        }
        
        for nombre, numero in dias_nombres.items():
            if f'próximo {nombre}' in texto_completo or f'próx {nombre}' in texto_completo:
                hoy = timezone.now().date()
                dias_adelante = (numero - hoy.weekday()) % 7
                if dias_adelante == 0:  # Si es el mismo día, se refiere al próximo
                    dias_adelante = 7
                fecha_compromiso = timezone.make_aware(
                    timezone.datetime.combine(
                        hoy + timezone.timedelta(days=dias_adelante),
                        timezone.datetime.max.time()
                    )
                )
                evidencia_fecha = f'Fecha crítica: próximo {nombre}'
                break
        
        # Patrón "para el DD/MM" o "para el DD"
        patron_fecha = r'para el (\d{1,2})[/\-]?(\d{1,2})?'
        match = re.search(patron_fecha, texto_completo)
        if match:
            try:
                dia = int(match.group(1))
                mes = int(match.group(2)) if match.group(2) else timezone.now().month
                anio = timezone.now().year
                fecha_obj = timezone.make_aware(
                    timezone.datetime(anio, mes, dia, 23, 59, 59)
                )
                # Si la fecha calculada ya pasó, asumimos que es el próximo año
                if fecha_obj < timezone.now():
                    fecha_obj = timezone.make_aware(
                        timezone.datetime(anio + 1, mes, dia, 23, 59, 59)
                    )
                fecha_compromiso = fecha_obj
                evidencia_fecha = f'Fecha crítica: {match.group(0)}'
            except (ValueError, timezone.timezone.InvalidTimeError):
                pass
    
    return {
        'fecha_compromiso': fecha_compromiso,
        'requiere_respuesta': requiere_respuesta,
        'evidencia_fecha': evidencia_fecha,
    }


def _generar_resumen_local(payload, clasificacion):
    prioridad_texto = clasificacion['prioridad_sugerida'].lower()
    remitente = payload.get('remitente_nombre') or payload.get('remitente') or 'Remitente sin identificar'
    snippet = payload.get('snippet', '')
    resumen = f'{remitente}: {payload.get("asunto", "Sin asunto")}. Prioridad {prioridad_texto}.'
    if snippet:
        resumen += f' {snippet[:150]}'
    acciones = []
    if clasificacion['requiere_accion']:
        acciones.append('Revisar y definir respuesta')
    if clasificacion['prioridad_sugerida'] == 'URGENTE':
        acciones.append('Atender hoy')
    return resumen[:280], acciones


def _generar_resumen_ia(payload, clasificacion):
    config = get_correo_resumen_config()
    if not config.get('ENABLE_AI_SUMMARY'):
        return _generar_resumen_local(payload, clasificacion)

    ai_service = AIService()
    if not ai_service.llm_enabled:
        return _generar_resumen_local(payload, clasificacion)

    try:
        prompt = (
            'Sos un asistente ejecutivo para un jefe de servicio médico. '
            'Resumí el correo en una línea clara y accionable. '
            'Indicá si requiere acción inmediata y proponé hasta dos acciones concretas. '\
            'Respondé en JSON con claves resumen y acciones.\n\n'
            f'Remitente: {payload.get("remitente", "")}\n'
            f'Asunto: {payload.get("asunto", "")}\n'
            f'Snippet: {payload.get("snippet", "")}\n'
            f'Prioridad calculada: {clasificacion["prioridad_sugerida"]}\n'
            f'Categoría: {clasificacion["categoria"]}'
        )
        response = ai_service.llm_client.chat.completions.create(
            model=ai_service.llm_model,
            messages=[
                {'role': 'system', 'content': 'Respondé solo JSON válido.'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content.strip()
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if not match:
            raise ResumenIAError('Respuesta IA sin JSON interpretable')
        import json
        parsed = json.loads(match.group(0))
        resumen = (parsed.get('resumen') or '').strip()[:280]
        acciones = parsed.get('acciones') or []
        if not isinstance(acciones, list):
            acciones = []
        return resumen or _generar_resumen_local(payload, clasificacion)[0], acciones[:2]
    except Exception as exc:
        raise ResumenIAError(str(exc)) from exc


def _generar_resumen_hilo_ia(hilo):
    """
    Genera el resumen de un hilo usando IA (OpenRouter via AIService).
    Toma los snippets/resúmenes de los últimos correos del hilo y produce
    un texto accionable de una línea que se guarda en hilo.resumen_hilo.

    Retorna el texto generado o None si falla (el llamador decide qué hacer).
    """
    import json

    config = get_correo_resumen_config()
    if not config.get('ENABLE_AI_SUMMARY'):
        return None

    ai_service = AIService()
    if not ai_service.llm_enabled:
        return None

    correos = hilo.correos.order_by('-fecha_email')[:5]
    if not correos.exists():
        return None

    bloques = []
    for c in correos:
        texto = c.resumen_ejecutivo or c.snippet or ''
        if texto:
            bloques.append(f'- [{c.fecha_email.strftime("%d/%m")}] {c.remitente_visible}: {texto[:200]}')

    if not bloques:
        return None

    contexto_correos = '\n'.join(bloques)

    prompt = (
        'Sos un asistente ejecutivo para un jefe de servicio médico de diagnóstico por imágenes. '
        'Te doy el hilo de una conversación de correo institucional. '
        'Escribí UNA sola frase clara y accionable que resuma el estado actual del hilo y lo que requiere atención. '
        'Máximo 200 caracteres. Sin comillas ni prefijos. Solo el texto.\n\n'
        f'Asunto del hilo: {hilo.asunto_normalizado}\n'
        f'Correos recientes:\n{contexto_correos}'
    )

    try:
        response = ai_service.llm_client.chat.completions.create(
            model=ai_service.llm_model,
            messages=[
                {'role': 'system', 'content': 'Respondé solo con el texto del resumen, sin explicaciones ni formato adicional.'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.2,
            max_tokens=80,
        )
        resumen = response.choices[0].message.content.strip().strip('"').strip("'")
        return resumen[:280] if resumen else None
    except Exception as exc:
        raise ResumenIAError(str(exc)) from exc


def _fetch_imap_messages(max_emails=None):
    config = get_correo_resumen_config()
    host = config.get('IMAP_HOST')
    username = config.get('IMAP_USERNAME')
    password = config.get('IMAP_PASSWORD')
    folder = config.get('IMAP_FOLDER', 'INBOX')
    provider = config.get('PROVIDER', 'imap').upper()

    if not host or not username or not password:
        raise ConfiguracionCorreoError('Faltan credenciales IMAP en CORREO_RESUMEN_CONFIG')

    search_criteria = config.get('SEARCH_CRITERIA', 'UNSEEN')
    max_to_fetch = max_emails or config.get('MAX_EMAILS_PER_RUN', 20)

    try:
        client = imaplib.IMAP4_SSL(host, int(config.get('IMAP_PORT', 993)))
        client.login(username, password)

        # Seleccionar carpeta configurada; si falla, intentar INBOX para no cortar el flujo.
        status_select, _ = client.select(folder)
        if status_select != 'OK':
            status_select, _ = client.select('INBOX')
            if status_select != 'OK':
                raise ConexionCorreoError(f'No se pudo seleccionar carpeta IMAP: {folder}')

        criterios = [segment for segment in str(search_criteria).split(' ') if segment]
        if not criterios:
            criterios = ['UNSEEN']

        status, data = client.search(None, *criterios)
        if status != 'OK':
            raise ConexionCorreoError('No se pudo ejecutar búsqueda IMAP')

        message_ids = data[0].split()[-max_to_fetch:]
        messages = []
        for raw_id in reversed(message_ids):
            status, message_data = client.fetch(raw_id, '(RFC822 FLAGS)')
            if status != 'OK' or not message_data:
                continue
            raw_email = None
            for item in message_data:
                if isinstance(item, tuple):
                    raw_email = item[1]
                    break
            if not raw_email:
                continue

            message = email.message_from_bytes(raw_email)
            body, attachment_count = _extract_text_from_message(message)
            remitente_nombre, remitente_email = parseaddr(_decode_header_value(message.get('From', '')))
            asunto = _decode_header_value(message.get('Subject', ''))
            fecha_email = _parse_imap_date(message.get('Date', ''))
            message_id = _decode_header_value(message.get('Message-ID', '')) or raw_id.decode()
            messages.append({
                'cuenta': username,
                'proveedor': provider,
                'remote_uid': raw_id.decode(),
                'message_id': message_id,
                'thread_id': '',
                'remitente': remitente_email,
                'remitente_nombre': remitente_nombre,
                'asunto': asunto or 'Sin asunto',
                'fecha_email': fecha_email,
                'snippet': _build_snippet(body),
                'cuerpo_texto': body,
                'leido': b'\\Seen' in (message_data[0][0] if isinstance(message_data[0], tuple) else b''),
                'tiene_adjuntos': attachment_count > 0,
                'cantidad_adjuntos': attachment_count,
                'datos_raw': {
                    'from': remitente_email,
                    'subject': asunto,
                    'date': fecha_email.isoformat(),
                },
            })
        client.logout()
        return messages
    except CorreoResumenError:
        raise
    except Exception as exc:
        raise ConexionCorreoError(str(exc)) from exc


def sincronizar_correos_resumen(max_emails=None):
    config = get_correo_resumen_config()
    sync = CorreoSincronizacion.objects.create(
        cuenta=config.get('IMAP_USERNAME', 'inbox-principal'),
        proveedor=config.get('PROVIDER', 'IMAP').upper(),
        estado='OK',
    )

    if not config.get('ENABLED'):
        sync.estado = 'SIN_CONFIG'
        sync.mensaje = 'Módulo deshabilitado por configuración'
        sync.finalizado_en = timezone.now()
        sync.save(update_fields=['estado', 'mensaje', 'finalizado_en'])
        return {'exito': False, 'mensaje': sync.mensaje, 'nuevos': 0}

    try:
        provider = config.get('PROVIDER', 'imap').lower()
        if provider == 'gmail':
            from pedidos_estudios.services.gmail_service import GmailService
            gmail_service = GmailService()
            query = config.get('GMAIL_QUERY', 'category:primary newer_than:3d')
            raw_messages = gmail_service.obtener_emails_nuevos(query=query, max_results=max_emails or config.get('MAX_EMAILS_PER_RUN', 20))
            messages = []
            for item in raw_messages:
                remitente_nombre, remitente_email = parseaddr(item.get('remitente', ''))
                body = item.get('cuerpo_texto', '')
                messages.append({
                    'cuenta': config.get('GMAIL_ACCOUNT', 'gmail'),
                    'proveedor': 'GMAIL',
                    'remote_uid': item.get('id', ''),
                    'message_id': item.get('message_id') or item.get('id', ''),
                    'thread_id': item.get('thread_id', ''),
                    'remitente': remitente_email,
                    'remitente_nombre': remitente_nombre,
                    'asunto': item.get('asunto') or 'Sin asunto',
                    'fecha_email': item.get('fecha') or timezone.now(),
                    'snippet': _build_snippet(body),
                    'cuerpo_texto': body,
                    'leido': 'UNREAD' not in item.get('labels', []),
                    'tiene_adjuntos': bool(item.get('adjuntos')),
                    'cantidad_adjuntos': len(item.get('adjuntos', [])),
                    'datos_raw': {'labels': item.get('labels', [])},
                })
        else:
            messages = _fetch_imap_messages(max_emails=max_emails)

        nuevos = 0
        for payload in messages:
            clasificacion = _clasificar_correo(payload, config)
            fechas_acciones = _extraer_fechas_y_acciones(payload)
            resumen_ejecutivo, acciones = _generar_resumen_local(payload, clasificacion)
            try:
                resumen_ejecutivo, acciones = _generar_resumen_ia(payload, clasificacion)
            except ResumenIAError:
                pass

            _, created = CorreoResumen.objects.update_or_create(
                cuenta=payload['cuenta'],
                message_id=payload['message_id'],
                defaults={
                    **payload,
                    **clasificacion,
                    **fechas_acciones,
                    'resumen_ejecutivo': resumen_ejecutivo,
                    'resumen_ia': resumen_ejecutivo,
                    'acciones_sugeridas': acciones,
                },
            )
            if created:
                nuevos += 1

        sync.correos_leidos = len(messages)
        sync.correos_nuevos = nuevos
        sync.mensaje = f'{nuevos} correo(s) nuevos priorizados'
        sync.finalizado_en = timezone.now()
        sync.save(update_fields=['correos_leidos', 'correos_nuevos', 'mensaje', 'finalizado_en'])
        
        # Agrupar correos en hilos (después de guardar todo)
        try:
            _agrupar_correos_en_hilos(config)
        except Exception as e:
            print(f"⚠️ Advertencia en agrupación de hilos: {e}")
        
        return {'exito': True, 'mensaje': sync.mensaje, 'nuevos': nuevos}
    except CorreoResumenError as exc:
        sync.estado = 'ERROR'
        sync.mensaje = str(exc)
        sync.finalizado_en = timezone.now()
        sync.save(update_fields=['estado', 'mensaje', 'finalizado_en'])
        return {'exito': False, 'mensaje': str(exc), 'nuevos': 0}
