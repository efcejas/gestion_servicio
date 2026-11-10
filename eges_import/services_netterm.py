from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal
import hashlib
from io import BytesIO
import json
import re
import unicodedata
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import OuterRef, Subquery
from openpyxl import load_workbook

from liquidacion.grupo_tarifario_mapping import es_eco_general_real, es_estudio_cardiologico


VERSION_PARSER_NETTERM = 'NETTERM_37_V3'
MAX_BYTES_NETTERM = 10 * 1024 * 1024
MAX_FILAS_NETTERM = 20000
ENCABEZADOS_NETTERM = (
    'SERVICIO', 'PEDIDO', 'PRACTICA', '', 'H.CLINICA', 'PACIENTE', 'T.DOC',
    'NRO.DOC', 'EDAD', 'FEC.PEDID.', '', 'FEC.REALIZ', '_1', 'COBERTURA',
    'PLAN', 'PROF.SOLIC.', 'HAB.', 'C', 'SECTOR', 'URGENTE', 'FEC.DIFERI',
    'PATOLOG', 'ESTADO', 'TECNICO', 'OPERADOR', 'CONFECC', 'NRO.VISUAL',
    'TIP.INF.', 'INFORMA', 'FEC.INFOR', '_2', 'IMPRESO', 'ANULA',
    'MOTIV.ANULA', 'DIA REALIZ', 'TIP.NOMENCLA', 'COD.NOMENCLA',
)


def _texto(valor):
    if valor is None:
        return ''
    if isinstance(valor, (float, Decimal)) and valor == int(valor):
        return str(int(valor))
    return str(valor).strip()


def _normalizado(valor):
    return ' '.join(''.join(
        caracter for caracter in unicodedata.normalize('NFKD', _texto(valor))
        if not unicodedata.combining(caracter)
    ).upper().split())


def _fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    for formato in ('%d/%m/%Y', '%Y-%m-%d', '%d/%m/%y'):
        try:
            return datetime.strptime(_texto(valor), formato).date()
        except ValueError:
            continue
    raise ValueError('fecha invalida')


def _hora(valor):
    if isinstance(valor, datetime):
        return valor.time()
    if isinstance(valor, time):
        return valor
    for formato in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(_texto(valor), formato).time()
        except ValueError:
            continue
    raise ValueError('hora invalida')


def clasificar_fila_netterm(nombre, codigo, servicio=''):
    from .models import EgesRow

    nombre_normalizado = _normalizado(nombre)
    practica = EgesRow(practica=_normalizado(nombre))
    modalidad = practica.clasificar_modalidad()
    if modalidad == 'OTROS' and any(alias in nombre_normalizado for alias in ('ANGIORESON', 'ANGIO RESON')):
        modalidad = 'RM'
    descripcion_insumo = practica.practica
    if modalidad != 'OTROS':
        descripcion_insumo = re.sub(
            r'\b(?:CON|SIN) (?:CONTRASTE|SEDACION)\b|\b[CS]/\s*CONTRASTE\b',
            '', descripcion_insumo,
        )
    es_insumo = EgesRow(practica=descripcion_insumo).clasificar_insumo()
    if es_insumo:
        return {'modalidad': 'INSUMO', 'es_insumo': True}
    if modalidad == 'OTROS':
        modalidad = EgesRow(servicio=_normalizado(servicio)).clasificar_modalidad()
    if modalidad != 'ECO':
        return {'modalidad': modalidad if modalidad != 'OTROS' else 'SIN_CLASIFICAR', 'es_insumo': False}
    return {'modalidad': _modalidad_eco(nombre, codigo), 'es_insumo': False}


def _modalidad_eco(nombre, codigo):
    if es_estudio_cardiologico('ECO', nombre, codigo):
        return 'ECOCAR'
    nombre_normalizado = _normalizado(nombre)
    if any(patron in nombre_normalizado for patron in ('DOPPLER', 'DUPLEX')):
        return 'DOP'
    if any(patron in nombre_normalizado for patron in ('ECOGRAF', 'ECO ')) and es_eco_general_real(
        tipo='ECO', nombre=nombre, codigo=codigo,
    ):
        return 'ECO_GENERAL'
    return 'SIN_CLASIFICAR'


