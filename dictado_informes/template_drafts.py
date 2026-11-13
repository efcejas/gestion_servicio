"""Borradores de plantillas normales: contexto cerrado, referencias y confirmación."""
import re
import unicodedata
import uuid

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import PlantillaEstructurada


# Catálogo cerrado: impide enviar texto libre (dictado/PHI) como contexto a la IA.
REGIONES_BORRADOR = {
    'RODILLA': 'Rodilla', 'HOMBRO': 'Hombro', 'BRAZO': 'Brazo',
    'CODO': 'Codo', 'MANO': 'Mano', 'DEDO': 'Dedo',
    'MUNECA': 'Muñeca', 'TOBILLO': 'Tobillo',
    'PIE': 'Pie', 'CADERA': 'Cadera', 'CEREBRO': 'Cerebro',
    'COLUMNA_CERVICAL': 'Columna cervical', 'COLUMNA_DORSAL': 'Columna dorsal',
    'COLUMNA_LUMBAR': 'Columna lumbar', 'ABDOMEN': 'Abdomen',
    'PELVIS': 'Pelvis', 'TORAX': 'Tórax', 'CUELLO': 'Cuello',
    'ATM': 'Articulación temporomandibular', 'MAMA': 'Mama',
}
MODALIDADES_BORRADOR = {
    'RES': 'RM', 'TOM': 'TC', 'RAD': 'RX', 'ECO': 'Ecografía',
    'MAM': 'Mamografía', 'DEN': 'Densitometría',
}
CRITERIO_REFERENCIAS = (
    'Plantillas activas y visibles cercanas por modalidad/región. '
    'Sin frecuencia de uso clínico fiable; popularidad pendiente para una fase futura.'
)
SALT = 'dictado.plantilla-normal.v1'
PATOLOGIA_BORRADOR_RE = re.compile(
    r'\b(rotura|desgarro|lesion\w*|tumor\w*|masa|nodulo\w*|edema|'
    r'fractura\w*|luxacion\w*|derrame|patologic\w*|adenopatia\w*|'
    r'coleccion\w*|quiste\w*|alteracion\w*|liquido libre)\b'
)
NEGACION_BORRADOR = (
    r'\b(?:sin|ni|ausencia\s+de|no(?:\s+se)?\s+'
    r'(?:identifica\w*|observa\w*|evidencia\w*|detecta\w*|'
    r'visualiza\w*|aprecia\w*))\s+'
    r'(?:(?:evidencia|signos?)\s+de\s+)?'
    r'(?:lesion\w*|alteracion\w*|hallazg\w*|fractura\w*|edema|'
    r'tumor\w*|masa|nodulo\w*|luxacion\w*|derrame|rotura\w*|'
    r'desgarro\w*|adenopatia\w*|coleccion\w*|quiste\w*|liquido libre)\b'
)
NEGACION_BORRADOR_RE = re.compile(NEGACION_BORRADOR)
NORMALIDAD_BORRADOR_RE = re.compile(
    r'\b(?:normal\w*|conservad\w*|habitual\w*)\b|' + NEGACION_BORRADOR
)


def normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto)
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(
        c for c in texto.lower() if not unicodedata.combining(c)
    )).strip()


def validar_contexto(data):
    region, modalidad = data.get('region'), data.get('modalidad')
    if region not in REGIONES_BORRADOR or modalidad not in MODALIDADES_BORRADOR:
        raise ValidationError('Elegí una región anatómica precisa y una modalidad.')
    return region, modalidad


