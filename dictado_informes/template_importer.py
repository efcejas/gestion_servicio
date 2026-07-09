import re
import zipfile
from html import unescape
from xml.etree import ElementTree


SECTION_ALIASES = {
    'INFORMACION CLINICA': {'INFORMACION CLINICA', 'INFORMACIÓN CLÍNICA', 'DATOS CLINICOS', 'DATOS CLÍNICOS'},
    'TECNICA': {'TECNICA', 'TÉCNICA', 'TECNICA DE ESTUDIO', 'TÉCNICA DE ESTUDIO', 'PROTOCOLO', 'SECUENCIAS'},
    'HALLAZGOS': {
        'HALLAZGOS', 'HALLAZGO', 'COMENTARIO', 'COMENTARIOS', 'INFORME',
        'DESCRIPCION', 'DESCRIPCIÓN', 'RESULTADO', 'RESULTADOS', 'DESARROLLO'
    },
    'CONCLUSION': {'CONCLUSION', 'CONCLUSIÓN', 'IMPRESION', 'IMPRESIÓN', 'OPINION', 'OPINIÓN'},
}

SECTION_TYPES = {
    'INFORMACION CLINICA': 'texto',
    'TECNICA': 'tecnica',
    'HALLAZGOS': 'hallazgos',
    'CONCLUSION': 'conclusion',
}

TECNICA_HINTS = {
    'se exploro', 'se exploró', 'se realizo', 'se realizó', 'se efectuo', 'se efectuó',
    'se adquirieron', 'se obtuvieron', 'se adiciono', 'se adicionó', 'se inyecto',
    'se inyectó', 'protocolo', 'secuencias', 'secuencia', 'ponderan', 'ponderadas',
    'relajacion', 'relajación', 't1', 't2', 'flair', 'stir', 'difusion', 'difusión',
    'adc', 'swi', 'gre', 'gadolinio', 'contraste', 'endovenoso', 'planos',
    'plano axial', 'plano coronal', 'plano sagital', 'axial', 'coronal', 'sagital',
}


class DocxTemplateImportError(ValueError):
    pass


def extraer_parrafos_docx(file_obj):
    """
    Extrae parrafos de un .docx leyendo word/document.xml.

    No preserva estilos complejos; para plantillas clinicas nos interesa el texto
    lineal y los encabezados de seccion.
    """
    try:
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        with zipfile.ZipFile(file_obj) as archivo:
            xml = archivo.read('word/document.xml')
    except KeyError as exc:
        raise DocxTemplateImportError('El archivo no contiene word/document.xml.') from exc
    except zipfile.BadZipFile as exc:
        raise DocxTemplateImportError('El archivo no parece ser un .docx valido.') from exc

    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise DocxTemplateImportError('No se pudo leer el XML interno del .docx.') from exc

    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    parrafos = []
    for parrafo in root.findall('.//w:p', ns):
        partes = []
        for nodo in parrafo.findall('.//w:t', ns):
            if nodo.text:
                partes.append(nodo.text)
        texto = normalizar_espacios(''.join(partes))
        if texto:
            parrafos.append(texto)

    if not parrafos:
        raise DocxTemplateImportError('No se encontraron parrafos con texto en el .docx.')

    return parrafos


def extraer_parrafos_texto(file_obj):
    """
    Extrae parrafos desde archivos de texto plano o formatos livianos.

    Soporta .txt, .md/.markdown, .rtf, .html/.htm y .doc basado en RTF
    sin dependencias externas.
    """
    nombre = (getattr(file_obj, 'name', '') or '').lower()
    extension = nombre.rsplit('.', 1)[-1] if '.' in nombre else 'txt'

    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)
    contenido = file_obj.read()
    if isinstance(contenido, str):
        texto = contenido
    else:
        texto = decodificar_texto(contenido)

    if extension == 'doc':
        inicio = contenido[:256] if not isinstance(contenido, str) else contenido[:256].encode('latin-1', errors='ignore')
        if not inicio.lstrip().startswith(b'{\\rtf'):
            raise DocxTemplateImportError(
                'Los archivos .doc binarios de Word 97-2003 no se pueden leer directamente. '
                'Abre el archivo en Word/LibreOffice y guardalo como .docx, .rtf o .txt.'
            )

    if extension in {'html', 'htm'}:
        texto = html_a_texto(texto)
    elif extension in {'rtf', 'doc'}:
        texto = rtf_a_texto(texto)
    elif extension in {'md', 'markdown'}:
        texto = markdown_a_texto(texto)

    parrafos = texto_a_parrafos(texto)
    if not parrafos:
        raise DocxTemplateImportError('No se encontraron parrafos con texto en el archivo.')

    return parrafos


