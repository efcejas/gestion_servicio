from django.shortcuts import render, redirect, get_object_or_404
from django import forms
from django.conf import settings
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from .models import (
    Informe, PlantillaInforme, AudioTranscripcion, TipoEstudio, 
    EstadoInforme, TerminoMedico, CorreccionAprendizaje, MetricaDictado,
    PlantillaEstructurada, FeedbackCalidadDictado, TrazaAgenteDictado,
    EventoAprendizajeDictado, PreferenciaAprendidaDictado,
)
from .learning_services import (
    MIN_CONFIRMACIONES_PLANTILLA,
    MIN_CONFIANZA_PLANTILLA,
    obtener_preferencia_activa_seleccion,
    registrar_evento_aprendizaje,
)
from .forms import TerminoMedicoForm, PlantillaEstructuradaForm, ImportarPlantillaDocxForm
from .ai_services import ai_service
from .template_importer import (
    DocxTemplateImportError,
    extraer_texto_plantilla_archivo,
    importar_plantilla_archivo,
    importar_plantilla_texto,
)
import json
import base64
import logging
import time  # 🚀 FASE 4: Para medir tiempos
import difflib
import re
import unicodedata
import hashlib

logger = logging.getLogger(__name__)


def user_can_access_dictado_module(user):
    return user.is_authenticated and getattr(user, 'puede_acceder_dictado_ia', lambda: False)()


def user_can_access_transcripcion_preinformes(user):
    """Permite transcripción desde preinformes cuando el rollout está habilitado."""
    if not user.is_authenticated:
        return False

    if user_can_access_dictado_module(user):
        return True

    if not getattr(settings, 'PREINFORMES_DICTADO_CURSOR_HABILITADO', False):
        return False

    return getattr(user, 'rol', None) in {
        'medico_residente',
        'medico_staff',
        'jefe_residentes',
        'instructor_residentes',
        'jefe_servicio',
    }


def get_plantillas_estructuradas_visibles(user, solo_activas=False):
    return PlantillaEstructurada.visibles_para_usuario(user, solo_activas=solo_activas)


def _generar_codigo_interno_plantilla():
    codigos = PlantillaEstructurada.objects.values_list('codigo', flat=True)
    max_codigo = 99999
    for codigo in codigos:
        if not str(codigo).isdigit():
            continue
        try:
            max_codigo = max(max_codigo, int(codigo))
        except (TypeError, ValueError):
            continue

    while True:
        max_codigo += 1
        candidato = str(max_codigo)
        if not PlantillaEstructurada.objects.filter(codigo=candidato).exists():
            return candidato


def _normalizar_texto_selector(texto):
    texto = unicodedata.normalize('NFKD', texto or '')
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r'[^a-zA-Z0-9]+', ' ', texto.lower())
    return re.sub(r'\s+', ' ', texto).strip()


def _tokens_selector(texto):
    stopwords = {
        'de', 'del', 'la', 'las', 'el', 'los', 'con', 'sin', 'para', 'por',
        'una', 'uno', 'un', 'y', 'o', 'en', 'se', 'al', 'rm', 'resonancia',
        'magnetica', 'tomografia', 'tc', 'estudio', 'informe',
    }
    return {
        token for token in _normalizar_texto_selector(texto).split()
        if len(token) >= 3 and token not in stopwords
    }


REGION_SELECTOR_KEYWORDS = {
    'RODILLA': {
        'rodilla', 'gonalgia', 'menisco', 'meniscal', 'rotula', 'patelar',
        'cruzado', 'lca', 'lcp',
    },
    'HOMBRO': {
        'hombro', 'manguito', 'supraespinoso', 'infraespinoso', 'subescapular',
        'glenohumeral', 'acromioclavicular',
    },
    'CODO': {'codo', 'epicondilo', 'epitroclea'},
    'MANO': {
        'mano', 'manos', 'dedo', 'dedos', 'pulgar', 'metacarpiano',
        'metacarpianos', 'metacarpofalangica', 'interfalangica', 'falange',
        'falanges', 'risartrosis', 'trapeciometacarpiana',
    },
    'MUNECA': {
        'muneca', 'carpo', 'carpiano', 'carpianos', 'escafoides',
        'semilunar', 'radiocubital', 'radiocarpiana', 'tunel carpiano',
    },
    'TOBILLO': {'tobillo', 'aquiles', 'peroneos', 'retromaleolar'},
    'CADERA': {
        'cadera', 'caderas', 'coxofemoral', 'coxalgia', 'gluteo', 'gluteos',
        'trocanter', 'trocanterica', 'acetabulo', 'acetabular', 'femoral',
        'iliopsoas',
    },
    'CEREBRO': {
        'cerebro', 'encefalo', 'encefalico', 'cefalea', 'convulsion',
        'convulsiones', 'frontal', 'parietal', 'temporal', 'occipital',
    },
    'COLUMNA': {
        'columna', 'lumbar', 'lumbosacra', 'lumbosacro', 'dorsal', 'cervical',
        'vertebral', 'vertebrales', 'discal', 'discales', 'disco', 'protrusion',
        'protrusiones', 'hernia', 'cono', 'medular', 'radicular',
    },
}

REGION_EXPLICIT_KEYWORDS = {
    'RODILLA': {'rodilla', 'rodillas'},
    'HOMBRO': {'hombro', 'hombros'},
    'CODO': {'codo', 'codos'},
    'MANO': {'mano', 'manos'},
    'MUNECA': {'muneca', 'munecas'},
    'TOBILLO': {'tobillo', 'tobillos'},
    'CADERA': {'cadera', 'caderas'},
    'CEREBRO': {'cerebro', 'encefalo', 'craneo'},
    'COLUMNA': {
        'columna', 'lumbar', 'lumbosacra', 'lumbosacro', 'cervical', 'dorsal',
    },
}

MODALIDAD_SELECTOR_KEYWORDS = {
    'RES': {'resonancia', 'rm'},
    'TOM': {'tomografia', 'tomografica', 'tc'},
    'RAD': {'radiografia', 'radiografica', 'rx'},
    'ECO': {'ecografia', 'ecografica', 'eco'},
}


def _regiones_en_texto_selector(texto):
    tokens = set(_normalizar_texto_selector(texto).split())
    return {
        region
        for region, claves in REGION_SELECTOR_KEYWORDS.items()
        if tokens & claves
    }


def _regiones_explicitas_en_texto(texto):
    tokens = set(_normalizar_texto_selector(texto).split())
    return {
        region
        for region, claves in REGION_EXPLICIT_KEYWORDS.items()
        if tokens & claves
    }


def _modalidades_en_texto_selector(texto):
    tokens = set(_normalizar_texto_selector(texto).split())
    return {
        modalidad
        for modalidad, claves in MODALIDAD_SELECTOR_KEYWORDS.items()
        if tokens & claves
    }


def extraer_contexto_clinico_dictado(texto):
    texto_norm = _normalizar_texto_selector(texto)
    tokens = set(texto_norm.split())

    lateralidad = None
    lado_tecnica = None
    if 'bilateral' in tokens or 'ambas' in tokens or 'ambos' in tokens:
        lateralidad = 'BILATERAL'
        lado_tecnica = 'bilateral'
    elif {'derecha', 'derecho'} & tokens:
        lateralidad = 'DERECHA'
        lado_tecnica = 'derecha'
    elif {'izquierda', 'izquierdo'} & tokens:
        lateralidad = 'IZQUIERDA'
        lado_tecnica = 'izquierda'

    regiones_explicitas = _regiones_explicitas_en_texto(texto_norm)
    regiones_detectadas = _regiones_en_texto_selector(texto_norm)
    region = None
    region_fuente = ''
    for nombre in REGION_SELECTOR_KEYWORDS:
        if nombre in regiones_explicitas:
            region = nombre
            region_fuente = 'explicita'
            break
    if not region:
        for nombre in REGION_SELECTOR_KEYWORDS:
            if nombre in regiones_detectadas:
                region = nombre
                region_fuente = 'inferida'
                break

    modalidades = _modalidades_en_texto_selector(texto_norm)
    modalidad = next(
        (nombre for nombre in MODALIDAD_SELECTOR_KEYWORDS if nombre in modalidades),
        None,
    )

    indicaciones = []
    if 'gonalgia' in tokens:
        indicaciones.append('Gonalgia')
    if 'coxalgia' in tokens:
        indicaciones.append('Coxalgia')
    if 'trauma' in tokens or 'traumatismo' in tokens:
        indicaciones.append('Antecedente traumatico')
    if 'dolor' in tokens and not indicaciones:
        indicaciones.append('Dolor')
    if 'cefalea' in tokens:
        indicaciones.append('Cefalea')
    if 'convulsion' in tokens or 'convulsiones' in tokens:
        indicaciones.append('Convulsiones')

    lateralidad_indicacion = None
    for termino in ('gonalgia', 'coxalgia'):
        match = re.search(
            rf'\b{termino}\b(?:\s+de)?\s+(derecha|derecho|izquierda|izquierdo|bilateral)',
            texto_norm,
        )
        if match:
            valor = match.group(1)
            if valor.startswith('derech'):
                lateralidad_indicacion = 'DERECHA'
            elif valor.startswith('izquierd'):
                lateralidad_indicacion = 'IZQUIERDA'
            else:
                lateralidad_indicacion = 'BILATERAL'
            break

    lateralidad_para_indicacion = lateralidad_indicacion or lateralidad
    if indicaciones and indicaciones[0] in {'Gonalgia', 'Coxalgia'} and lateralidad_para_indicacion:
        sufijo = (
            'bilateral'
            if lateralidad_para_indicacion == 'BILATERAL'
            else lateralidad_para_indicacion.lower()
        )
        indicacion_clinica = f"{indicaciones[0]} {sufijo}."
    elif indicaciones:
        indicacion_clinica = f"{indicaciones[0]}."
    else:
        indicacion_clinica = ''

    titulo_lateralidad = ''
    frase_lateralidad = ''
    regiones_bilaterales = {
        'RODILLA': ('AMBAS RODILLAS', 'ambas rodillas'),
        'HOMBRO': ('AMBOS HOMBROS', 'ambos hombros'),
        'CODO': ('AMBOS CODOS', 'ambos codos'),
        'MANO': ('AMBAS MANOS', 'ambas manos'),
        'MUNECA': ('AMBAS MUÑECAS', 'ambas muñecas'),
        'TOBILLO': ('AMBOS TOBILLOS', 'ambos tobillos'),
        'CADERA': ('AMBAS CADERAS', 'ambas caderas'),
    }
    if lateralidad == 'BILATERAL' and region in regiones_bilaterales:
        titulo_lateralidad, frase_lateralidad = regiones_bilaterales[region]
    elif lateralidad in {'DERECHA', 'IZQUIERDA'}:
        titulo_lateralidad = lateralidad
        frase_lateralidad = lateralidad.lower()

    return {
        'lateralidad': lateralidad,
        'lado_tecnica': lado_tecnica,
        'titulo_lateralidad': titulo_lateralidad,
        'frase_lateralidad': frase_lateralidad,
        'region': region,
        'region_fuente': region_fuente,
        'regiones_detectadas': sorted(regiones_detectadas),
        'regiones_explicitas': sorted(regiones_explicitas),
        'conflicto_region': len(regiones_explicitas) > 1,
        'modalidad': modalidad,
        'conflicto_modalidad': len(modalidades) > 1,
        'lateralidad_indicacion': lateralidad_indicacion,
        'indicacion_clinica': indicacion_clinica,
    }