def seleccionar_referencias(usuario, region, modalidad, limite=3):
    """Sin trazas/conteos: modalidad exacta primero, luego región, empate por PK."""
    alias = {
        'RES': ('rm', 'resonancia'), 'TOM': ('tc', 'tomografia'),
        'RAD': ('rx', 'radiografia'), 'ECO': ('eco', 'ecografia'),
        'MAM': ('mamografia',), 'DEN': ('densitometria',),
    }
    region_tokens = set(normalizar(REGIONES_BORRADOR[region]).split())
    candidatas = []
    for plantilla in PlantillaEstructurada.visibles_para_usuario(usuario, solo_activas=True):
        tokens = set(normalizar(f'{plantilla.nombre} {plantilla.titulo}').split())
        modalidades = {key for key, palabras in alias.items() if tokens.intersection(palabras)}
        if modalidades and modalidad not in modalidades:
            continue
        cercania = len(tokens & region_tokens)
        misma_modalidad = modalidad in modalidades
        if not misma_modalidad and not cercania:
            continue
        candidatas.append((misma_modalidad, cercania, plantilla))
    candidatas.sort(key=lambda item: (-int(item[0]), -item[1], item[2].pk))
    return [item[2] for item in candidatas[:limite]]


def validar_borrador(data, region, modalidad, *, advertencias=None):
    """Contrato pequeño y estricto; revisión clínica humana sigue siendo obligatoria."""
    if not isinstance(data, dict):
        raise ValidationError('El borrador debe ser un objeto.')
    permitidos = {'nombre', 'titulo', 'comentarios_base', 'seccion_tecnica', 'conclusion'}
    if set(data) - permitidos:
        raise ValidationError('El borrador contiene campos no permitidos.')
    if data.get('seccion_tecnica') or data.get('conclusion'):
        raise ValidationError('El borrador no puede afirmar técnica ni conclusión.')
    nombre, titulo = data.get('nombre'), data.get('titulo')
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre) > 200:
        raise ValidationError('Nombre obligatorio, hasta 200 caracteres.')
    if not isinstance(titulo, str) or not titulo.strip() or len(titulo) > 500:
        raise ValidationError('Título obligatorio, hasta 500 caracteres.')
    metadatos = normalizar(f'{nombre} {titulo}')
    if re.search(r'\b(contraste|gadolinio|secuencias|paciente|dni)\b', metadatos):
        raise ValidationError('Nombre y título no deben agregar técnica ni datos de paciente.')
    objetivo = set(normalizar(REGIONES_BORRADOR[region]).split())
    if not objetivo.issubset(set(normalizar(titulo).split())):
        raise ValidationError('El título debe conservar la región solicitada.')
    modalidad_tokens = {
        'RES': {'rm', 'resonancia'}, 'TOM': {'tc', 'tomografia'},
        'RAD': {'rx', 'radiografia'}, 'ECO': {'eco', 'ecografia'},
        'MAM': {'mamografia'}, 'DEN': {'densitometria'},
    }
    if not modalidad_tokens[modalidad].intersection(normalizar(titulo).split()):
        raise ValidationError('El título debe conservar la modalidad solicitada.')
    lineas = data.get('comentarios_base')
    if not isinstance(lineas, list) or not 1 <= len(lineas) <= 30:
        raise ValidationError('Se requieren entre 1 y 30 líneas de anatomía normal.')
    for numero, linea in enumerate(lineas, 1):
        if (not isinstance(linea, str) or not linea.strip() or len(linea) > 500
                or '\n' in linea or '\r' in linea):
            raise ValidationError('Cada línea debe tener entre 1 y 500 caracteres.')
        texto = normalizar(linea)
        if re.search(
            r'\b(t1|t2|stir|flair|secuencia|secuencias|contraste|gadolinio|'
            r'dosis|proyecciones|adquisicion|paciente|dni|historia clinica)\b', texto
        ):
            raise ValidationError('No incluir técnica ni datos de paciente en las líneas base.')
        segmentos = re.split(r'[,.;]|\b(?:y|pero|aunque)\b', texto)
        if any(
            PATOLOGIA_BORRADOR_RE.search(NEGACION_BORRADOR_RE.sub('', segmento))
            for segmento in segmentos
        ):
            raise ValidationError(
                f'Línea {numero}: se detectó una posible afirmación patológica. '
                'La plantilla debe describir anatomía normal.'
            )
        if not NORMALIDAD_BORRADOR_RE.search(texto):
            mensaje = (
                f'Línea {numero}: no se reconoció una expresión de normalidad. '
                'Revisá esa línea y reformulala o eliminala antes de guardar. '
                'Esto no significa que se haya detectado patología.'
            )
            if advertencias is None:
                raise ValidationError(mensaje)
            advertencias.append(mensaje)
    if len({normalizar(linea) for linea in lineas}) != len(lineas):
        raise ValidationError('El borrador contiene líneas repetidas.')
    return {
        'nombre': nombre.strip(), 'titulo': titulo.strip(),
        'comentarios_base': [linea.strip() for linea in lineas],
        'seccion_tecnica': '', 'conclusion': '',
    }


