"""
Servicios para control_stock:
  - Búsqueda en API externa (UPCItemDB)
  - Análisis de foto de producto con GPT-4o-mini Vision
  - Envío de alertas de stock bajo por email
"""
import json
import logging
import base64

import requests
from decouple import config
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

UPCITEMDB_URL = 'https://api.upcitemdb.com/prod/trial/lookup'
_CACHE_TTL = 60 * 60 * 24  # 24 horas — UPCItemDB trial: 100 req/día


def buscar_en_api_externa(codigo_barras: str) -> dict | None:
    """
    Consulta UPCItemDB con el código de barras.
    Cachea el resultado 24 h para no agotar el límite de la API trial.
    Retorna un dict con {nombre, descripcion, imagen_url} o None si no se encontró.
    """
    cache_key = f'upcitemdb_{codigo_barras}'
    cached = cache.get(cache_key)
    if cached is not None:
        # None almacenado significa "no existe en UPCItemDB" — también es válido cachear
        return cached if cached != '__not_found__' else None

    try:
        response = requests.get(
            UPCITEMDB_URL,
            params={'upc': codigo_barras},
            timeout=5,
            headers={'User-Agent': 'gestion_servicio/1.0'},
        )
        if response.status_code != 200:
            logger.warning(f'UPCItemDB devolvió status {response.status_code} para código {codigo_barras}')
            cache.set(cache_key, '__not_found__', _CACHE_TTL)
            return None

        data = response.json()
        items = data.get('items', [])
        if not items:
            cache.set(cache_key, '__not_found__', _CACHE_TTL)
            return None

        item = items[0]
        resultado = {
            'nombre': item.get('title', ''),
            'descripcion': item.get('description', ''),
            'imagen_url': (item.get('images') or [''])[0],
            'marca': item.get('brand', ''),
        }
        cache.set(cache_key, resultado, _CACHE_TTL)
        return resultado
    except requests.RequestException as exc:
        logger.error(f'Error consultando UPCItemDB: {exc}')
        return None


def analizar_foto_producto(image_base64: str) -> dict:
    """
    Envía una imagen en base64 a GPT-4o-mini Vision para extraer datos del packaging.

    Retorna un dict con los campos detectados:
    {
        'codigo_barras': str | None,
        'nombre': str | None,
        'descripcion': str | None,
        'fecha_vencimiento': str | None,   # formato ISO YYYY-MM-DD si se detecta
        'numero_lote': str | None,
        'categoria_sugerida': str | None,
        'unidad_medida': str | None,
        'error': str | None,               # descripción del error si hubo uno
    }
    """
    resultado_vacio = {
        'codigo_barras': None,
        'nombre': None,
        'descripcion': None,
        'fecha_vencimiento': None,
        'numero_lote': None,
        'categoria_sugerida': None,
        'unidad_medida': None,
        'error': None,
    }

    openai_key = config('OPENAI_API_KEY', default=None)
    if not openai_key:
        resultado_vacio['error'] = 'OPENAI_API_KEY no configurada. Completá los datos manualmente.'
        return resultado_vacio

    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)

        # Asegurar que la cadena base64 no tenga el prefijo de data URI
        if ',' in image_base64:
            image_base64 = image_base64.split(',', 1)[1]

        prompt_sistema = (
            'Eres un asistente de inventario hospitalario. '
            'Analizas imágenes de packaging de insumos médicos y descartables. '
            'Retorna ÚNICAMENTE un objeto JSON válido sin texto adicional.'
        )
        prompt_usuario = (
            'Analiza esta imagen de un producto médico o insumo hospitalario. '
            'Extrae toda la información visible del packaging y devuelve SOLO este JSON:\n'
            '{\n'
            '  "codigo_barras": "string o null",\n'
            '  "nombre": "nombre del producto o null",\n'
            '  "descripcion": "descripcion breve o null",\n'
            '  "fecha_vencimiento": "YYYY-MM-DD o null",\n'
            '  "numero_lote": "numero de lote o null",\n'
            '  "categoria_sugerida": "una de: descartable, medicamento, material_procedimiento, material_limpieza, instrumental, equipo_menor, otro",\n'
            '  "unidad_medida": "una de: unidad, caja, frasco, ampolla, bolsa, rollo, par, litro, ml, gramo, otro"\n'
            '}\n'
            'Si un campo no es visible o legible, usa null. '
            'Para fecha_vencimiento: si ves "VENC", "VTO", "Expiry", "EXP", convierte al formato YYYY-MM-DD. '
            'Si solo ves mes/año como "03/27" o "03/2027", usa el último día del mes.'
        )

        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': prompt_sistema},
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': prompt_usuario},
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:image/jpeg;base64,{image_base64}',
                                'detail': 'high',
                            },
                        },
                    ],
                },
            ],
            max_tokens=400,
            temperature=0.1,
        )

        raw = response.choices[0].message.content.strip()
        # Limpiar bloques de código markdown si los hay
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1] if '\n' in raw else raw
            raw = raw.rsplit('```', 1)[0].strip()

        datos = json.loads(raw)
        resultado_vacio.update({k: datos.get(k) for k in resultado_vacio if k != 'error'})
        return resultado_vacio

    except json.JSONDecodeError as exc:
        logger.error(f'GPT no devolvió JSON válido: {exc}')
        resultado_vacio['error'] = 'No se pudo interpretar la respuesta de la IA. Completá los datos manualmente.'
        return resultado_vacio
    except Exception as exc:
        logger.error(f'Error en analizar_foto_producto: {exc}')
        resultado_vacio['error'] = 'Error al analizar la imagen. Completá los datos manualmente.'
        return resultado_vacio


def enviar_alerta_stock_bajo(stock_por_area) -> bool:
    """
    Envía un email al responsable del área cuando el stock baja del mínimo.
    Retorna True si se envió correctamente.
    """
    area = stock_por_area.area
    producto = stock_por_area.producto

    if not area.responsable or not area.responsable.email:
        logger.warning(
            f'Stock bajo en {area.nombre} / {producto.nombre}: '
            'sin responsable o email configurado, no se envía alerta.'
        )
        return False

    asunto = f'⚠️ Stock bajo: {producto.nombre} en {area.nombre}'
    mensaje = (
        f'Hola {area.responsable.get_full_name() or area.responsable.username},\n\n'
        f'El stock de "{producto.nombre}" en el área "{area.nombre}" '
        f'está por debajo del mínimo configurado.\n\n'
        f'  • Cantidad actual: {stock_por_area.cantidad} {producto.get_unidad_medida_display()}\n'
        f'  • Stock mínimo: {producto.stock_minimo} {producto.get_unidad_medida_display()}\n\n'
        f'Por favor, gestioná la reposición a la brevedad.\n\n'
        f'— Sistema de Gestión de Stock'
    )

    try:
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[area.responsable.email],
            fail_silently=False,
        )
        logger.info(f'Alerta stock bajo enviada a {area.responsable.email} para {producto.nombre}')
        return True
    except Exception as exc:
        logger.error(f'Error enviando alerta stock bajo: {exc}')
        return False