def preparar_preview_netterm(archivo):
    """Lee un Netterm de 37 columnas; no consulta ni escribe modelos o sesiones."""
    if not str(getattr(archivo, 'name', '')).lower().endswith('.xlsx'):
        raise ValidationError('Netterm requiere un archivo .xlsx de 37 columnas.')
    archivo.seek(0)
    contenido = archivo.read(MAX_BYTES_NETTERM + 1)
    archivo.seek(0)
    if len(contenido) > MAX_BYTES_NETTERM:
        raise ValidationError('El archivo Netterm supera el limite de 10 MB.')
    try:
        with ZipFile(BytesIO(contenido)) as comprimido:
            if sum(item.file_size for item in comprimido.infolist()) > 100 * 1024 * 1024:
                raise ValidationError('El contenido expandido del archivo supera el limite permitido.')
        libro = load_workbook(BytesIO(contenido), read_only=True, data_only=False, keep_links=False)
    except (BadZipFile, OSError, ValueError, KeyError):
        raise ValidationError('No se pudo leer el libro XLSX Netterm.') from None

    filas = []
    advertencias = []
    motivos = Counter()
    hojas_leidas = []
    ignoradas = 0
    filas_procesadas = 0

    def advertir(hoja, numero, codigo, campo):
        motivos[codigo] += 1
        if len(advertencias) < 100:
            advertencias.append({'hoja': hoja, 'fila': numero, 'codigo': codigo, 'campo': campo})

    try:
        for hoja in libro:
            if hoja.max_column and hoja.max_column > len(ENCABEZADOS_NETTERM):
                raise ValidationError('El libro contiene columnas fuera del formato Netterm de 37 columnas.')
            if hoja.max_row and hoja.max_row > MAX_FILAS_NETTERM + 1:
                raise ValidationError('El libro supera el limite de 20000 filas de datos.')
            iterador = hoja.iter_rows()
            encabezado = next(iterador, ())
            if not any(_texto(celda.value) for celda in encabezado):
                if any(any(_texto(celda.value) for celda in fila) for fila in iterador):
                    raise ValidationError('Hay una hoja con datos pero sin encabezado Netterm.')
                continue
            esperado = list(ENCABEZADOS_NETTERM)
            recibido = [_normalizado(celda.value) for celda in encabezado]
            if recibido != esperado:
                raise ValidationError('El libro no coincide con las 37 columnas Netterm esperadas, en su orden original.')
            hojas_leidas.append(hoja.title)
            for numero, celdas in enumerate(iterador, start=2):
                filas_procesadas += 1
                if filas_procesadas > MAX_FILAS_NETTERM:
                    raise ValidationError('El libro supera el limite de 20000 filas de datos.')
                valores = tuple(celda.value for celda in celdas)
                if not any(_texto(valor) for valor in valores):
                    ignoradas += 1
                    continue
                if [_normalizado(valor) for valor in valores] == esperado:
                    ignoradas += 1
                    continue
                if any(celda.data_type == 'f' for celda in celdas):
                    advertir(hoja.title, numero, 'FORMULA_NO_ADMITIDA', 'fila')
                    ignoradas += 1
                    continue
                pedido, practica, codigo = _texto(valores[1]), _texto(valores[2]), _texto(valores[36])
                if not pedido or not practica or not codigo:
                    advertir(hoja.title, numero, 'FILA_NO_IDENTIFICABLE', 'pedido/practica/codigo')
                    ignoradas += 1
                    continue
                fechas = {}
                for campo, indice, conversor in (
                    ('fecha_pedido', 9, _fecha), ('hora_pedido', 10, _hora),
                    ('fecha_realizacion', 11, _fecha), ('hora_realizacion', 12, _hora),
                    ('fecha_informe', 29, _fecha), ('hora_informe', 30, _hora),
                ):
                    fechas[campo] = None
                    if not _texto(valores[indice]):
                        if campo in {'fecha_pedido', 'hora_pedido'}:
                            advertir(hoja.title, numero, 'DATO_AUSENTE', campo)
                        continue
                    try:
                        fechas[campo] = conversor(valores[indice])
                    except ValueError:
                        advertir(hoja.title, numero, 'DATO_INVALIDO', campo)
                if not _texto(valores[7]):
                    advertir(hoja.title, numero, 'DATO_AUSENTE', 'documento')
                if not _texto(valores[28]):
                    advertir(hoja.title, numero, 'DATO_AUSENTE', 'informante')
                estado = _normalizado(valores[22])
                estado_informe = {
                    'INFORME DEFINITIVO': 'DEFINITIVO',
                    'INFORME NO DEFINITIV': 'NO_DEFINITIVO',
                    'PENDIENTE INFORMAR': 'PENDIENTE',
                    'ESCRITO': 'ESCRITO',
                }.get(estado, 'DESCONOCIDO')
                if estado not in {
                    'INFORME DEFINITIVO', 'INFORME NO DEFINITIV', 'PENDIENTE INFORMAR',
                    'PENDIENTE REALIZAR', 'ANULADO', 'ESCRITO',
                }:
                    advertir(hoja.title, numero, 'ESTADO_DESCONOCIDO', 'estado')
                filas.append({
                    'hoja': hoja.title, 'numero_fila': numero, 'originales': valores,
                    'servicio': _texto(valores[0]),
                    'pedido': pedido, 'practica': practica,
                    'tipo_nomenclador': _texto(valores[35]), 'codigo_nomenclador': codigo,
                    'historia_clinica': _texto(valores[4]), 'tipo_documento': _texto(valores[6]),
                    'documento': _texto(valores[7]), 'paciente': _texto(valores[5]),
                    'marca_atencion_original': _texto(valores[3]), 'sector': _texto(valores[18]),
                    'urgencia_original': _texto(valores[19]), 'numero_visual': _texto(valores[26]),
                    'solicitante': _texto(valores[15]), 'informante': _texto(valores[28]),
                    'tecnico': _texto(valores[23]), 'operador': _texto(valores[24]),
                    'autor_anulacion': _texto(valores[32]), 'motivo_anulacion': _texto(valores[33]),
                    'estado_original': _texto(valores[22]), 'estado_informe': estado_informe,
                    'estado_realizacion': 'PENDIENTE' if estado == 'PENDIENTE REALIZAR' else (
                        'CON_FECHA' if fechas['fecha_realizacion'] else 'DESCONOCIDO'
                    ),
                    'anulado': estado == 'ANULADO',
                    **clasificar_fila_netterm(practica, codigo, _texto(valores[0])),
                    'cantidad': None,
                    **fechas,
                })
    finally:
        libro.close()
    if not hojas_leidas:
        raise ValidationError('No se encontro una hoja Netterm con encabezados validos.')
    claves = Counter((fila['pedido'], fila['tipo_nomenclador'], fila['codigo_nomenclador']) for fila in filas)
    for fila in filas:
        fila['clave_repetida'] = claves[(fila['pedido'], fila['tipo_nomenclador'], fila['codigo_nomenclador'])] > 1

    def distribucion(campo, excluir_insumos=False):
        return [{'valor': valor, 'cantidad': cantidad} for valor, cantidad in sorted(Counter(
            fila[campo] or 'DESCONOCIDO' for fila in filas
            if not excluir_insumos or not fila['es_insumo']
        ).items())]

    periodos = {}
    for campo in ('fecha_pedido', 'fecha_realizacion', 'fecha_informe'):
        fechas_validas = [fila[campo] for fila in filas if fila[campo]]
        periodos[campo] = {
            'desde': min(fechas_validas) if fechas_validas else None,
            'hasta': max(fechas_validas) if fechas_validas else None,
            'presentes': len(fechas_validas), 'ausentes': len(filas) - len(fechas_validas),
        }
    return {
        'version_parser': VERSION_PARSER_NETTERM,
        'sha256': hashlib.sha256(contenido).hexdigest(),
        'hojas': hojas_leidas, 'filas': filas,
        'resumen': {
            'filas_validas': len(filas), 'filas_ignoradas': ignoradas,
            'filas_practicas': sum(not fila['es_insumo'] for fila in filas),
            'filas_insumos': sum(fila['es_insumo'] for fila in filas),
            'claves_repetidas': sum(cantidad > 1 for cantidad in claves.values()),
            'filas_en_claves_repetidas': sum(cantidad for cantidad in claves.values() if cantidad > 1),
            'advertencias_total': sum(motivos.values()),
            'advertencias_por_codigo': [{'valor': valor, 'cantidad': cantidad} for valor, cantidad in sorted(motivos.items())],
            'modalidades': distribucion('modalidad', excluir_insumos=True), 'estados': distribucion('estado_informe'),
            'realizacion': distribucion('estado_realizacion'), 'periodos': periodos,
            'anulados': sum(fila['anulado'] for fila in filas),
        },
        'advertencias': advertencias,
    }