def decodificar_texto(contenido):
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
        try:
            return contenido.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocxTemplateImportError('No se pudo decodificar el archivo de texto.')


def texto_a_parrafos(texto):
    texto = (texto or '').replace('\r\n', '\n').replace('\r', '\n')
    lineas = []
    for linea in texto.split('\n'):
        linea = normalizar_espacios(linea)
        if linea:
            lineas.append(linea)
    return lineas


def markdown_a_texto(texto):
    lineas = []
    for linea in (texto or '').splitlines():
        limpia = linea.strip()
        limpia = re.sub(r'^\s{0,3}#{1,6}\s+', '', limpia)
        limpia = re.sub(r'^\s*[-*+]\s+', '', limpia)
        limpia = re.sub(r'^\s*\d+[.)]\s+', '', limpia)
        limpia = re.sub(r'[*_`]+', '', limpia)
        lineas.append(limpia)
    return '\n'.join(lineas)


def html_a_texto(texto):
    texto = re.sub(r'(?is)<\s*(br|/p|/div|/h[1-6]|/li)\b[^>]*>', '\n', texto or '')
    texto = re.sub(r'(?is)<\s*(p|div|h[1-6]|li)\b[^>]*>', '\n', texto)
    texto = re.sub(r'(?is)<script\b.*?</script>', ' ', texto)
    texto = re.sub(r'(?is)<style\b.*?</style>', ' ', texto)
    texto = re.sub(r'(?s)<[^>]+>', ' ', texto)
    return unescape(texto)


def rtf_a_texto(texto):
    texto = re.sub(r"\\'[0-9a-fA-F]{2}", ' ', texto or '')
    texto = texto.replace('\\par', '\n').replace('\\line', '\n')
    texto = re.sub(r'\\[a-zA-Z]+-?\d* ?', ' ', texto)
    texto = texto.replace('{', ' ').replace('}', ' ').replace('\\', ' ')
    return texto


def construir_estructura_desde_parrafos(parrafos):
    titulo_lineas = []
    secciones = []
    seccion_actual = None

    for parrafo in parrafos:
        header, contenido_inline = detectar_header_y_contenido(parrafo)
        if header:
            seccion_actual = {
                'nombre': header,
                'tipo': SECTION_TYPES.get(header, 'texto'),
                'contenido_lineas': [],
            }
            if contenido_inline:
                seccion_actual['contenido_lineas'].append(contenido_inline)
            secciones.append(seccion_actual)
            continue

        if seccion_actual is None:
            titulo_lineas.append(parrafo)
        else:
            seccion_actual['contenido_lineas'].append(parrafo)

    titulo = titulo_lineas[0] if titulo_lineas else (parrafos[0] if parrafos else 'PLANTILLA IMPORTADA')
    tecnica = ''
    comentarios_base = []
    estructura_secciones = []

    if titulo:
        estructura_secciones.append({
            'nombre': 'TITULO',
            'tipo': 'titulo',
            'contenido': titulo,
            'editable_por_ia': True,
        })

    if not secciones and len(parrafos) > 1:
        tecnica_inferida, hallazgos_inferidos = separar_tecnica_y_hallazgos(parrafos[1:])
        if tecnica_inferida:
            secciones.append({
                'nombre': 'TECNICA',
                'tipo': 'tecnica',
                'contenido_lineas': tecnica_inferida,
            })
        secciones.append({
            'nombre': 'HALLAZGOS',
            'tipo': 'hallazgos',
            'contenido_lineas': hallazgos_inferidos if tecnica_inferida else parrafos[1:],
        })

    for seccion in secciones:
        nombre = seccion['nombre']
        tipo = seccion['tipo']
        lineas = [l for l in seccion.get('contenido_lineas', []) if l.strip()]
        contenido = '\n'.join(lineas).strip()

        if tipo == 'tecnica':
            tecnica = contenido
            estructura_secciones.append({
                'nombre': nombre,
                'tipo': tipo,
                'contenido': contenido,
                'editable_por_ia': False,
            })
        elif tipo == 'hallazgos':
            comentarios_base = lineas
            estructura_secciones.append({
                'nombre': nombre,
                'tipo': tipo,
                'lineas_base': lineas,
                'editable_por_ia': True,
            })
        elif tipo == 'conclusion':
            estructura_secciones.append({
                'nombre': nombre,
                'tipo': tipo,
                'contenido': contenido,
                'editable_por_ia': True,
            })
        else:
            estructura_secciones.append({
                'nombre': nombre,
                'tipo': tipo,
                'contenido': contenido,
                'editable_por_ia': True,
            })

    if not tecnica:
        tecnica = ''

    return {
        'titulo': titulo,
        'seccion_tecnica': tecnica,
        'comentarios_base': comentarios_base,
        'estructura_documento': {
            'modo': 'estricta',
            'permitir_secciones_nuevas': False,
            'secciones': estructura_secciones,
        },
    }