def generar_borrador(usuario, data):
    from .ai_services import ai_service

    region, modalidad = validar_contexto(data)
    referencias = seleccionar_referencias(usuario, region, modalidad)
    if not referencias:
        raise ValidationError(
            'No hay referencias activas compatibles. Creá la plantilla manualmente en la biblioteca.'
        )
    # Nunca pasar data ni contexto clínico del informe al generador.
    borrador = ai_service.generar_plantilla_normal(
        region=REGIONES_BORRADOR[region],
        modalidad=MODALIDADES_BORRADOR[modalidad],
        referencias=[{
            'nombre': p.nombre, 'titulo': p.titulo,
            'comentarios_base': (p.comentarios_base or [])[:30],
            'secciones': [
                s['nombre'] for s in p.obtener_estructura_documento()['secciones']
                if s['tipo'] in {'hallazgos', 'conclusion'}
            ],
        } for p in referencias],
    )
    advertencias = []
    borrador = validar_borrador(borrador, region, modalidad, advertencias=advertencias)
    token = signing.dumps({
        'usuario': usuario.pk, 'region': region, 'modalidad': modalidad,
        'codigo': f'IA_{uuid.uuid4().hex.upper()}',
    }, salt=SALT)
    return {
        'borrador': borrador, 'token': token,
        'advertencias': advertencias,
        'referencias': [{'codigo': p.codigo, 'nombre': p.nombre} for p in referencias],
        'criterio_referencias': CRITERIO_REFERENCIAS,
    }


def confirmar_borrador(usuario, data):
    if data.get('confirmar') is not True:
        raise ValidationError('Se requiere confirmación explícita del médico.')
    try:
        contexto = signing.loads(data.get('token', ''), salt=SALT, max_age=1800)
    except (signing.BadSignature, TypeError):
        raise ValidationError('El borrador venció o no es válido. Generá una nueva propuesta.')
    if contexto['usuario'] != usuario.pk:
        raise ValidationError('El borrador pertenece a otro usuario.')
    borrador = validar_borrador(data.get('borrador'), contexto['region'], contexto['modalidad'])
    compartida = data.get('compartida', False)
    if not isinstance(compartida, bool):
        raise ValidationError('Compartida debe ser un valor booleano.')
    estructura = {
        'modo': 'estricta', 'permitir_secciones_nuevas': False,
        'secciones': [
            {'nombre': 'TITULO', 'tipo': 'titulo', 'contenido': borrador['titulo']},
            {'nombre': 'COMENTARIO', 'tipo': 'hallazgos', 'lineas_base': borrador['comentarios_base']},
            {'nombre': 'CONCLUSION', 'tipo': 'conclusion', 'contenido': ''},
        ],
    }
    with transaction.atomic():
        # Código firmado único: reintentar confirmación no duplica ni modifica la plantilla.
        plantilla, _ = PlantillaEstructurada.objects.get_or_create(
            codigo=contexto['codigo'],
            defaults={
                'nombre': borrador['nombre'], 'titulo': borrador['titulo'],
                'seccion_tecnica': '', 'comentarios_base': borrador['comentarios_base'],
                'estructura_documento': estructura, 'modo_estructura': 'estricta',
                'creada_por': usuario, 'origen': 'user', 'activa': True,
                'compartida': compartida,
            },
        )
    if plantilla.creada_por_id != usuario.pk or not plantilla.activa:
        raise ValidationError('La plantilla ya no está disponible.')
    return plantilla