def sugerir_plantilla_para_dictado(texto, usuario=None):
    """
    Selector deterministico para el primer paso del modo agente.
    Devuelve la plantilla visible mas compatible con el dictado.
    """
    texto_norm = _normalizar_texto_selector(texto)
    if not texto_norm:
        return None

    texto_tokens = _tokens_selector(texto)
    contexto_clinico = extraer_contexto_clinico_dictado(texto)
    queryset = PlantillaEstructurada.visibles_para_usuario(usuario, solo_activas=True)
    candidatos = []

    for plantilla in queryset:
        corpus = ' '.join([
            plantilla.codigo,
            plantilla.nombre,
            plantilla.titulo,
            plantilla.seccion_tecnica,
            ' '.join(plantilla.comentarios_base or []),
        ])
        plantilla_norm = _normalizar_texto_selector(corpus)
        plantilla_tokens = _tokens_selector(corpus)
        region = contexto_clinico.get('region')
        regiones_plantilla = _regiones_en_texto_selector(corpus)
        if region and regiones_plantilla and region not in regiones_plantilla:
            continue
        modalidad = contexto_clinico.get('modalidad')
        modalidades_plantilla = _modalidades_en_texto_selector(corpus)
        if modalidad and modalidades_plantilla and modalidad not in modalidades_plantilla:
            continue

        coincidencias = texto_tokens & plantilla_tokens
        score = len(coincidencias) * 3

        nombre_tokens = _tokens_selector(f'{plantilla.nombre} {plantilla.titulo}')
        score += len(texto_tokens & nombre_tokens) * 4

        for token in nombre_tokens:
            if token and token in texto_norm:
                score += 3

        if plantilla.codigo and _normalizar_texto_selector(plantilla.codigo) in texto_norm:
            score += 8

        if region and region.lower() in plantilla_norm:
            score += 25
        if region and region.lower() in _normalizar_texto_selector(plantilla.nombre):
            score += 20
        if region and region in regiones_plantilla:
            score += 30

        if usuario and plantilla.creada_por_id == getattr(usuario, 'id', None):
            score += 40

        if any(token in plantilla_norm for token in texto_tokens):
            score += 1

        if score > 0:
            candidatos.append((score, plantilla))

    candidatos.sort(key=lambda item: (-item[0], item[1].pk))
    if candidatos and candidatos[0][0] >= 5:
        mejor_score, mejor = candidatos[0]
        segundo_score = candidatos[1][0] if len(candidatos) > 1 else 0
        margen = mejor_score - segundo_score
        if margen >= 20:
            confianza_selector = 'alta'
        elif margen >= 8:
            confianza_selector = 'media'
        else:
            confianza_selector = 'baja'
        return {
            'codigo': mejor.codigo,
            'nombre': mejor.nombre,
            'score': mejor_score,
            'margen': margen,
            'confianza_selector': confianza_selector,
            'candidatos': [
                {
                    'codigo': plantilla.codigo,
                    'nombre': plantilla.nombre,
                    'score': score,
                }
                for score, plantilla in candidatos[:5]
            ],
            'contexto_clinico': contexto_clinico,
        }
    return None


SELECTOR_HIBRIDO_STOPWORDS = {
    'a', 'al', 'con', 'de', 'del', 'el', 'en', 'es', 'la', 'las', 'lo',
    'los', 'magnetica', 'paciente', 'presenta', 'que', 'resonancia', 'se',
    'sin', 'un', 'una', 'y',
}


def sugerir_plantilla_hibrida_en_sombra(texto, usuario=None):
    """Rank templates semantically without affecting the active selection."""
    texto_norm = _normalizar_texto_selector(texto)
    if not texto_norm:
        return None

    contexto = extraer_contexto_clinico_dictado(texto)
    region = contexto.get('region')
    modalidad = contexto.get('modalidad')
    texto_tokens = _tokens_selector(texto) - SELECTOR_HIBRIDO_STOPWORDS
    candidatos = []

    for plantilla in PlantillaEstructurada.visibles_para_usuario(usuario, solo_activas=True):
        nombre_titulo = f'{plantilla.nombre} {plantilla.titulo}'
        corpus = ' '.join([
            plantilla.codigo,
            nombre_titulo,
            plantilla.seccion_tecnica,
            ' '.join(plantilla.comentarios_base or []),
            plantilla.guia_estilo or '',
        ])
        regiones_plantilla = _regiones_en_texto_selector(corpus)
        if region and regiones_plantilla and region not in regiones_plantilla:
            continue
        modalidades_plantilla = _modalidades_en_texto_selector(corpus)
        if modalidad and modalidades_plantilla and modalidad not in modalidades_plantilla:
            continue

        nombre_tokens = _tokens_selector(nombre_titulo) - SELECTOR_HIBRIDO_STOPWORDS
        corpus_tokens = _tokens_selector(corpus) - SELECTOR_HIBRIDO_STOPWORDS
        union_nombre = texto_tokens | nombre_tokens
        union_corpus = texto_tokens | corpus_tokens
        similitud_nombre = (
            len(texto_tokens & nombre_tokens) / len(union_nombre)
            if union_nombre else 0.0
        )
        similitud_corpus = (
            len(texto_tokens & corpus_tokens) / len(union_corpus)
            if union_corpus else 0.0
        )
        secuencia = difflib.SequenceMatcher(
            None,
            texto_norm,
            _normalizar_texto_selector(nombre_titulo),
        ).ratio()

        score = similitud_nombre * 25
        score += similitud_corpus * 20
        score += secuencia * 10
        if region and region in regiones_plantilla:
            score += 40
        elif region and not regiones_plantilla:
            score += 5
        if usuario and plantilla.creada_por_id == getattr(usuario, 'id', None):
            score += 5
        if contexto.get('region_fuente') == 'explicita' and region in regiones_plantilla:
            score += 10

        candidatos.append((round(score, 2), plantilla))

    candidatos.sort(key=lambda item: (-item[0], item[1].pk))
    if not candidatos or candidatos[0][0] < 10:
        return None

    mejor_score, mejor = candidatos[0]
    segundo_score = candidatos[1][0] if len(candidatos) > 1 else 0.0
    margen = round(mejor_score - segundo_score, 2)
    if margen >= 15:
        confianza = 'alta'
    elif margen >= 5:
        confianza = 'media'
    else:
        confianza = 'baja'

    return {
        'version': 'hibrido_v1',
        'codigo': mejor.codigo,
        'nombre': mejor.nombre,
        'score': mejor_score,
        'margen': margen,
        'confianza_selector': confianza,
        'candidatos': [
            {'codigo': plantilla.codigo, 'nombre': plantilla.nombre, 'score': score}
            for score, plantilla in candidatos[:5]
        ],
        'contexto_clinico': contexto,
    }


def resolver_seleccion_plantilla_agente(plantilla_legacy, plantilla_hibrida, contexto):
    """Give control to the hybrid selector only inside the safe rollout limits."""
    if not getattr(settings, 'DICTADO_SELECTOR_HIBRIDO_ACTIVO', True):
        return plantilla_legacy, 'legacy'

    contexto = contexto or {}
    sin_conflictos = not (
        contexto.get('conflicto_region') or contexto.get('conflicto_modalidad')
    )
    score_minimo = float(
        getattr(settings, 'DICTADO_SELECTOR_HIBRIDO_SCORE_MINIMO', 45.0)
    )
    hibrido_confiable = bool(
        plantilla_hibrida
        and contexto.get('region')
        and plantilla_hibrida.get('confianza_selector') == 'alta'
        and float(plantilla_hibrida.get('score') or 0) >= score_minimo
        and sin_conflictos
    )
    if hibrido_confiable:
        return plantilla_hibrida, 'hibrido_alta'
    if plantilla_legacy:
        return plantilla_legacy, 'legacy'
    return None, 'fallback'


def construir_candidatos_confirmacion_plantilla(plantilla_legacy, plantilla_hibrida, limite=3):
    """Combina rankings no calibrados usando posicion y consenso, no porcentajes."""
    combinados = {}
    for fuente, resultado in (('hibrido', plantilla_hibrida), ('legacy', plantilla_legacy)):
        if not resultado:
            continue
        candidatos = resultado.get('candidatos') or [{
            'codigo': resultado.get('codigo'),
            'nombre': resultado.get('nombre'),
            'score': resultado.get('score', 0),
        }]
        for posicion, candidato in enumerate(candidatos[:5], 1):
            codigo = str(candidato.get('codigo') or '').strip()
            if not codigo:
                continue
            item = combinados.setdefault(codigo, {
                'codigo': codigo,
                'nombre': candidato.get('nombre') or codigo,
                'fuentes': [],
                'puntaje_ranking': 0.0,
                'posicion_hibrida': 999,
            })
            if fuente not in item['fuentes']:
                item['fuentes'].append(fuente)
                item['puntaje_ranking'] += 1 / posicion
            if fuente == 'hibrido':
                item['posicion_hibrida'] = min(item['posicion_hibrida'], posicion)
            if candidato.get('nombre'):
                item['nombre'] = candidato['nombre']

    ordenados = sorted(
        combinados.values(),
        key=lambda item: (
            -len(item['fuentes']),
            -item['puntaje_ranking'],
            item['posicion_hibrida'],
            item['nombre'],
        ),
    )
    for posicion, item in enumerate(ordenados[:limite], 1):
        item['posicion'] = posicion
        item['recomendada'] = posicion == 1
        item['consenso_selectores'] = len(item['fuentes']) > 1
        item.pop('puntaje_ranking', None)
        item.pop('posicion_hibrida', None)
    return ordenados[:limite]