def importar_plantilla_docx(file_obj):
    parrafos = extraer_parrafos_docx(file_obj)
    return construir_estructura_desde_parrafos(parrafos)


def importar_plantilla_archivo(file_obj):
    nombre = (getattr(file_obj, 'name', '') or '').lower()
    if nombre.endswith('.docx'):
        parrafos = extraer_parrafos_docx(file_obj)
    elif nombre.endswith(('.txt', '.md', '.markdown', '.rtf', '.html', '.htm', '.doc')):
        parrafos = extraer_parrafos_texto(file_obj)
    else:
        raise DocxTemplateImportError('Formato no soportado. Usa .docx, .doc, .txt, .md, .rtf o .html.')
    return construir_estructura_desde_parrafos(parrafos)


def importar_plantilla_texto(texto):
    parrafos = texto_a_parrafos(texto)
    if not parrafos:
        raise DocxTemplateImportError('No se encontraron parrafos con texto para importar.')
    return construir_estructura_desde_parrafos(parrafos)


def separar_tecnica_y_hallazgos(parrafos):
    tecnica = []
    hallazgos = []
    bloque_tecnico_abierto = True

    for parrafo in parrafos:
        if bloque_tecnico_abierto and es_parrafo_tecnico(parrafo):
            tecnica.append(parrafo)
        else:
            bloque_tecnico_abierto = False
            hallazgos.append(parrafo)

    return tecnica, hallazgos


def es_parrafo_tecnico(parrafo):
    texto = normalizar_header(parrafo).lower()
    if not texto:
        return False

    hits = 0
    for hint in TECNICA_HINTS:
        if normalizar_header(hint).lower() in texto:
            hits += 1

    tiene_verbo_estudio = any(
        normalizar_header(v).lower() in texto
        for v in {'se exploro', 'se exploró', 'se realizo', 'se realizó', 'se efectuó', 'se adquirieron'}
    )
    tiene_secuencias = any(token in texto for token in {'t1', 't2', 'flair', 'stir', 'difusion', 'difusión', 'adc'})
    tiene_planos = any(token in texto for token in {'axial', 'coronal', 'sagital', 'planos'})

    return hits >= 2 or (tiene_verbo_estudio and (tiene_secuencias or tiene_planos))


def detectar_header(texto):
    header, _ = detectar_header_y_contenido(texto)
    return header


def detectar_header_y_contenido(texto):
    texto = (texto or '').strip()
    if not texto:
        return None, ''

    normalizado = normalizar_header(texto)
    for canonical, aliases in SECTION_ALIASES.items():
        aliases_norm = {normalizar_header(alias) for alias in aliases}
        if normalizado in aliases_norm:
            return canonical, ''

    match = re.match(r'^\s*([^:]{2,60})\s*:\s*(.+?)\s*$', texto)
    if match:
        posible_header = normalizar_header(match.group(1))
        contenido = normalizar_espacios(match.group(2))
        for canonical, aliases in SECTION_ALIASES.items():
            aliases_norm = {normalizar_header(alias) for alias in aliases}
            if posible_header in aliases_norm:
                return canonical, contenido

    return None, ''


def normalizar_header(texto):
    tabla = str.maketrans('ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')
    limpio = (texto or '').strip().translate(tabla).upper().rstrip(':')
    return normalizar_espacios(limpio)


def normalizar_espacios(texto):
    return re.sub(r'\s+', ' ', (texto or '').strip())
