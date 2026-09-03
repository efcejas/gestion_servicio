"""Ontologia anatomica pequena para razonamiento estructural del dictado."""

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class ComponenteAnatomico:
    codigo: str
    nombre: str
    aliases: tuple[str, ...]
    frase_normal: str = ''


@dataclass(frozen=True)
class GrupoAnatomico:
    codigo: str
    nombre: str
    region: str
    aliases: tuple[str, ...]
    componentes: tuple[ComponenteAnatomico, ...]
    frase_residual: str
    disparadores_contexto: tuple[str, ...] = ()


ONTOLOGIA_ANATOMICA = (
    GrupoAnatomico(
        codigo='meniscos',
        nombre='Meniscos',
        region='RODILLA',
        aliases=('meniscos', 'aparato meniscal'),
        componentes=(
            ComponenteAnatomico(
                'menisco_interno',
                'Menisco interno',
                ('menisco interno', 'menisco medial'),
                'Menisco interno de altura y señal conservadas.',
            ),
            ComponenteAnatomico(
                'menisco_externo',
                'Menisco externo',
                ('menisco externo', 'menisco lateral'),
                'Menisco externo de altura y señal conservadas.',
            ),
        ),
        frase_residual='Resto de los meniscos sin otras alteraciones.',
        disparadores_contexto=('menisco', 'meniscal'),
    ),
    GrupoAnatomico(
        codigo='ligamentos_cruzados',
        nombre='Ligamentos cruzados',
        region='RODILLA',
        aliases=('ligamentos cruzados',),
        componentes=(
            ComponenteAnatomico(
                'ligamento_cruzado_anterior',
                'Ligamento cruzado anterior',
                ('ligamento cruzado anterior', 'cruzado anterior', 'lca'),
                'Ligamento cruzado anterior conservado.',
            ),
            ComponenteAnatomico(
                'ligamento_cruzado_posterior',
                'Ligamento cruzado posterior',
                ('ligamento cruzado posterior', 'cruzado posterior', 'lcp'),
                'Ligamento cruzado posterior conservado.',
            ),
        ),
        frase_residual='Resto de los ligamentos cruzados sin alteraciones.',
        disparadores_contexto=('ligamento cruzado', 'cruzado'),
    ),
    GrupoAnatomico(
        codigo='manguito_rotador',
        nombre='Manguito rotador',
        region='HOMBRO',
        aliases=('manguito rotador', 'tendones del manguito'),
        componentes=(
            ComponenteAnatomico('supraespinoso', 'Supraespinoso', ('supraespinoso',)),
            ComponenteAnatomico('infraespinoso', 'Infraespinoso', ('infraespinoso',)),
            ComponenteAnatomico('subescapular', 'Subescapular', ('subescapular',)),
            ComponenteAnatomico('redondo_menor', 'Redondo menor', ('redondo menor',)),
        ),
        frase_residual='Resto de tendones del manguito rotador sin alteraciones.',
    ),
    GrupoAnatomico(
        codigo='parenquima_cerebral',
        nombre='Parénquima cerebral',
        region='CEREBRO',
        aliases=(
            'parenquima cerebral', 'parenquima encefalico',
            'sustancia gris ni blanca', 'sustancia gris y blanca',
            'sustancias gris y blanca',
        ),
        componentes=(
            ComponenteAnatomico('sustancia_gris', 'Sustancia gris', ('sustancia gris',)),
            ComponenteAnatomico('sustancia_blanca', 'Sustancia blanca', ('sustancia blanca',)),
        ),
        frase_residual='No se observan otras alteraciones en el resto del parénquima cerebral.',
        disparadores_contexto=(
            'cerebral', 'encefalico', 'frontal', 'parietal', 'temporal',
            'occipital', 'cerebeloso', 'cerebelo',
        ),
    ),
)


PATOLOGIA_ALIASES = (
    'desgarro', 'rotura', 'ruptura', 'lesion', 'lesionado', 'lesionada',
    'edema', 'nodulo', 'nodular', 'masa', 'tumor', 'focal', 'isquemia',
    'infarto', 'hemorragia', 'tendinopatia', 'tenosinovitis', 'degenerativo',
)


def normalizar_anatomia(texto):
    texto = unicodedata.normalize('NFKD', str(texto or ''))
    texto = ''.join(char for char in texto if not unicodedata.combining(char))
    texto = re.sub(r'[^a-zA-Z0-9]+', ' ', texto.lower())
    return re.sub(r'\s+', ' ', texto).strip()


def _contiene_alias(texto_normalizado, alias):
    alias_normalizado = normalizar_anatomia(alias)
    if not alias_normalizado:
        return False
    return bool(re.search(rf'(?<!\w){re.escape(alias_normalizado)}(?!\w)', texto_normalizado))


def _aliases_grupo(grupo):
    aliases = list(grupo.aliases) + list(grupo.disparadores_contexto)
    for componente in grupo.componentes:
        aliases.extend(componente.aliases)
    return tuple(aliases)