def priorizar_preferencia_aprendida(candidatos, contexto, usuario, limite=3):
    """Prioriza memoria fuerte solo dentro del flujo humano de confirmacion."""
    contexto = contexto or {}
    preferencia = obtener_preferencia_activa_seleccion(
        usuario=usuario,
        region=contexto.get('region'),
        modalidad=contexto.get('modalidad'),
        lateralidad=contexto.get('lateralidad'),
    )
    if not preferencia:
        return candidatos, ''

    codigo = str(preferencia.valor.get('codigo_plantilla') or '').strip()
    plantilla = PlantillaEstructurada.visibles_para_usuario(
        usuario,
        solo_activas=True,
    ).filter(codigo=codigo).first()
    if not plantilla:
        return candidatos, ''

    candidatos = [dict(candidato) for candidato in (candidatos or [])]
    preferida = next((c for c in candidatos if c.get('codigo') == codigo), None)
    candidatos = [c for c in candidatos if c.get('codigo') != codigo]
    if not preferida:
        preferida = {
            'codigo': codigo,
            'nombre': plantilla.nombre,
            'fuentes': ['memoria_usuario'],
            'consenso_selectores': False,
        }
    preferida['desde_preferencia_aprendida'] = True
    candidatos.insert(0, preferida)
    candidatos = candidatos[:limite]
    for posicion, candidato in enumerate(candidatos, 1):
        candidato['posicion'] = posicion
        candidato['recomendada'] = posicion == 1
    return candidatos, codigo


def debe_confirmar_plantilla_agente(
    plantilla_elegida,
    origen_seleccion,
    plantilla_legacy,
    plantilla_hibrida,
    contexto,
):
    """Solicita decision humana solo cuando la seleccion no es claramente segura."""
    if not getattr(settings, 'DICTADO_SELECTOR_CONFIRMACION_ACTIVA', True):
        return False

    contexto = contexto or {}
    if contexto.get('conflicto_region') or contexto.get('conflicto_modalidad'):
        return True
    if origen_seleccion == 'hibrido_alta':
        return False
    if not plantilla_elegida:
        return True

    confianza_elegida = plantilla_elegida.get('confianza_selector', '')
    if confianza_elegida in {'media', 'baja'}:
        return True

    if plantilla_hibrida and plantilla_legacy:
        desacuerdo = plantilla_hibrida.get('codigo') != plantilla_legacy.get('codigo')
        hibrido_relevante = plantilla_hibrida.get('confianza_selector') in {'alta', 'media'}
        if desacuerdo and hibrido_relevante:
            return True

    return False


def _registrar_traza_agente(
    request, texto, plantilla_sugerida, contexto_clinico, result=None,
    plantilla_sombra=None, plantilla_usada=None, origen_seleccion='',
    duracion_ms=0, error_detalle='',
):
    """Persist agent decisions while avoiding storage of raw clinical text."""
    result = result or {}
    sugerida = plantilla_sugerida or {}
    sombra = plantilla_sombra or {}
    usada = plantilla_usada or sugerida
    plantilla_obj = None
    codigo = usada.get('codigo', '')
    if codigo:
        plantilla_obj = PlantillaEstructurada.visibles_para_usuario(
            request.user,
            solo_activas=True,
        ).filter(codigo=codigo).first()

    try:
        return TrazaAgenteDictado.objects.create(
            usuario=request.user if request.user.is_authenticated else None,
            huella_entrada=hashlib.sha256((texto or '').encode('utf-8')).hexdigest(),
            longitud_entrada=len(texto or ''),
            region_detectada=(contexto_clinico or {}).get('region') or '',
            lateralidad_detectada=(contexto_clinico or {}).get('lateralidad') or '',
            plantilla_seleccionada=plantilla_obj,
            codigo_plantilla=codigo,
            codigo_plantilla_legacy=sugerida.get('codigo', ''),
            origen_seleccion=origen_seleccion,
            conflicto_contexto=bool(
                (contexto_clinico or {}).get('conflicto_region')
                or (contexto_clinico or {}).get('conflicto_modalidad')
            ),
            score_selector=sugerida.get('score', 0),
            margen_selector=sugerida.get('margen', 0),
            confianza_selector=sugerida.get('confianza_selector', ''),
            candidatos=sugerida.get('candidatos', []),
            codigo_plantilla_sombra=sombra.get('codigo', ''),
            score_selector_sombra=sombra.get('score', 0.0),
            margen_selector_sombra=sombra.get('margen', 0.0),
            confianza_selector_sombra=sombra.get('confianza_selector', ''),
            candidatos_sombra=sombra.get('candidatos', []),
            selector_sombra_coincide=bool(
                sugerida.get('codigo')
                and sugerida.get('codigo') == sombra.get('codigo')
            ),
            guardrails_aplicados=result.get('guardrails_aplicados', []),
            confianza_ia=result.get('confianza', 0.0) or 0.0,
            modelo_ia=result.get('model_used', ''),
            requiere_confirmacion=result.get('requiere_confirmacion', False),
            posible_invencion=result.get('posible_invencion', False),
            duracion_ms=max(0, duracion_ms),
            exitosa=not bool(error_detalle),
            error_detalle=(error_detalle or '')[:500],
        )
    except Exception:
        logger.exception('No se pudo registrar la traza del agente')
        return None


def _calcular_metricas_edicion(texto_ia, texto_final):
    """Calcula edición manual aproximada con ratio de similitud de caracteres."""
    texto_ia = (texto_ia or '').strip()
    texto_final = (texto_final or '').strip()

    if not texto_ia and not texto_final:
        return {
            'longitud_texto_ia': 0,
            'longitud_texto_final': 0,
            'caracteres_editados': 0,
            'porcentaje_edicion': 0.0,
            'tuvo_edicion': False,
        }

    ratio = difflib.SequenceMatcher(None, texto_ia, texto_final).ratio()
    base = max(len(texto_ia), len(texto_final), 1)
    caracteres_editados = max(0, int(round((1.0 - ratio) * base)))
    porcentaje_edicion = round((caracteres_editados / base) * 100, 2)

    return {
        'longitud_texto_ia': len(texto_ia),
        'longitud_texto_final': len(texto_final),
        'caracteres_editados': caracteres_editados,
        'porcentaje_edicion': porcentaje_edicion,
        'tuvo_edicion': caracteres_editados > 0,
    }


class SuperuserRequiredMixin(UserPassesTestMixin):
    """Mixin para restringir acceso solo a superusuarios"""
    def test_func(self):
        return self.request.user.is_superuser
    
    def handle_no_permission(self):
        messages.warning(self.request, "⚠️ No tienes permiso para acceder a esta sección.")
        return redirect('home')


class DictadoModuleAccessMixin(UserPassesTestMixin):
    """Acceso restringido al piloto de dictado y superusuarios."""

    def test_func(self):
        return user_can_access_dictado_module(self.request.user)

    def handle_no_permission(self):
        messages.warning(self.request, "⚠️ No tienes permiso para acceder a Dictado IA.")
        return redirect('home')


class DashboardDictadoView(LoginRequiredMixin, SuperuserRequiredMixin, TemplateView):
    """Vista principal del módulo de dictado de informes"""
    template_name = 'dictado_informes/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estadísticas generales
        context['total_informes'] = Informe.objects.count()
        context['informes_pendientes'] = Informe.objects.filter(
            estado__in=[EstadoInforme.BORRADOR, EstadoInforme.EN_REVISION]
        ).count()
        context['informes_finalizados'] = Informe.objects.filter(
            estado=EstadoInforme.FINALIZADO
        ).count()
        context['informes_firmados'] = Informe.objects.filter(
            estado=EstadoInforme.FIRMADO
        ).count()
        
        # Informes recientes
        context['informes_recientes'] = Informe.objects.select_related(
            'medico', 'plantilla_usada'
        ).order_by('-fecha_creacion')[:10]
        
        # Total de plantillas activas
        context['total_plantillas'] = PlantillaInforme.objects.filter(activa=True).count()
        
        # Informes por tipo de estudio
        context['informes_por_tipo'] = Informe.objects.values(
            'tipo_estudio'
        ).annotate(total=Count('id')).order_by('-total')
        
        # Información de API de IA
        context['api_info'] = ai_service.get_api_info()
        
        return context


class DictadoRapidoView(LoginRequiredMixin, DictadoModuleAccessMixin, TemplateView):
    """Vista simplificada para dictado rápido sin guardar - solo dictar, mejorar y copiar"""
    template_name = 'dictado_informes/dictado_rapido_whisper.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plantillas_visibles = list(get_plantillas_estructuradas_visibles(
            self.request.user,
            solo_activas=True,
        ).values(
            'codigo',
            'nombre',
            'creada_por_id',
            'creada_por__username',
            'compartida',
        ).order_by('codigo'))

        plantillas_propias = [
            p for p in plantillas_visibles
            if p['creada_por_id'] == self.request.user.id
        ]
        plantillas_biblioteca = [
            p for p in plantillas_visibles
            if p['creada_por_id'] != self.request.user.id
        ]

        default_codigo = None
        if plantillas_propias:
            default_codigo = plantillas_propias[0]['codigo']
        elif plantillas_biblioteca:
            default_codigo = plantillas_biblioteca[0]['codigo']

        context['plantillas_estructuradas'] = plantillas_visibles
        context['plantillas_propias'] = plantillas_propias
        context['plantillas_biblioteca'] = plantillas_biblioteca
        context['plantillas_default_codigo'] = default_codigo
        context['plantillas_total_visibles'] = len(plantillas_visibles)
        context['dictado_agente_habilitado'] = getattr(settings, 'DICTADO_AGENTE_HABILITADO', True)
        return context


class MemoriaAprendizajeView(LoginRequiredMixin, DictadoModuleAccessMixin, TemplateView):
    """Panel personal, no clinico, para auditar y pausar memoria aprendida."""

    template_name = 'dictado_informes/memoria_aprendizaje.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        preferencias = PreferenciaAprendidaDictado.objects.filter(
            usuario=self.request.user,
        ).order_by('-vigente', '-fecha_modificacion')
        vigentes = list(preferencias.filter(vigente=True))
        context['preferencias_vigentes'] = vigentes
        context['historial_preferencias'] = preferencias.filter(vigente=False)[:20]
        context['total_activas'] = sum(
            1 for preferencia in vigentes
            if preferencia.estado == PreferenciaAprendidaDictado.Estado.ACTIVA
        )
        context['total_candidatas'] = sum(
            1 for preferencia in vigentes
            if preferencia.estado == PreferenciaAprendidaDictado.Estado.CANDIDATA
        )
        context['total_pausadas'] = sum(
            1 for preferencia in vigentes
            if preferencia.estado == PreferenciaAprendidaDictado.Estado.INACTIVA
        )

        categorias = {}
        eventos = EventoAprendizajeDictado.objects.filter(
            usuario=self.request.user,
            tipo_evento=EventoAprendizajeDictado.TipoEvento.APRENDIZAJE_CONFIRMADO,
        ).only('metadatos')[:100]
        for evento in eventos:
            for categoria, cantidad in (evento.metadatos.get('categorias') or {}).items():
                categorias[categoria] = categorias.get(categoria, 0) + int(cantidad or 0)
        context['categorias_evidencia'] = sorted(
            categorias.items(),
            key=lambda item: (-item[1], item[0]),
        )[:10]
        return context


