import hashlib
import logging
import math
import re
import struct

from decouple import config
from django.conf import settings
from django.utils import timezone
from openai import OpenAI


logger = logging.getLogger(__name__)


class BusquedaSemanticaInformes:
    """Genera y compara embeddings compactos sin depender de pgvector."""

    def __init__(self):
        api_key = config('OPENAI_API_KEY', default=None)
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.modelo = getattr(
            settings,
            'PREINFORMES_EMBEDDING_MODEL',
            'text-embedding-3-small',
        )
        self.umbral = getattr(settings, 'PREINFORMES_EMBEDDING_UMBRAL', 0.30)
        self.max_resultados = getattr(settings, 'PREINFORMES_EMBEDDING_MAX_RESULTADOS', 50)

    @staticmethod
    def _fuente_hash(texto):
        return hashlib.sha256((texto or '').encode('utf-8')).hexdigest()

    @staticmethod
    def _reemplazar_valor(texto, valor):
        valor = (valor or '').strip()
        if len(valor) < 3:
            return texto
        return re.sub(
            rf'(?<!\w){re.escape(valor)}(?!\w)',
            '[dato omitido]',
            texto,
            flags=re.IGNORECASE,
        )

    def texto_anonimizado(self, revision):
        texto = revision.informe_final_texto or ''
        preinforme = revision.preinforme
        for valor in (
            preinforme.nombre_paciente,
            preinforme.apellido_paciente,
            preinforme.dni_paciente,
            preinforme.numero_estudio,
        ):
            texto = self._reemplazar_valor(texto, valor)
        texto = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[email omitido]', texto)
        texto = re.sub(r'\b\d{7,10}\b', '[documento omitido]', texto)
        texto = re.sub(r'\s+', ' ', texto).strip()[:12000]
        return (
            f'Tipo de estudio: {preinforme.tipo_estudio.nombre}. '
            f'Región: {preinforme.region.nombre}. Informe: {texto}'
        )

    @staticmethod
    def empaquetar(vector):
        if not vector:
            return None
        return struct.pack(f'<{len(vector)}f', *vector)

    @staticmethod
    def desempaquetar(datos):
        if not datos:
            return ()
        datos = bytes(datos)
        cantidad = len(datos) // 4
        if cantidad == 0 or len(datos) % 4:
            return ()
        return struct.unpack(f'<{cantidad}f', datos)

    @staticmethod
    def similitud_coseno(vector_a, vector_b):
        if not vector_a or len(vector_a) != len(vector_b):
            return 0.0
        producto = sum(a * b for a, b in zip(vector_a, vector_b))
        norma_a = math.sqrt(sum(a * a for a in vector_a))
        norma_b = math.sqrt(sum(b * b for b in vector_b))
        if not norma_a or not norma_b:
            return 0.0
        return producto / (norma_a * norma_b)

    def crear_embeddings(self, textos):
        if not self.client:
            raise RuntimeError('Falta OPENAI_API_KEY para generar embeddings.')
        response = self.client.embeddings.create(model=self.modelo, input=textos)
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]

    def indexar_revisiones(self, revisiones, forzar=False):
        revisiones = list(revisiones)
        pendientes = []
        textos = []
        for revision in revisiones:
            fuente_hash = self._fuente_hash(revision.informe_final_texto)
            vigente = (
                revision.embedding_busqueda
                and revision.embedding_modelo == self.modelo
                and revision.embedding_fuente_hash == fuente_hash
            )
            if vigente and not forzar:
                continue
            texto = self.texto_anonimizado(revision)
            if not texto.strip():
                continue
            pendientes.append((revision, fuente_hash))
            textos.append(texto)

        if not pendientes:
            return 0

        vectores = self.crear_embeddings(textos)
        for (revision, fuente_hash), vector in zip(pendientes, vectores):
            revision.embedding_busqueda = self.empaquetar(vector)
            revision.embedding_modelo = self.modelo
            revision.embedding_fuente_hash = fuente_hash
            revision.embedding_actualizado_en = timezone.now()
            revision.save(update_fields=[
                'embedding_busqueda',
                'embedding_modelo',
                'embedding_fuente_hash',
                'embedding_actualizado_en',
            ])
        return len(pendientes)

    def buscar(self, consulta, revisiones):
        if not self.client:
            return {
                'success': False,
                'error': 'La búsqueda semántica no está disponible: falta OPENAI_API_KEY.',
                'resultados': [],
            }
        try:
            vector_consulta = self.crear_embeddings([consulta])[0]
            resultados = []
            indexadas = 0
            for revision in revisiones:
                if revision.embedding_modelo != self.modelo:
                    continue
                vector_informe = self.desempaquetar(revision.embedding_busqueda)
                if not vector_informe:
                    continue
                indexadas += 1
                similitud = self.similitud_coseno(vector_consulta, vector_informe)
                if similitud >= self.umbral:
                    resultados.append({
                        'revision_id': revision.id,
                        'preinforme_id': revision.preinforme_id,
                        'similitud': similitud,
                    })
            resultados.sort(key=lambda item: item['similitud'], reverse=True)
            return {
                'success': True,
                'resultados': resultados[:self.max_resultados],
                'indexadas': indexadas,
                'modelo': self.modelo,
            }
        except Exception:
            logger.exception('Error en búsqueda semántica de informes')
            return {
                'success': False,
                'error': 'No se pudo ejecutar la búsqueda semántica.',
                'resultados': [],
            }