def obtener_grupo(codigo):
    return next((grupo for grupo in ONTOLOGIA_ANATOMICA if grupo.codigo == codigo), None)


def grupo_para_linea(linea, exigir_conjunto=False):
    texto = normalizar_anatomia(linea)
    for grupo in ONTOLOGIA_ANATOMICA:
        tiene_alias_grupo = any(_contiene_alias(texto, alias) for alias in grupo.aliases)
        componentes = [
            componente for componente in grupo.componentes
            if any(_contiene_alias(texto, alias) for alias in componente.aliases)
        ]
        if tiene_alias_grupo or componentes:
            if exigir_conjunto and not (tiene_alias_grupo or len(componentes) > 1):
                continue
            return grupo
    return None


def componentes_afectados(grupo, contexto):
    afectados = []
    segmentos = [
        normalizar_anatomia(segmento)
        for segmento in re.split(r'[.\n;]+', str(contexto or ''))
        if normalizar_anatomia(segmento)
    ]
    for componente in grupo.componentes:
        for segmento in segmentos:
            menciona = any(_contiene_alias(segmento, alias) for alias in componente.aliases)
            patologico = any(_contiene_alias(segmento, alias) for alias in PATOLOGIA_ALIASES)
            if menciona and patologico:
                afectados.append(componente)
                break
    return tuple(afectados)


def contexto_patologico_del_grupo(grupo, contexto):
    segmentos = [normalizar_anatomia(s) for s in re.split(r'[.\n;]+', str(contexto or ''))]
    aliases = _aliases_grupo(grupo)
    return any(
        any(_contiene_alias(segmento, alias) for alias in aliases)
        and any(_contiene_alias(segmento, patologia) for patologia in PATOLOGIA_ALIASES)
        for segmento in segmentos
    )


def conjunto_completo_afectado(grupo, contexto):
    """Detecta cuando el dictado patologico alcanza al grupo en plural."""
    segmentos = [normalizar_anatomia(s) for s in re.split(r'[.\n;]+', str(contexto or ''))]
    return any(
        any(_contiene_alias(segmento, alias) for alias in grupo.aliases)
        and any(_contiene_alias(segmento, patologia) for patologia in PATOLOGIA_ALIASES)
        for segmento in segmentos
    )


def construir_linea_residual(linea_base, contexto):
    grupo = grupo_para_linea(linea_base, exigir_conjunto=True)
    if not grupo:
        return None

    if conjunto_completo_afectado(grupo, contexto):
        return None

    afectados = componentes_afectados(grupo, contexto)
    if not afectados:
        if grupo.codigo == 'parenquima_cerebral' and contexto_patologico_del_grupo(grupo, contexto):
            return grupo.frase_residual
        return None
    if len(afectados) >= len(grupo.componentes):
        return None

    restantes = [componente for componente in grupo.componentes if componente not in afectados]
    if len(restantes) == 1 and restantes[0].frase_normal:
        return restantes[0].frase_normal
    return grupo.frase_residual


def puntuar_linea_relacionada(linea, grupo):
    texto = normalizar_anatomia(linea)
    score = 0
    if any(
        _contiene_alias(texto, alias)
        for alias in grupo.aliases + grupo.disparadores_contexto
    ):
        score += 3
    for componente in grupo.componentes:
        if any(_contiene_alias(texto, alias) for alias in componente.aliases):
            score += 4
    if any(_contiene_alias(texto, alias) for alias in PATOLOGIA_ALIASES):
        score += 2
    return score


def resumen_ontologia_relevante(*textos):
    combinado = normalizar_anatomia(' '.join(str(texto or '') for texto in textos))
    grupos = [
        grupo for grupo in ONTOLOGIA_ANATOMICA
        if any(_contiene_alias(combinado, alias) for alias in _aliases_grupo(grupo))
    ]
    if not grupos:
        return ''

    lineas = ['RELACIONES ANATOMICAS EXPLICITAS:']
    for grupo in grupos:
        componentes = ', '.join(componente.nombre for componente in grupo.componentes)
        lineas.append(f'- {grupo.nombre} incluye: {componentes}.')
    lineas.append(
        'Si un componente esta patologico, no conservar una normalidad contradictoria del conjunto; '
        'describir los componentes restantes inmediatamente debajo del hallazgo.'
    )
    lineas.append(
        'Si el dictado atribuye patologia al grupo en plural, considerar afectados todos sus '
        'componentes y no agregar normalidades residuales individuales.'
    )
    return '\n'.join(lineas)


def mapa_aliases_estructuras():
    mapa = {}
    for grupo in ONTOLOGIA_ANATOMICA:
        mapa[grupo.codigo] = list(_aliases_grupo(grupo))
        for componente in grupo.componentes:
            mapa[componente.codigo] = list(componente.aliases)
    return mapa