def _json_normalizado(valor):
    return json.loads(json.dumps(valor, cls=DjangoJSONEncoder, ensure_ascii=False, allow_nan=False))


def _huella_json(valor):
    return hashlib.sha256(json.dumps(
        valor, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ).encode('utf-8')).hexdigest()


def _celda_original_json(valor):
    return {'tipo': type(valor).__name__, 'valor': _json_normalizado(valor)}


@transaction.atomic
def guardar_lote_netterm(*, archivo, usuario, motivo, sha256_esperado, version_parser_esperada):
    """Archiva observaciones de origen; no consolida estudios ni actualiza EGES."""
    from .models import NettermFila, NettermLote

    if not usuario.is_authenticated or not usuario.is_superuser:
        raise ValidationError('Solo un superusuario puede guardar lotes Netterm.')
    motivo = (motivo or '').strip()
    if not motivo or len(motivo) > 2000:
        raise ValidationError('Indica un motivo de hasta 2000 caracteres.')
    resultado = preparar_preview_netterm(archivo)
    if resultado['sha256'] != sha256_esperado or resultado['version_parser'] != version_parser_esperada:
        raise ValidationError('El archivo o la version del lector no coincide con el preview. No se guardo el lote.')
    if not resultado['filas']:
        raise ValidationError('No hay filas identificables para guardar.')
    existente = NettermLote.objects.filter(archivo_sha256=resultado['sha256']).first()
    if existente:
        return {'lote': existente, 'creado': False}

    observaciones = []
    for fila in resultado['filas']:
        originales = [_celda_original_json(valor) for valor in fila['originales']]
        normalizados = _json_normalizado({
            campo: valor for campo, valor in fila.items()
            if campo not in {'originales', 'hoja', 'numero_fila', 'clave_repetida'}
        })
        observaciones.append({
            'fila': fila,
            'originales': originales,
            'normalizados': normalizados,
            'clave': _huella_json([fila['pedido'], fila['tipo_nomenclador'], fila['codigo_nomenclador']]),
            'contenido': _huella_json(originales),
        })
    anteriores = {}
    ultimo_lote = NettermFila.objects.filter(
        clave_candidata_sha256=OuterRef('clave_candidata_sha256'),
    ).order_by('-lote_id').values('lote_id')[:1]
    for previa in NettermFila.objects.filter(
        clave_candidata_sha256__in={item['clave'] for item in observaciones},
        lote_id=Subquery(ultimo_lote),
    ).only(
        'pk', 'lote_id', 'clave_candidata_sha256', 'contenido_sha256', 'normalizados_json',
        'clase_observacion',
    ).order_by('clave_candidata_sha256', 'pk').iterator(chunk_size=500):
        anteriores.setdefault(previa.clave_candidata_sha256, []).append(previa)
    clases = Counter()
    for item in observaciones:
        fila = item['fila']
        previas = anteriores.get(item['clave'], [])
        referencia = None
        clase = NettermFila.CLASE_NUEVA
        if (
            fila['clave_repetida'] or not fila['tipo_nomenclador'] or len(previas) > 1
            or (previas and previas[0].clase_observacion == NettermFila.CLASE_AMBIGUA)
        ):
            clase = NettermFila.CLASE_AMBIGUA
        elif previas:
            previa = previas[0]
            campos_identidad = ('tipo_documento', 'documento', 'historia_clinica')
            identidad = tuple(item['normalizados'].get(campo) or '' for campo in campos_identidad)
            identidad_previa = tuple(previa.normalizados_json.get(campo) or '' for campo in campos_identidad)
            if not any(identidad[1:]) or identidad != identidad_previa:
                clase = NettermFila.CLASE_AMBIGUA
            else:
                referencia = previa
                clase = NettermFila.CLASE_REITERADA if item['contenido'] == previa.contenido_sha256 else NettermFila.CLASE_ACTUALIZADA
        item['referencia'] = referencia
        item['clase'] = clase
        clases[clase] += 1
    resumen = _json_normalizado(resultado['resumen'])
    resumen['observaciones_por_clase'] = [
        {'valor': clase, 'cantidad': cantidad} for clase, cantidad in sorted(clases.items())
    ]
    lote, creado = NettermLote.objects.get_or_create(
        archivo_sha256=resultado['sha256'],
        defaults={
            'archivo_nombre': str(archivo.name)[:255],
            'version_parser': resultado['version_parser'],
            'importado_por': usuario,
            'motivo': motivo,
            'resumen_json': resumen,
            'advertencias_json': resultado['advertencias'],
        },
    )
    if not creado:
        return {'lote': lote, 'creado': False}
    NettermFila.objects.bulk_create([
        NettermFila(
            lote=lote,
            hoja=item['fila']['hoja'],
            numero_fila=item['fila']['numero_fila'],
            clave_candidata_sha256=item['clave'],
            contenido_sha256=item['contenido'],
            clase_observacion=item['clase'],
            referencia_previa=item['referencia'],
            originales_json=item['originales'],
            normalizados_json=item['normalizados'],
            fecha_pedido=item['fila']['fecha_pedido'],
            fecha_realizacion=item['fila']['fecha_realizacion'],
            fecha_informe=item['fila']['fecha_informe'],
            modalidad=item['fila']['modalidad'],
            estado_informe=item['fila']['estado_informe'],
            anulado=item['fila']['anulado'],
        )
        for item in observaciones
    ], batch_size=500)
    return {'lote': lote, 'creado': True}