@require_POST
def actualizar_estado_memoria(request, pk):
    """Pausa o restaura una preferencia propia sin eliminar sus versiones."""
    if not user_can_access_dictado_module(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    preferencia = get_object_or_404(
        PreferenciaAprendidaDictado,
        pk=pk,
        usuario=request.user,
        vigente=True,
    )
    accion = str(request.POST.get('accion') or '').strip()
    if accion == 'desactivar':
        preferencia.estado = PreferenciaAprendidaDictado.Estado.INACTIVA
        preferencia.save(update_fields=['estado', 'fecha_modificacion'])
        messages.success(request, 'La preferencia quedó pausada. El historial se conserva.')
    elif accion == 'reactivar':
        puede_reactivar = (
            preferencia.categoria == PreferenciaAprendidaDictado.Categoria.SELECCION_PLANTILLA
            and preferencia.confirmaciones >= MIN_CONFIRMACIONES_PLANTILLA
            and preferencia.confianza >= MIN_CONFIANZA_PLANTILLA
        )
        if not puede_reactivar:
            messages.warning(request, 'La preferencia todavía no reúne evidencia suficiente para activarse.')
        else:
            preferencia.estado = PreferenciaAprendidaDictado.Estado.ACTIVA
            preferencia.save(update_fields=['estado', 'fecha_modificacion'])
            messages.success(request, 'La preferencia volvió a estar activa.')
    else:
        messages.error(request, 'Acción de memoria inválida.')
    return redirect('dictado_informes:memoria_aprendizaje')


class DemoPresentacionIAView(TemplateView):
    """Pantalla de demo para charla clinica (sin logica de negocio)."""
    template_name = 'dictado_informes/demo_presentacion_ia.html'


def demo_segmentos_reales_api(request):
    """Métricas agregadas para incrustar segmentos reales en la demo de presentación."""
    data = {
        'dictado': {
            'informes_total': 0,
            'informes_finalizados': 0,
            'correcciones_aprendizaje': 0,
            'tiempo_promedio_segundos': 0,
        },
        'preinformes': {
            'total': 0,
            'pendiente_revision': 0,
            'finalizado': 0,
            'revisiones': 0,
        },
        'docencia': {
            'clases_activas': 0,
            'conversaciones_bot': 0,
            'mensajes_bot': 0,
        }
    }

    # Segmento real de Dictado IA
    data['dictado']['informes_total'] = Informe.objects.count()
    data['dictado']['informes_finalizados'] = Informe.objects.filter(
        estado=EstadoInforme.FINALIZADO
    ).count()
    data['dictado']['correcciones_aprendizaje'] = CorreccionAprendizaje.objects.count()

    promedio_ms = MetricaDictado.objects.filter(
        tiempo_total_ms__isnull=False
    ).aggregate(promedio=Avg('tiempo_total_ms'))['promedio']
    if promedio_ms:
        data['dictado']['tiempo_promedio_segundos'] = round(float(promedio_ms) / 1000, 1)

    # Segmento real de Preinformes (residencia)
    try:
        from preinformes.models import Preinforme, RevisionPreinforme

        data['preinformes']['total'] = Preinforme.objects.count()
        data['preinformes']['pendiente_revision'] = Preinforme.objects.filter(
            estado='pendiente_revision'
        ).count()
        data['preinformes']['finalizado'] = Preinforme.objects.filter(
            estado='finalizado'
        ).count()
        data['preinformes']['revisiones'] = RevisionPreinforme.objects.count()
    except Exception as exc:
        logger.warning("No se pudieron cargar métricas de preinformes para demo: %s", exc)

    # Segmento real de Docencia
    try:
        from clases_residentes.models import ClaseResidente, ConversacionBot, MensajeBot

        data['docencia']['clases_activas'] = ClaseResidente.objects.filter(activa=True).count()
        data['docencia']['conversaciones_bot'] = ConversacionBot.objects.count()
        data['docencia']['mensajes_bot'] = MensajeBot.objects.count()
    except Exception as exc:
        logger.warning("No se pudieron cargar métricas de docencia para demo: %s", exc)

    return JsonResponse(
        {
            'ok': True,
            'actualizado': timezone.now().strftime('%d/%m/%Y %H:%M'),
            'data': data,
        }
    )


class InformeListView(LoginRequiredMixin, SuperuserRequiredMixin, ListView):
    """Lista de todos los informes"""
    model = Informe
    template_name = 'dictado_informes/informe_list.html'
    context_object_name = 'informes'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('medico', 'medico_firma', 'plantilla_usada')
        
        # Filtros
        tipo_estudio = self.request.GET.get('tipo_estudio')
        estado = self.request.GET.get('estado')
        search = self.request.GET.get('q')
        
        if tipo_estudio:
            queryset = queryset.filter(tipo_estudio=tipo_estudio)
        if estado:
            queryset = queryset.filter(estado=estado)
        if search:
            queryset = queryset.filter(
                Q(nombre__icontains=search) |
                Q(apellido__icontains=search) |
                Q(dni_paciente__icontains=search) |
                Q(numero_estudio__icontains=search)
            )
        
        return queryset.order_by('-fecha_creacion')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_estudio'] = TipoEstudio.choices
        context['estados'] = EstadoInforme.choices
        context['tipo_estudio_seleccionado'] = self.request.GET.get('tipo_estudio', '')
        context['estado_seleccionado'] = self.request.GET.get('estado', '')
        context['search'] = self.request.GET.get('search', '')
        return context


class InformeCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    """Crear un nuevo informe"""
    model = Informe
    template_name = 'dictado_informes/informe_form.html'
    fields = [
        'nombre_paciente', 'apellido_paciente', 'dni_paciente', 'edad_paciente',
        'fecha_nacimiento', 'tipo_estudio', 'numero_estudio', 'fecha_estudio',
        'region_anatomica', 'indicacion_clinica', 'tecnica', 'hallazgos',
        'conclusion', 'estado', 'plantilla_usada', 'notas_privadas'
    ]
    success_url = reverse_lazy('dictado_informes:lista_informes')
    
    def form_valid(self, form):
        form.instance.medico = self.request.user
        messages.success(self.request, "✅ Informe creado exitosamente")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plantillas'] = PlantillaInforme.objects.filter(activa=True)
        context['es_nuevo'] = True
        return context


class InformeUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    """Editar un informe existente"""
    model = Informe
    template_name = 'dictado_informes/informe_form.html'
    fields = [
        'nombre_paciente', 'apellido_paciente', 'dni_paciente', 'edad_paciente',
        'fecha_nacimiento', 'tipo_estudio', 'numero_estudio', 'fecha_estudio',
        'region_anatomica', 'indicacion_clinica', 'tecnica', 'hallazgos',
        'conclusion', 'estado', 'plantilla_usada', 'notas_privadas'
    ]
    success_url = reverse_lazy('dictado_informes:informe_list')
    
    def form_valid(self, form):
        messages.success(self.request, "✅ Informe actualizado exitosamente")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plantillas'] = PlantillaInforme.objects.filter(activa=True)
        context['es_nuevo'] = False
        context['audios'] = self.object.audios.all()
        return context


class InformeDetailView(LoginRequiredMixin, SuperuserRequiredMixin, DetailView):
    """Ver detalle de un informe"""
    model = Informe
    template_name = 'dictado_informes/informe_detail.html'
    context_object_name = 'informe'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['audios'] = self.object.audios.all()
        return context


class InformeDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    """Eliminar un informe"""
    model = Informe
    template_name = 'dictado_informes/informe_confirm_delete.html'
    success_url = reverse_lazy('dictado_informes:informe_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, "🗑️ Informe eliminado exitosamente")
        return super().delete(request, *args, **kwargs)


class PlantillaListView(LoginRequiredMixin, SuperuserRequiredMixin, ListView):
    """Lista de plantillas de informes"""
    model = PlantillaInforme
    template_name = 'dictado_informes/plantilla_list.html'
    context_object_name = 'plantillas'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('creada_por')
        
        tipo_estudio = self.request.GET.get('tipo_estudio')
        if tipo_estudio:
            queryset = queryset.filter(tipo_estudio=tipo_estudio)
        
        activa = self.request.GET.get('activa')
        if activa == 'true':
            queryset = queryset.filter(activa=True)
        elif activa == 'false':
            queryset = queryset.filter(activa=False)
        
        return queryset.order_by('-fecha_creacion')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_estudio'] = TipoEstudio.choices
        context['tipo_seleccionado'] = self.request.GET.get('tipo_estudio', '')
        return context


class PlantillaCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    """Crear una nueva plantilla"""
    model = PlantillaInforme
    template_name = 'dictado_informes/plantilla_form.html'
    fields = ['nombre', 'tipo_estudio', 'contenido', 'variables', 'activa']
    success_url = reverse_lazy('dictado_informes:plantilla_list')
    
    def form_valid(self, form):
        form.instance.creada_por = self.request.user
        messages.success(self.request, "✅ Plantilla creada exitosamente")
        return super().form_valid(form)


class PlantillaUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    """Editar una plantilla existente"""
    model = PlantillaInforme
    template_name = 'dictado_informes/plantilla_form.html'
    fields = ['nombre', 'tipo_estudio', 'contenido', 'variables', 'activa']
    success_url = reverse_lazy('dictado_informes:plantilla_list')
    
    def form_valid(self, form):
        messages.success(self.request, "✅ Plantilla actualizada exitosamente")
        return super().form_valid(form)


# ========================================================================
# VISTAS CRUD PARA PLANTILLAS ESTRUCTURADAS (Guardrails de IA)
# ========================================================================

class PlantillaEstructuradaListView(LoginRequiredMixin, DictadoModuleAccessMixin, ListView):
    """Lista de plantillas estructuradas para guardrails"""
    model = PlantillaEstructurada
    template_name = 'dictado_informes/plantilla_estructurada_list.html'
    context_object_name = 'plantillas'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = get_plantillas_estructuradas_visibles(self.request.user).select_related('creada_por').order_by('codigo')

        scope = self.request.GET.get('scope')
        if scope == 'mias':
            queryset = queryset.filter(creada_por=self.request.user)
        elif scope == 'biblioteca':
            queryset = queryset.filter(compartida=True).exclude(creada_por=self.request.user)
        
        activa = self.request.GET.get('activa')
        if activa == 'true':
            queryset = queryset.filter(activa=True)
        elif activa == 'false':
            queryset = queryset.filter(activa=False)
        
        origen = self.request.GET.get('origen')
        if origen:
            queryset = queryset.filter(origen=origen)

        compartida = self.request.GET.get('compartida')
        if compartida == 'true':
            queryset = queryset.filter(compartida=True)
        elif compartida == 'false':
            queryset = queryset.filter(compartida=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ORIGEN_CHOICES'] = PlantillaEstructurada.ORIGEN_CHOICES
        context['origen_seleccionado'] = self.request.GET.get('origen', '')
        context['compartida_seleccionada'] = self.request.GET.get('compartida', '')
        context['scope_seleccionado'] = self.request.GET.get('scope', '')
        return context


class PlantillaEstructuradaCreateView(LoginRequiredMixin, DictadoModuleAccessMixin, CreateView):
    """Crear una nueva plantilla estructurada"""
    model = PlantillaEstructurada
    form_class = PlantillaEstructuradaForm
    template_name = 'dictado_informes/plantilla_estructurada_form.html'
    success_url = reverse_lazy('dictado_informes:plantilla_estructurada_list')
    
    def form_valid(self, form):
        form.instance.creada_por = self.request.user
        form.instance.origen = 'user'
        estado_comparticion = 'compartida' if form.instance.compartida else 'privada'
        messages.success(self.request, f"✅ Plantilla '{form.instance.nombre}' creada exitosamente como {estado_comparticion}")
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['es_nueva'] = True
        context['titulo'] = 'Crear Nueva Plantilla Estructurada'
        return context


@login_required
def importar_plantilla_docx_view(request):
    """Importa una plantilla desde archivo con preview editable antes de guardar."""
    if not user_can_access_dictado_module(request.user):
        messages.warning(request, "⚠️ No tienes permiso para acceder a Dictado IA.")
        return redirect('home')

    upload_form = ImportarPlantillaDocxForm()
    plantilla_form = None
    preview_generado = False

    if request.method == 'POST' and request.POST.get('accion') == 'preview':
        upload_form = ImportarPlantillaDocxForm(request.POST, request.FILES)
        if upload_form.is_valid():
            archivo = upload_form.cleaned_data['archivo_docx']
            texto_plantilla = upload_form.cleaned_data.get('texto_plantilla') or ''
            estructurar_con_ia = upload_form.cleaned_data.get('estructurar_con_ia')
            try:
                if archivo:
                    texto_fuente = extraer_texto_plantilla_archivo(archivo)
                    data = importar_plantilla_archivo(archivo)
                else:
                    texto_fuente = texto_plantilla
                    data = importar_plantilla_texto(texto_plantilla)
                if estructurar_con_ia:
                    try:
                        data = ai_service.estructurar_plantilla_importada(texto_fuente)
                        messages.success(
                            request,
                            "La IA estructuro la plantilla. Revisa la vista previa antes de guardar."
                        )
                    except Exception as exc:
                        logger.warning("No se pudo estructurar plantilla con IA: %s", exc)
                        messages.warning(
                            request,
                            "No se pudo estructurar con IA; se uso el analisis local como respaldo."
                        )
                codigo = _generar_codigo_interno_plantilla()
                initial = {
                    'codigo': codigo,
                    'nombre': data.get('titulo') or codigo,
                    'titulo': data.get('titulo') or '',
                    'seccion_tecnica': data.get('seccion_tecnica') or '',
                    'comentarios_base_texto': '\n'.join(data.get('comentarios_base') or []),
                    'modo_estructura': PlantillaEstructurada.MODO_ESTRUCTURA_ESTRICTA,
                    'permitir_secciones_nuevas': False,
                    'estructura_documento_texto': json.dumps(
                        data.get('estructura_documento') or {},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    'activa': True,
                    'compartida': getattr(request.user, 'rol', None) != 'piloto_dictado',
                }
                plantilla_form = PlantillaEstructuradaForm(initial=initial, user=request.user)
                plantilla_form.fields['codigo'].widget = forms.HiddenInput()
                plantilla_form.fields['seccion_tecnica'].widget.attrs['placeholder'] = ''
                plantilla_form.fields['comentarios_base_texto'].widget.attrs['placeholder'] = ''
                preview_generado = True
                messages.info(request, "Revisa la vista previa antes de guardar la plantilla.")
            except DocxTemplateImportError as exc:
                upload_form.add_error('archivo_docx', str(exc))

    elif request.method == 'POST' and request.POST.get('accion') == 'guardar':
        plantilla_form = PlantillaEstructuradaForm(request.POST, user=request.user)
        plantilla_form.fields['codigo'].widget = forms.HiddenInput()
        if plantilla_form.is_valid():
            plantilla = plantilla_form.save(commit=False)
            plantilla.creada_por = request.user
            plantilla.origen = 'user'
            plantilla.save()
            messages.success(request, f"✅ Plantilla '{plantilla.nombre}' importada desde Word.")
            return redirect('dictado_informes:plantilla_estructurada_update', pk=plantilla.pk)
        preview_generado = True

    return render(request, 'dictado_informes/importar_plantilla_docx.html', {
        'upload_form': upload_form,
        'plantilla_form': plantilla_form,
        'preview_generado': preview_generado,
    })


class PlantillaEstructuradaUpdateView(LoginRequiredMixin, DictadoModuleAccessMixin, UpdateView):
    """Editar una plantilla estructurada existente"""
    model = PlantillaEstructurada
    form_class = PlantillaEstructuradaForm
    template_name = 'dictado_informes/plantilla_estructurada_form.html'
    success_url = reverse_lazy('dictado_informes:plantilla_estructurada_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"✅ Plantilla '{form.instance.nombre}' actualizada exitosamente")
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_queryset(self):
        if self.request.user.is_superuser:
            return PlantillaEstructurada.objects.all()
        return PlantillaEstructurada.objects.filter(creada_por=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['es_nueva'] = False
        context['titulo'] = f'Editar Plantilla: {self.object.nombre}'
        # Si es legacy, mostrar advertencia
        if self.object.origen == 'legacy':
            context['advertencia_legacy'] = 'Esta plantilla fue migrada desde hardcode. Los cambios afectarán el comportamiento de IA.'
        return context


class PlantillaEstructuradaDeleteView(LoginRequiredMixin, DictadoModuleAccessMixin, DeleteView):
    """Eliminar una plantilla estructurada (soft delete)"""
    model = PlantillaEstructurada
    template_name = 'dictado_informes/plantilla_estructurada_confirm_delete.html'
    success_url = reverse_lazy('dictado_informes:plantilla_estructurada_list')
    
    def delete(self, request, *args, **kwargs):
        plantilla = self.get_object()
        # Soft delete - solo desactivar
        plantilla.activa = False
        plantilla.save()
        messages.success(request, f"🗑️ Plantilla '{plantilla.nombre}' desactivada exitosamente")
        return redirect(self.success_url)

    def get_queryset(self):
        if self.request.user.is_superuser:
            return PlantillaEstructurada.objects.all()
        return PlantillaEstructurada.objects.filter(creada_por=self.request.user)


# Vista AJAX para obtener plantilla por ID
def obtener_plantilla(request, pk):
    """API para obtener contenido de una plantilla"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        plantilla = PlantillaInforme.objects.get(pk=pk, activa=True)
        return JsonResponse({
            'success': True,
            'contenido': plantilla.contenido,
            'variables': plantilla.variables,
            'tipo_estudio': plantilla.tipo_estudio
        })
    except PlantillaInforme.DoesNotExist:
        return JsonResponse({'error': 'Plantilla no encontrada'}, status=404)


# Vista para firmar informe
def firmar_informe(request, pk):
    """Firma un informe"""
    if not request.user.is_superuser:
        messages.error(request, "No tienes permiso para firmar informes")
        return redirect('home')
    
    informe = get_object_or_404(Informe, pk=pk)
    informe.firmar(request.user)
    messages.success(request, f"✅ Informe firmado exitosamente")
    return redirect('dictado_informes:informe_detail', pk=pk)


# ========================================================================
# NOTA: La función procesar_audio_dictado() fue eliminada el 2026-03-08
# Se reemplazó por dos APIs separadas para mejor modularidad:
#   - transcribir_audio_whisper() - Solo transcripción STT
#   - mejorar_texto_ia() - Solo mejora con LLM
# Esto permite usar cada servicio independientemente según necesidad.
# ========================================================================

# API para transcribir audio con Whisper (sin mejora IA)
@require_POST
@require_http_methods(["POST"])
@login_required
def transcribir_audio_whisper(request):
    """
    Transcribe audio usando Whisper API
    Solo transcripción, sin mejora de IA
    🚀 FASE 4: Registra métricas de performance
    
    Seguridad: CSRF protegido, requiere autenticación y superuser
    """
    if not user_can_access_transcripcion_preinformes(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    # 📊 FASE 4: Iniciar medición de tiempo
    tiempo_inicio = time.time()
    metrica = None
    tuvo_error = False
    error_detalle = ""
    
    try:
        data = json.loads(request.body)
        audio_base64 = data.get('audio')
        
        if not audio_base64:
            return JsonResponse({'error': 'No se recibió audio'}, status=400)
        
        logger.info("🎤 Transcribiendo audio con Whisper...")
        
        # Decodificar audio base64
        try:
            audio_data = base64.b64decode(audio_base64.split(',')[1] if ',' in audio_base64 else audio_base64)
            logger.info(f"Audio decodificado: {len(audio_data)} bytes")
        except Exception as e:
            logger.error(f"Error decodificando base64: {str(e)}")
            return JsonResponse({'error': 'Audio inválido'}, status=400)
        
        # Validar tamaño mínimo del audio
        MIN_AUDIO_SIZE = 500  # Mínimo 500 bytes (~0.1 segundos de audio WebM)
        if len(audio_data) < MIN_AUDIO_SIZE:
            logger.warning(f"Audio muy pequeño: {len(audio_data)} bytes (mínimo: {MIN_AUDIO_SIZE})")
            return JsonResponse({
                'success': False,
                'error': f'Audio demasiado corto ({len(audio_data)} bytes). Mantén presionado el botón por más tiempo.'
            }, status=400)
        
        # Crear archivo temporal
        audio_file = ContentFile(audio_data, name='dictado.webm')
        
        # 📊 FASE 4: Medir tiempo de transcripción
        tiempo_transcripcion_inicio = time.time()
        
        # Transcribir con Whisper
        transcripcion_result = ai_service.transcribe_audio(audio_file)
        
        # 📊 FASE 4: Calcular tiempo de transcripción
        tiempo_transcripcion_ms = int((time.time() - tiempo_transcripcion_inicio) * 1000)
        
        if transcripcion_result.get('error'):
            tuvo_error = True
            error_detalle = transcripcion_result['error']
            return JsonResponse({
                'success': False,
                'error': transcripcion_result['error']
            }, status=500)
        
        texto_transcrito = transcripcion_result.get('text', '')
        
        # 🎯 PROCESAMIENTO UNIFICADO: Comandos de voz + diccionario médico en orden correcto
        texto_procesado, correcciones = TerminoMedico.procesar_texto_completo(texto_transcrito)

        if not (texto_procesado or '').strip():
            tuvo_error = True
            error_detalle = 'Whisper no devolvio texto util'
            logger.warning("Transcripcion vacia: Whisper no devolvio texto util")
            return JsonResponse({
                'success': False,
                'error': 'No se detecto texto en el audio. Intenta grabar nuevamente hablando mas cerca del microfono.'
            }, status=400)
        
        if correcciones:
            logger.info(f"✅ Texto procesado: {len(correcciones)} correcciones aplicadas")
            for i, corr in enumerate(correcciones[:5], 1):  # Mostrar max 5 en log
                logger.info(f"   {i}. {corr['de']} → {corr['a']}")
        
        logger.info(f"✅ Transcripción Whisper: {texto_transcrito[:100]}...")
        logger.info(f"✅ Texto procesado final: {texto_procesado[:100]}...")
        
        # 📊 FASE 4: Registrar métrica
        tiempo_total_ms = int((time.time() - tiempo_inicio) * 1000)
        
        metrica = MetricaDictado.objects.create(
            usuario=request.user,
            tiempo_transcripcion_ms=tiempo_transcripcion_ms,
            tiempo_total_ms=tiempo_total_ms,
            transcripcion_from_cache=transcripcion_result.get('from_cache', False),
            duracion_audio_segundos=transcripcion_result.get('duration'),
            tamanio_audio_kb=len(audio_data) // 1024,
            longitud_transcripcion=len(texto_procesado),
            api_transcripcion='whisper',
            tuvo_errores=False
        )
        
        logger.info(f"📊 Métrica registrada: {tiempo_total_ms}ms (transcripción: {tiempo_transcripcion_ms}ms)")
        
        return JsonResponse({
            'success': True,
            'texto_transcrito': texto_procesado,  # Enviar texto YA con comandos procesados
            'texto_original': texto_transcrito,  # Por si se necesita el original
            'correcciones': correcciones,  # 🆕 Incluir correcciones del diccionario médico
            'confianza': transcripcion_result.get('confidence', 0.95),
            'duracion': transcripcion_result.get('duration'),
            'from_cache': transcripcion_result.get('from_cache', False)
        })
    
    except Exception as e:
        tuvo_error = True
        error_detalle = str(e)
        logger.exception(f"Error en transcribir_audio_whisper: {str(e)}")
        
        # 📊 FASE 4: Registrar métrica de error
        try:
            tiempo_total_ms = int((time.time() - tiempo_inicio) * 1000)
            MetricaDictado.objects.create(
                usuario=request.user,
                tiempo_total_ms=tiempo_total_ms,
                tuvo_errores=True,
                error_detalle=error_detalle[:500],  # Limitar longitud
                api_transcripcion='whisper'
            )
        except Exception as metric_error:
            logger.error(f"Error registrando métrica: {metric_error}")
        
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



# API para mejorar texto existente
@require_POST
def mejorar_texto_ia(request):
    """
    Mejora un texto ya escrito usando IA
    Útil para mejorar borradores sin dictado
    Soporta modo plantilla para respetar estructuras predefinidas
    🚀 FASE 4: Registra métricas de performance
    """
    if not user_can_access_dictado_module(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    # 📊 FASE 4: Iniciar medición de tiempo
    tiempo_inicio = time.time()
    tuvo_error = False
    error_detalle = ""
    
    try:
        data = json.loads(request.body)
        # Aceptar tanto 'texto' como 'texto_original' para compatibilidad
        texto = data.get('texto_original') or data.get('texto') or data.get('texto_transcrito', '')
        tipo_estudio = data.get('tipo_estudio', 'OTR')
        modo = data.get('modo', 'LIBRE')
        tipo_plantilla = data.get('tipo_plantilla', 'RODILLA')  # Nuevo campo
        plantilla = data.get('plantilla', None)
        field_name = data.get('field_name', None)
        plantilla_sugerida = None
        plantilla_legacy = None
        plantilla_sombra = None
        origen_seleccion = ''
        preferencia_aprendida_codigo = ''
        
        if not texto or texto.strip() == '':
            logger.warning("⚠️ mejorar_texto_ia: No se recibió texto válido")
            return JsonResponse({'error': 'No se recibió texto para mejorar'}, status=400)
        if modo == 'AGENTE' and not getattr(settings, 'DICTADO_AGENTE_HABILITADO', True):
            logger.warning("Modo AGENTE solicitado pero deshabilitado por settings")
            return JsonResponse({'error': 'Modo agente deshabilitado'}, status=403)
        
        logger.info(f"📝 Mejorando texto ({len(texto)} caracteres) en modo {modo} para campo '{field_name}'")
        
        # Inicializar correcciones como lista vacía
        correcciones = []
        
        # El texto ya viene con diccionario médico aplicado desde la transcripción
        # Si viene de edición manual, aplicar diccionario ahora
        if data.get('from_manual_edit', False):
            texto_procesado, correcciones = TerminoMedico.aplicar_correcciones(texto)
            if correcciones:
                logger.info(f"✅ Diccionario aplicado (edición manual): {len(correcciones)} correcciones")
        else:
            # Ya viene procesado de transcripción
            texto_procesado = texto
        
        if modo == 'AGENTE':
            contexto_seleccion = extraer_contexto_clinico_dictado(texto_procesado)
            codigo_confirmado = str(data.get('plantilla_confirmada_codigo') or '').strip()
            plantilla_legacy = sugerir_plantilla_para_dictado(texto_procesado, request.user)
            calcular_hibrido = (
                getattr(settings, 'DICTADO_SELECTOR_HIBRIDO_SOMBRA', True)
                or getattr(settings, 'DICTADO_SELECTOR_HIBRIDO_ACTIVO', True)
            )
            if calcular_hibrido:
                plantilla_sombra = sugerir_plantilla_hibrida_en_sombra(
                    texto_procesado,
                    request.user,
                )
            plantilla_sugerida, origen_seleccion = resolver_seleccion_plantilla_agente(
                plantilla_legacy,
                plantilla_sombra,
                contexto_seleccion,
            )
            candidatos_confirmacion = construir_candidatos_confirmacion_plantilla(
                plantilla_legacy,
                plantilla_sombra,
            )
            candidatos_confirmacion, preferencia_aprendida_codigo = priorizar_preferencia_aprendida(
                candidatos_confirmacion,
                contexto_seleccion,
                request.user,
            )

            if codigo_confirmado:
                plantilla_confirmada = PlantillaEstructurada.visibles_para_usuario(
                    request.user,
                    solo_activas=True,
                ).filter(codigo=codigo_confirmado).first()
                if not plantilla_confirmada:
                    return JsonResponse(
                        {'error': 'La plantilla seleccionada no esta disponible.'},
                        status=400,
                    )
                plantilla_sugerida = {
                    'codigo': plantilla_confirmada.codigo,
                    'nombre': plantilla_confirmada.nombre,
                    'score': 0,
                    'margen': 0,
                    'confianza_selector': 'confirmada',
                    'candidatos': candidatos_confirmacion,
                    'contexto_clinico': contexto_seleccion,
                }
                origen_seleccion = 'usuario_confirmada'
            elif debe_confirmar_plantilla_agente(
                plantilla_sugerida,
                origen_seleccion,
                plantilla_legacy,
                plantilla_sombra,
                contexto_seleccion,
            ):
                logger.info(
                    'Modo AGENTE: seleccion incierta; se solicita decision del usuario (%s candidatos)',
                    len(candidatos_confirmacion),
                )
                return JsonResponse({
                    'success': True,
                    'requiere_seleccion_plantilla': True,
                    'candidatos_plantilla': candidatos_confirmacion,
                    'confianza_selector': (
                        (plantilla_sugerida or {}).get('confianza_selector') or 'baja'
                    ),
                    'selector_origen': 'pendiente_usuario',
                    'contexto_clinico': contexto_seleccion,
                    'preferencia_aprendida_codigo': preferencia_aprendida_codigo,
                })

            if plantilla_sugerida:
                tipo_plantilla = plantilla_sugerida['codigo']
                logger.info(
                    "Modo AGENTE: plantilla sugerida %s por %s (score %s)",
                    plantilla_sugerida['codigo'],
                    origen_seleccion,
                    plantilla_sugerida['score'],
                )
            else:
                logger.info(
                    "Modo AGENTE: no hubo match claro; se usa plantilla fallback %s",
                    tipo_plantilla,
                )

        modo_procesamiento = 'ESTRUCTURADO' if modo == 'AGENTE' else modo
        contexto_clinico = (
            (plantilla_sugerida or {}).get('contexto_clinico')
            if modo == 'AGENTE'
            else extraer_contexto_clinico_dictado(texto_procesado)
        )

        # Construir contexto con modo y campo especifico
        contexto = {
            'modo': modo_procesamiento,
            'field_name': field_name,
            'contexto_clinico': contexto_clinico,
        }

        # Solo agregar tipo_plantilla si NO es modo FIEL
        if modo_procesamiento != 'FIEL':
            contexto['tipo_plantilla'] = tipo_plantilla
            logger.info(f"Tipo de plantilla: {tipo_plantilla}")
        else:
            logger.info("Modo FIEL - sin plantilla, solo correccion")

        # Solo agregar plantilla si NO es modo FIEL
        if plantilla and modo_procesamiento != 'FIEL':
            contexto['plantilla'] = plantilla
            logger.info(f"Usando plantilla: {plantilla.get('nombre', 'sin nombre')}")

        # FASE 4: Medir tiempo de mejora con IA
        tiempo_mejora_inicio = time.time()
                # 3. MEJORAR CON IA
        result = ai_service.improve_medical_text(
            texto_procesado, 
            tipo_estudio, 
            contexto,
            usuario=request.user if request.user.is_authenticated else None
        )
        
        # 📊 FASE 4: Calcular tiempo de mejora
        tiempo_mejora_ms = int((time.time() - tiempo_mejora_inicio) * 1000)
        tiempo_total_ms = int((time.time() - tiempo_inicio) * 1000)
        
        texto_mejorado = result.get('texto_mejorado', texto_procesado)
        
        logger.info(f"✅ Texto mejorado en modo final: {result.get('modo', modo)}")
        
        # 📊 FASE 4: Registrar métrica
        try:
            MetricaDictado.objects.create(
                usuario=request.user,
                tiempo_mejora_ms=tiempo_mejora_ms,
                tiempo_total_ms=tiempo_total_ms,
                mejora_from_cache=result.get('from_cache', False),
                longitud_transcripcion=len(texto),  # Texto original
                longitud_mejora=len(texto_mejorado),  # Texto mejorado
                api_mejora=result.get('api_used', 'gpt'),
                modo_mejora=modo,
                tipo_estudio=tipo_estudio,
                tuvo_errores=False
            )
            logger.info(f"📊 Métrica registrada: {tiempo_total_ms}ms (mejora: {tiempo_mejora_ms}ms)")
        except Exception as metric_error:
            logger.error(f"Error registrando métrica: {metric_error}")
        
        evento_aprendizaje_id = None
        if modo == 'AGENTE':
            traza_agente = _registrar_traza_agente(
                request=request,
                texto=texto_procesado,
                plantilla_sugerida=plantilla_legacy,
                contexto_clinico=contexto_clinico,
                result=result,
                plantilla_sombra=plantilla_sombra,
                plantilla_usada=plantilla_sugerida,
                origen_seleccion=origen_seleccion,
                duracion_ms=tiempo_total_ms,
            )
            if origen_seleccion == 'usuario_confirmada':
                try:
                    propuesta = (candidatos_confirmacion or [{}])[0].get('codigo', '')
                    evento = registrar_evento_aprendizaje(
                        usuario=request.user,
                        tipo_evento=EventoAprendizajeDictado.TipoEvento.PLANTILLA_CONFIRMADA,
                        modo_dictado='AGENTE',
                        tipo_estudio=tipo_estudio if tipo_estudio in dict(TipoEstudio.choices) else '',
                        region=(contexto_clinico or {}).get('region') or '',
                        modalidad=(contexto_clinico or {}).get('modalidad') or '',
                        lateralidad=(contexto_clinico or {}).get('lateralidad') or '',
                        plantilla_propuesta_codigo=propuesta,
                        plantilla_confirmada_codigo=tipo_plantilla,
                        traza=traza_agente,
                        metadatos={
                            'coincide_propuesta': propuesta == tipo_plantilla,
                            'confianza_selector': (
                                (plantilla_legacy or {}).get('confianza_selector') or ''
                            ),
                        },
                    )
                    evento_aprendizaje_id = evento.pk
                except Exception:
                    logger.exception('No se pudo registrar la confirmacion de plantilla')

        return JsonResponse({
            'success': True,
            'requiere_seleccion_plantilla': False,
            'texto_mejorado': texto_mejorado,
            'confianza': result.get('confianza', 0.0),
            'sugerencias': result.get('sugerencias', []),
            'correcciones_aplicadas': correcciones,  # Enviar correcciones al frontend
            'modo': result.get('modo', modo),  # Retornar modo usado por la IA
            'score_confianza': result.get('score_confianza', 1.0),
            'requiere_confirmacion': result.get('requiere_confirmacion', False),
            'motivo_confianza': result.get('motivo_confianza', ''),
            'guardrails_aplicados': result.get('guardrails_aplicados', []),
            'posible_invencion': result.get('posible_invencion', False),
            'terminos_sospechosos': result.get('terminos_sospechosos', []),
            'plantilla_sugerida': plantilla_sugerida,
            'tipo_plantilla_usada': tipo_plantilla,
            'selector_origen': origen_seleccion,
            'contexto_clinico': contexto_clinico,
            'evento_aprendizaje_id': evento_aprendizaje_id,
            'preferencia_aprendida_codigo': preferencia_aprendida_codigo,
        })
    
    except json.JSONDecodeError as e:
        tuvo_error = True
        error_detalle = f"JSON decode error: {str(e)}"
        logger.error(f"❌ Error decodificando JSON: {str(e)}")
        return JsonResponse({'error': 'Datos inválidos en la solicitud'}, status=400)
    except Exception as e:
        tuvo_error = True
        error_detalle = str(e)
        logger.error(f"❌ Error en mejorar_texto_ia: {str(e)}", exc_info=True)
        
        # 📊 FASE 4: Registrar métrica de error
        try:
            tiempo_total_ms = int((time.time() - tiempo_inicio) * 1000)
            MetricaDictado.objects.create(
                usuario=request.user,
                tiempo_total_ms=tiempo_total_ms,
                tipo_estudio=data.get('tipo_estudio', 'OTR') if 'data' in locals() else 'OTR',
                modo_mejora=data.get('modo', 'LIBRE') if 'data' in locals() else 'LIBRE',
                tuvo_errores=True,
                error_detalle=error_detalle[:500],  # Limitar longitud
                api_mejora='gpt'
            )
        except Exception as metric_error:
            logger.error(f"Error registrando métrica: {metric_error}")
        
        if 'data' in locals() and data.get('modo') == 'AGENTE':
            _registrar_traza_agente(
                request=request,
                texto=locals().get('texto_procesado', locals().get('texto', '')),
                plantilla_sugerida=locals().get('plantilla_legacy'),
                contexto_clinico=locals().get('contexto_clinico', {}),
                plantilla_sombra=locals().get('plantilla_sombra'),
                plantilla_usada=locals().get('plantilla_sugerida'),
                origen_seleccion=locals().get('origen_seleccion', ''),
                duracion_ms=int((time.time() - tiempo_inicio) * 1000),
                error_detalle=error_detalle,
            )

        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def corregir_borrador_ia(request):
    """Aplica una instruccion localizada al informe actual sin regenerar la plantilla."""
    if not user_can_access_dictado_module(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    try:
        data = json.loads(request.body)
        texto_actual = data.get('texto_actual', '')
        instruccion = data.get('instruccion', '')
        fragmento_objetivo = data.get('fragmento_objetivo', '')
        contexto_conversacion = data.get('contexto_conversacion', [])
        if not str(texto_actual).strip():
            return JsonResponse({'error': 'No se recibio el informe actual'}, status=400)
        if not str(instruccion).strip():
            return JsonResponse({'error': 'No se recibio una instruccion de correccion'}, status=400)
        if data.get('confirmar_propuesta'):
            resultado = ai_service.confirmar_edicion_informe(
                texto_actual=texto_actual,
                instruccion=instruccion,
                operaciones=data.get('operaciones_propuestas'),
            )
        else:
            argumentos_edicion = {
                'texto_actual': texto_actual,
                'instruccion': instruccion,
                'fragmento_objetivo': fragmento_objetivo,
            }
            if contexto_conversacion:
                argumentos_edicion['contexto_conversacion'] = contexto_conversacion
            resultado = ai_service.edit_medical_report(**argumentos_edicion)

        requiere_revision = bool(
            resultado.get('requiere_confirmacion')
            or resultado.get('requiere_aclaracion')
        )
        evento_aprendizaje_id = None
        try:
            operaciones = resultado.get('operaciones_aplicadas') or []
            if operaciones and not requiere_revision:
                tipos_operacion = sorted({
                    str(operacion.get('tipo') or '').strip()
                    for operacion in operaciones
                    if isinstance(operacion, dict) and operacion.get('tipo')
                })
                evento = registrar_evento_aprendizaje(
                    usuario=request.user,
                    tipo_evento=EventoAprendizajeDictado.TipoEvento.CORRECCION_VOZ_APLICADA,
                    modo_dictado=str(data.get('modo_dictado') or '')[:20],
                    plantilla_confirmada_codigo=str(data.get('tipo_plantilla') or '')[:50],
                    tipo_operacion=','.join(tipos_operacion)[:50],
                    metadatos={
                        'cantidad_operaciones': len(operaciones),
                        'tipos_operacion': tipos_operacion,
                        'uso_fragmento_objetivo': bool(str(fragmento_objetivo).strip()),
                        'confirmacion_explicita': bool(data.get('confirmar_propuesta')),
                    },
                )
                evento_aprendizaje_id = evento.pk
        except Exception:
            logger.exception('No se pudo registrar el evento de correccion por voz')
        return JsonResponse({
            'success': True,
            'aplicada': not requiere_revision,
            'evento_aprendizaje_id': evento_aprendizaje_id,
            **resultado,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Datos invalidos en la solicitud'}, status=400)
    except ValueError as error:
        logger.warning('Correccion de borrador rechazada: %s', error)
        return JsonResponse({'error': str(error)}, status=400)
    except Exception as error:
        logger.error('Error corrigiendo borrador con IA: %s', error, exc_info=True)
        return JsonResponse({
            'error': 'No se pudo aplicar la correccion. El informe no fue modificado.'
        }, status=500)


@require_POST
def deshacer_evento_correccion(request):
    """Registra deshacer o rehacer sin almacenar el contenido del informe."""
    if not user_can_access_dictado_module(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    try:
        data = json.loads(request.body)
        evento_id = data.get('evento_id')
        accion = str(data.get('accion') or 'deshacer').strip().lower()
        if accion not in {'deshacer', 'rehacer'}:
            return JsonResponse({'error': 'Accion invalida'}, status=400)
        evento = EventoAprendizajeDictado.objects.filter(
            pk=evento_id,
            usuario=request.user,
            tipo_evento=EventoAprendizajeDictado.TipoEvento.CORRECCION_VOZ_APLICADA,
        ).first()
        if not evento:
            return JsonResponse({'error': 'Evento de correccion no encontrado'}, status=404)
        estado_objetivo = accion == 'deshacer'
        if evento.revertido == estado_objetivo:
            return JsonResponse({'success': True, 'sin_cambios': True})

        evento.revertido = estado_objetivo
        evento.save(update_fields=['revertido'])
        registrar_evento_aprendizaje(
            usuario=request.user,
            tipo_evento=(
                EventoAprendizajeDictado.TipoEvento.CORRECCION_VOZ_DESHECHA
                if accion == 'deshacer'
                else EventoAprendizajeDictado.TipoEvento.CORRECCION_VOZ_REHECHA
            ),
            modo_dictado=evento.modo_dictado,
            plantilla_confirmada_codigo=evento.plantilla_confirmada_codigo,
            tipo_operacion=evento.tipo_operacion,
            metadatos={'evento_origen_id': evento.pk, 'accion': accion},
        )
        return JsonResponse({'success': True, 'sin_cambios': False})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Datos invalidos en la solicitud'}, status=400)
    except Exception:
        logger.exception('No se pudo marcar la correccion por voz como deshecha')
        return JsonResponse({'error': 'No se pudo registrar la accion'}, status=500)



# ========================================
# VISTAS PARA DICCIONARIO MÉDICO
# ========================================

class TerminoMedicoListView(LoginRequiredMixin, SuperuserRequiredMixin, ListView):
    """Lista de términos médicos del diccionario"""
    model = TerminoMedico
    template_name = 'dictado_informes/termino_list.html'
    context_object_name = 'terminos'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
        categoria = self.request.GET.get('categoria')
        activo = self.request.GET.get('activo')
        search = self.request.GET.get('q')
        
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        if activo == 'si':
            queryset = queryset.filter(activo=True)
        elif activo == 'no':
            queryset = queryset.filter(activo=False)
        if search:
            queryset = queryset.filter(
                Q(termino_incorrecto__icontains=search) |
                Q(termino_correcto__icontains=search) |
                Q(notas__icontains=search)
            )
        
        return queryset.order_by('-frecuencia_uso', 'termino_incorrecto')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_terminos'] = TerminoMedico.objects.count()
        context['terminos_activos'] = TerminoMedico.objects.filter(activo=True).count()
        context['mas_usados'] = TerminoMedico.objects.filter(activo=True).order_by('-frecuencia_uso')[:5]
        return context


class TerminoMedicoCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    """Crear nuevo término médico"""
    model = TerminoMedico
    form_class = TerminoMedicoForm
    template_name = 'dictado_informes/termino_form.html'
    success_url = reverse_lazy('dictado_informes:termino_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"✅ Término '{form.instance.termino_correcto}' agregado al diccionario")
        return super().form_valid(form)


class TerminoMedicoUpdateView(LoginRequiredMixin, SuperuserRequiredMixin, UpdateView):
    """Editar término médico existente"""
    model = TerminoMedico
    form_class = TerminoMedicoForm
    template_name = 'dictado_informes/termino_form.html'
    success_url = reverse_lazy('dictado_informes:termino_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"✅ Término '{form.instance.termino_correcto}' actualizado")
        return super().form_valid(form)


class TerminoMedicoDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    """Eliminar término médico"""
    model = TerminoMedico
    template_name = 'dictado_informes/termino_confirm_delete.html'
    success_url = reverse_lazy('dictado_informes:termino_list')
    
    def delete(self, request, *args, **kwargs):
        termino = self.get_object()
        messages.success(request, f"🗑️ Término '{termino.termino_correcto}' eliminado del diccionario")
        return super().delete(request, *args, **kwargs)


@require_POST
def toggle_termino_activo(request, pk):
    """Toggle estado activo/inactivo de un término"""
    termino = get_object_or_404(TerminoMedico, pk=pk)
    termino.activo = not termino.activo
    termino.save()
    
    estado = "activado" if termino.activo else "desactivado"
    return JsonResponse({
        'success': True,
        'activo': termino.activo,
        'message': f"Término '{termino.termino_correcto}' {estado}"
    })


@require_POST
def guardar_correccion_aprendizaje(request):
    """
    Guarda una corrección manual del usuario para entrenar la IA.
    Se llama cuando el usuario edita el texto mejorado y lo guarda.
    """
    if not user_can_access_dictado_module(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        data = json.loads(request.body)
        texto_original = data.get('texto_original', '')  # Transcripción Whisper
        texto_ia = data.get('texto_ia', '')              # Texto mejorado por IA
        texto_final = data.get('texto_final', '')        # Texto editado por usuario
        tipo_estudio = data.get('tipo_estudio', '')
        modo_dictado = str(data.get('modo_dictado') or '')[:20]
        tipo_plantilla = str(data.get('tipo_plantilla') or '')[:50]
        contexto_clinico = data.get('contexto_clinico') or {}
        if not isinstance(contexto_clinico, dict):
            contexto_clinico = {}
        
        if not texto_original or not texto_ia or not texto_final:
            return JsonResponse({'error': 'Faltan textos requeridos'}, status=400)
        
        # Solo guardar si el usuario hizo cambios
        if texto_ia.strip() == texto_final.strip():
            return JsonResponse({
                'success': True,
                'message': 'No hay cambios para guardar',
                'guardado': False
            })
        
        # Crear registro de aprendizaje
        correccion = CorreccionAprendizaje.objects.create(
            texto_original=texto_original,
            texto_ia=texto_ia,
            texto_final=texto_final,
            usuario=request.user,
            tipo_estudio=tipo_estudio if tipo_estudio in dict(TipoEstudio.choices) else '',
            modo_dictado=modo_dictado,
            tipo_plantilla=tipo_plantilla,
            region=str(contexto_clinico.get('region') or '')[:30],
            modalidad=str(contexto_clinico.get('modalidad') or '')[:20],
            lateralidad=str(contexto_clinico.get('lateralidad') or '')[:20],
        )

        apta_para_prompt = CorreccionAprendizaje.es_apta_para_prompt(correccion)
        estado_aprendizaje = "apta" if apta_para_prompt else "descartada_para_prompt"
        
        logger.info(f"✅ Corrección de aprendizaje guardada ID={correccion.id} por {request.user}")
        logger.info(f"   Cambios detectados: {len(correccion.cambios_detectados)}")
        logger.info(f"   Estado aprendizaje automático: {estado_aprendizaje}")

        if apta_para_prompt:
            mensaje = f"✅ Corrección guardada! {len(correccion.cambios_detectados)} cambios detectados"
        else:
            mensaje = (
                "✅ Corrección guardada en historial, pero no se usará automáticamente "
                "porque parece una edición atípica."
            )

        try:
            categorias = {}
            for cambio in correccion.cambios_detectados or []:
                categoria = str(cambio.get('categoria') or cambio.get('tipo') or 'otro')[:40]
                categorias[categoria] = categorias.get(categoria, 0) + 1
            registrar_evento_aprendizaje(
                usuario=request.user,
                tipo_evento=EventoAprendizajeDictado.TipoEvento.APRENDIZAJE_CONFIRMADO,
                tipo_estudio=correccion.tipo_estudio,
                modo_dictado=correccion.modo_dictado,
                region=correccion.region,
                modalidad=correccion.modalidad,
                lateralidad=correccion.lateralidad,
                plantilla_confirmada_codigo=correccion.tipo_plantilla,
                correccion=correccion,
                metadatos={
                    'cantidad_cambios': len(correccion.cambios_detectados or []),
                    'categorias': categorias,
                    'apta_para_prompt': apta_para_prompt,
                },
            )
        except Exception:
            logger.exception('No se pudo registrar la correccion en la bitacora de aprendizaje')
        
        return JsonResponse({
            'success': True,
            'message': mensaje,
            'guardado': True,
            'id': correccion.id,
            'cambios': correccion.cambios_detectados,
            'apta_para_prompt': apta_para_prompt,
            'estado_aprendizaje': estado_aprendizaje,
        })
        
    except Exception as e:
        logger.error(f"❌ Error guardando corrección: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def registrar_feedback_calidad(request):
    """Registra feedback binario de calidad y magnitud de edición manual."""
    if not user_can_access_dictado_module(request.user):
        return JsonResponse({'error': 'No autorizado'}, status=403)

    try:
        data = json.loads(request.body)
        estado_feedback = data.get('estado_feedback', '').strip()
        texto_ia = data.get('texto_ia', '')
        texto_final = data.get('texto_final', '')
        modo_dictado = data.get('modo_dictado', FeedbackCalidadDictado.ModoDictado.FIEL)
        tipo_estudio = data.get('tipo_estudio', '')
        tipo_plantilla = data.get('tipo_plantilla', '')

        estados_validos = {e[0] for e in FeedbackCalidadDictado.EstadoFeedback.choices}
        if estado_feedback not in estados_validos:
            return JsonResponse({'error': 'estado_feedback inválido'}, status=400)

        modos_validos = {m[0] for m in FeedbackCalidadDictado.ModoDictado.choices}
        if modo_dictado not in modos_validos:
            modo_dictado = FeedbackCalidadDictado.ModoDictado.FIEL

        if tipo_estudio not in dict(TipoEstudio.choices):
            tipo_estudio = ''

        metricas = _calcular_metricas_edicion(texto_ia, texto_final)

        feedback = FeedbackCalidadDictado.objects.create(
            usuario=request.user,
            estado_feedback=estado_feedback,
            modo_dictado=modo_dictado,
            tipo_estudio=tipo_estudio,
            tipo_plantilla=(tipo_plantilla or '')[:50],
            **metricas,
        )

        try:
            tipo_evento = (
                EventoAprendizajeDictado.TipoEvento.INFORME_ACEPTADO
                if estado_feedback == FeedbackCalidadDictado.EstadoFeedback.CORRECTO
                else EventoAprendizajeDictado.TipoEvento.INFORME_CORREGIDO
            )
            registrar_evento_aprendizaje(
                usuario=request.user,
                tipo_evento=tipo_evento,
                modo_dictado=modo_dictado,
                tipo_estudio=tipo_estudio,
                plantilla_confirmada_codigo=(tipo_plantilla or '')[:50],
                feedback=feedback,
                metadatos={
                    'porcentaje_edicion': feedback.porcentaje_edicion,
                    'tuvo_edicion': feedback.tuvo_edicion,
                },
            )
        except Exception:
            logger.exception('No se pudo registrar el feedback en la bitacora de aprendizaje')

        return JsonResponse({
            'success': True,
            'id': feedback.id,
            'porcentaje_edicion': feedback.porcentaje_edicion,
            'caracteres_editados': feedback.caracteres_editados,
            'tuvo_edicion': feedback.tuvo_edicion,
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Datos inválidos en la solicitud'}, status=400)
    except Exception as e:
        logger.exception(f"Error registrando feedback de calidad: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def info_aprendizaje(request):
    """
    Endpoint para obtener información sobre el sistema de aprendizaje activo
    """
    try:
        from .models import CorreccionAprendizaje
        
        # Obtener ejemplos para el usuario actual
        usuario = request.user if request.user.is_authenticated else None
        ejemplos = CorreccionAprendizaje.obtener_ejemplos_aprendizaje(usuario=usuario, limite=10)
        
        # Contar líneas de ejemplos (cada línea es una corrección)
        cantidad = len(ejemplos.split('\n')) if ejemplos else 0
        
        logger.info(f"📊 Info aprendizaje: usuario={usuario}, cantidad={cantidad}")
        
        return JsonResponse({
            'success': True,
            'cantidad': cantidad,
            'tiene_ejemplos': cantidad > 0
        })
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo info aprendizaje: {str(e)}")
        return JsonResponse({
            'success': False,
            'cantidad': 0,
            'tiene_ejemplos': False
        })
    except Exception as e:
        logger.exception(f"Error guardando corrección de aprendizaje: {str(e)}")
        return JsonResponse({
            'error': str(e)
        }, status=500)

