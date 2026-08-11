import hashlib
import json
import logging
import re

from decouple import config
from django.core.cache import cache
from openai import OpenAI

from .models import normalizar_texto_busqueda


logger = logging.getLogger(__name__)


class BuscadorCasosIA:
    """Interpreta una consulta clínica; nunca recibe informes ni accede a la base."""

    MODELO = 'gpt-4o-mini'
    CACHE_SECONDS = 24 * 60 * 60

    def __init__(self):
        api_key = config('OPENAI_API_KEY', default=None)
        self.client = OpenAI(api_key=api_key) if api_key else None

    @staticmethod
    def _sanitizar_consulta(consulta):
        consulta = (consulta or '').strip()[:500]
        consulta = re.sub(r'\b\d{7,10}\b', '[documento omitido]', consulta)
        consulta = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[email omitido]', consulta)
        return consulta

    @staticmethod
    def _limpiar_lista(valores, limite=8):
        resultado = []
        vistos = set()
        for valor in valores or []:
            valor = re.sub(r'\s+', ' ', str(valor)).strip()[:120]
            clave = normalizar_texto_busqueda(valor)
            if len(clave) < 3 or clave in vistos:
                continue
            vistos.add(clave)
            resultado.append(valor)
            if len(resultado) >= limite:
                break
        return resultado

    def interpretar(self, consulta):
        consulta_segura = self._sanitizar_consulta(consulta)
        if not consulta_segura:
            return {'success': False, 'error': 'Escribí qué casos necesitás encontrar.'}

        if not self.client:
            return {
                'success': False,
                'error': 'El buscador inteligente no está disponible en este momento.',
                'terminos': [consulta_segura],
            }

        cache_key = 'buscador_casos_ia:' + hashlib.sha256(
            normalizar_texto_busqueda(consulta_segura).encode('utf-8')
        ).hexdigest()
        cached = cache.get(cache_key)
        if cached:
            return cached

        schema = {
            'type': 'json_schema',
            'json_schema': {
                'name': 'interpretacion_busqueda_casos',
                'strict': True,
                'schema': {
                    'type': 'object',
                    'properties': {
                        'consulta_corregida': {'type': 'string'},
                        'terminos': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'minItems': 1,
                            'maxItems': 8,
                        },
                        'tipo_estudio': {'type': 'string'},
                        'region': {'type': 'string'},
                        'explicacion': {'type': 'string'},
                    },
                    'required': [
                        'consulta_corregida', 'terminos', 'tipo_estudio',
                        'region', 'explicacion',
                    ],
                    'additionalProperties': False,
                },
            },
        }
        system_prompt = (
            'Sos un intérprete de búsquedas para un banco de informes radiológicos '
            'definitivos y aprobados. Corregí errores ortográficos y convertí la consulta '
            'en entre 3 y 8 frases clínicas específicas que podrían aparecer literalmente '
            'en un informe. Incluí sinónimos radiológicos razonables, pero no inventes un '
            'diagnóstico más amplio que lo pedido. Extraé tipo de estudio y región anatómica '
            'solo si fueron expresados o son inequívocos; en caso contrario usá cadena vacía. '
            'No incluyas nombres de pacientes, documentos ni datos identificatorios. '
            'La explicación debe ser breve y describir qué se buscará.'
        )

        try:
            response = self.client.chat.completions.create(
                model=self.MODELO,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': consulta_segura},
                ],
                response_format=schema,
                temperature=0.1,
                max_tokens=500,
            )
            data = json.loads(response.choices[0].message.content)
            terminos = self._limpiar_lista(data.get('terminos'))
            if not terminos:
                terminos = [data.get('consulta_corregida') or consulta_segura]
            resultado = {
                'success': True,
                'consulta_corregida': str(data.get('consulta_corregida', ''))[:300],
                'terminos': terminos,
                'tipo_estudio': str(data.get('tipo_estudio', '')).strip()[:80],
                'region': str(data.get('region', '')).strip()[:80],
                'explicacion': str(data.get('explicacion', '')).strip()[:400],
                'modelo': self.MODELO,
            }
            cache.set(cache_key, resultado, self.CACHE_SECONDS)
            return resultado
        except Exception:
            logger.exception('Error interpretando búsqueda inteligente de casos')
            return {
                'success': False,
                'error': 'No se pudo interpretar la consulta con IA. Se buscó el texto escrito.',
                'terminos': [consulta_segura],
            }
