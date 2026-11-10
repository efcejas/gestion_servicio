"""Diagnostico RX de solo lectura en SQLite descartable; salida sin pacientes.

Ejecutar desde la raiz: gestion_env/Scripts/python.exe scripts/utils/analizar_rx_conjuntos.py --directorio <exportaciones>
No modifica reglas de conciliacion, cantidades, estadisticas ni pagos.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata


def texto(valor):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(valor or ''))
                            if not unicodedata.combining(c)).upper().split())


def resumen_filas(filas):
    # Solo campos del catalogo, cantidades y estados; nunca identidad/fecha/pedido.
    return [{'codigo': f['codigo'], 'descripcion': f['descripcion'],
             'cantidad': str(f['cantidad']) if f['cantidad'] is not None else None,
             'estado': f['estado']} for f in filas]


def analizar(directorio):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from eges_import.models import ImportBatch
    from eges_import.services import procesar_excel_eges
    from eges_import.services_conciliacion import _dni, _codigo
    from eges_import.services_netterm import preparar_preview_netterm

    call_command('migrate', verbosity=0)
    usuario = get_user_model().objects.create_user(username='qa_rx_conjuntos', is_superuser=True)
    nombres = ['Atendidos-RX-Octubre-26.xls', 'LibroDescargadoNetterm-RX-oct-26.xlsx']
    archivos = {n: (directorio / n).read_bytes() for n in nombres}
    lote = ImportBatch.objects.create(usuario=usuario, archivo_nombre=nombres[0])
    importacion = procesar_excel_eges(SimpleUploadedFile(nombres[0], archivos[nombres[0]]), lote)
    eges = []
    for f in lote.filas.filter(es_insumo=False, modalidad='RX').order_by('pk'):
        eges.append({'persona': _dni(f.dni_paciente), 'fecha': f.fecha_turno,
                     'sesion': (str(f.hora_turno), f.centro_atencion, f.protocolo, f.numero_turno),
                     'codigo': _codigo(f.codigo_practica), 'descripcion': texto(f.practica),
                     'cantidad': f.cantidad, 'estado': texto(f.estado_turno),
                     'region': texto(f.region_informe)})
    preview = preparar_preview_netterm(SimpleUploadedFile(nombres[1], archivos[nombres[1]]))
    netterm = [{'persona': _dni(f['documento']) if re.sub('[^A-Z]', '', texto(f['tipo_documento'])) == 'DNI' else None,
                'fecha': f['fecha_pedido'], 'pedido': f['pedido'],
                'codigo': _codigo(f['codigo_nomenclador']), 'descripcion': texto(f['practica']),
                'cantidad': None, 'estado': f['estado_informe'], 'region': texto(f['originales'][21])}
               for f in preview['filas'] if f['modalidad'] == 'RX' and not f['es_insumo']]
    eg_dias, nt_pedidos = defaultdict(list), defaultdict(list)
    for f in eges:
        if f['persona'] and f['fecha']:
            eg_dias[(f['persona'], f['fecha'])].append(f)
    for f in netterm:
        if f['persona'] and f['fecha'] and f['pedido']:
            nt_pedidos[(f['persona'], f['fecha'], f['pedido'])].append(f)
    pedidos_por_dia = Counter(k[:2] for k in nt_pedidos)
    codigos = lambda fs: Counter(f['codigo'] for f in fs)
    marca = lambda f: bool(re.search(r'\bSUBSIG', f['descripcion']))
    medida, patrones = Counter(), Counter()
    ejemplos = {}
    for clave, filas in nt_pedidos.items():
        if len(filas) < 2:
            continue
        medida['pedidos_multifila'] += 1
        otras = eg_dias.get(clave[:2], [])
        medida['sin_eges_mismo_dni_fecha' if not otras else 'con_eges_mismo_dni_fecha'] += 1
        medida['multifila_con_marca_SUBSIG_amplia'] += any(marca(f) for f in filas)
        if len(otras) < 2:
            continue
        medida['multifila_con_varias_filas_eges'] += 1
        sesiones = defaultdict(list)
        for f in otras:
            sesiones[f['sesion']].append(f)
        candidatos = [fs for fs in sesiones.values() if codigos(fs) == codigos(filas)]
        mismos_dia = codigos(otras) == codigos(filas)
        medida['multiconjunto_codigos_igual_todo_dia'] += mismos_dia
        medida['multiconjunto_codigos_igual_una_sesion'] += len(candidatos) == 1
        medida['multiconjunto_codigos_igual_varias_sesiones'] += len(candidatos) > 1
        sub = codigos(filas) <= codigos(otras)
        medida['codigos_nt_contenidos_con_multiplicidad_en_eges_dia'] += sub
        if not candidatos:
            continue
        # No se resuelve identidad: puede haber mas de un pedido con la misma firma.
        rivales = sum(codigos(fs) == codigos(filas) for k, fs in nt_pedidos.items() if k[:2] == clave[:2])
        if len(candidatos) != 1 or rivales != 1:
            medida['igualdad_codigos_no_univoca_por_sesion_o_pedido'] += 1
            continue
        medida['firma_codigos_univoca_pedido_sesion'] += 1
        elegidas = candidatos[0]
        medida['firma_univoca_con_subsig_en_ambas'] += any(marca(f) for f in filas) and any(marca(f) for f in elegidas)
        medida['firma_univoca_eges_todas_cantidad_1'] += all(f['cantidad'] == 1 for f in elegidas)
        medida['firma_univoca_eges_alguna_cantidad_mayor_1'] += any(f['cantidad'] > 1 for f in elegidas)
        medida['firma_univoca_eges_todas_informado'] += all(f['estado'] == 'INFORMADO' for f in elegidas)
        medida['firma_univoca_nt_todas_definitivo'] += all(f['estado'] == 'DEFINITIVO' for f in filas)
        patron = tuple(sorted((f['codigo'], f['descripcion']) for f in filas))
        patrones[patron] += 1
        ejemplos.setdefault(patron, {'netterm': resumen_filas(filas), 'eges': resumen_filas(elegidas)})
    # La igualdad de cantidades en una sola fila es una hipotesis distinta.
    singles = Counter()
    for clave, filas in nt_pedidos.items():
        otras = eg_dias.get(clave[:2], [])
        if len(filas) > 1 and len(otras) == 1:
            singles['pedidos_con_una_fila_eges'] += 1
            singles['cantidad_eges_igual_numero_filas_nt'] += otras[0]['cantidad'] == Decimal(len(filas))
    return {'metodo': 'Firmas de multiconjuntos de codigos por pedido vs sesion EGES; evidencia estructural, no identidad clinica confirmada.',
            'archivos': {n: {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()} for n, b in archivos.items()},
            'importacion_eges': {k: v for k, v in importacion.items() if k in {'creadas', 'duplicadas', 'errores', 'insumos_omitidos'}},
            'filas': {'eges_rx': len(eges), 'netterm_rx': len(netterm)},
            'marcas': {origen: {'SUBSIG_amplia': sum(marca(f) for f in fs),
                                'SUBSIGUIENTE_literal': sum('SUBSIGUIENTE' in f['descripcion'] for f in fs)}
                       for origen, fs in [('eges', eges), ('netterm', netterm)]},
            'grupos': dict(medida), 'hipotesis_una_fila_cantidad': dict(singles),
            'muestras_catalogo_sin_identidad': [dict(ejemplos[p], frecuencia_patron=n) for p, n in patrones.most_common(6)],
            'limitaciones': ['No establece unidades/proyecciones a partir de cantidad.',
                             'Igualdad de codigo no certifica estudio ni equivalencia de estados.',
                             'Sesion EGES usa hora, centro, protocolo y numero_turno; campos vacios no prueban una atencion unica.',
                             'No se aplica ninguna correspondencia ni se cambia el conteo.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directorio', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    with tempfile.TemporaryDirectory(prefix='qa-codex-rx-conjuntos-') as temporal:
        db = Path(temporal) / 'qa.sqlite3'
        os.environ['DATABASE_URL'] = 'sqlite:///' + db.as_posix()
        os.environ['DJANGO_SETTINGS_MODULE'] = 'gestion_estudios.settings'
        conexiones = None
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                import django
                django.setup()
                from django.conf import settings
                from django.db import connections
                conexiones = connections
                settings.DEBUG = False
                config = connections['default'].settings_dict
                if config['ENGINE'] != 'django.db.backends.sqlite3' or Path(config['NAME']).resolve() != db.resolve():
                    raise RuntimeError('Se requiere SQLite temporal aislada; operacion cancelada.')
                resultado = analizar(args.directorio)
        finally:
            if conexiones is not None:
                conexiones.close_all()
    resultado['sqlite_temporal_eliminada'] = not Path(temporal).exists()
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
