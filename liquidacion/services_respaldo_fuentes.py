"""Respaldo de existencia/autoria: solo lectura, sin recalculo ni validacion economica."""
from collections import Counter, defaultdict
from calendar import monthrange
from datetime import date
import hashlib
import json

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction

from eges_import.models import EgesRow, NettermFila
from eges_import.services_conciliacion import (
    construir_preview_conciliacion, _codigo, _paciente_clave, _texto_normalizado,
)
from eges_import.services_produccion import realizada_eges, realizada_netterm
from .services_eges import _tokens_nombre_medico
from .models import RegistroEstudio, ValidacionRespaldoFuenteRegistro


MAX_REGISTROS_RESPALDO = 10000
MODALIDADES = {'ECO': 'ECO', 'DOP': 'ECO', 'ECOCAR': 'ECO', 'TOM': 'TC',
               'RES': 'RM', 'RAD': 'RX', 'MAM': 'MAM'}
ALIAS_NOMBRE = {
    'ECO ABDOMINAL': 'ECOGRAFIA COMPLETA DE ABDOMEN',
    'ECOGRAFIA ABDOMINAL': 'ECOGRAFIA COMPLETA DE ABDOMEN',
}


def registros_con_respaldo_vigente(sesion):
    """Revalida firmas actuales; un OK guardado no es evidencia perpetua.

    Toda la línea del registro debe estar respaldada en una misma selección.
    No escribe ni certifica cantidades u horarios.
    """
    selecciones = set()
    for validacion in ValidacionRespaldoFuenteRegistro.objects.filter(
        linea_estudio__registro__sesion_contable=sesion,
        linea_estudio__registro__anulado=False,
    ).only('lotes_eges_ids', 'lotes_netterm_ids'):
        selecciones.add((tuple(sorted(validacion.lotes_eges_ids)),
                         tuple(sorted(validacion.lotes_netterm_ids))))
    respaldados = set()
    for eges_ids, netterm_ids in selecciones:
        try:
            preview = construir_preview_respaldo_fuentes(
                sesion=sesion, batch_eges_ids=list(eges_ids), lote_netterm_ids=list(netterm_ids),
            )
        except ValidationError:
            # Una selección borrada, inválida o demasiado grande nunca libera el cierre.
            continue
        for resultado in preview['resultados']:
            if resultado['lineas'] and all(
                linea['estado'] in {'OK_EGES', 'OK_NETTERM'} and linea['validacion_persistida']
                for linea in resultado['lineas']
            ):
                respaldados.add(resultado['registro'].pk)
    return respaldados


def _nombre(valor):
    normalizado = _texto_normalizado(valor)
    return ALIAS_NOMBRE.get(normalizado, normalizado)


def _compatible(relacion, fila):
    if MODALIDADES.get(relacion.estudio.tipo) != fila['modalidad']:
        return None
    codigo = _codigo(relacion.estudio.codigo)
    if codigo and codigo.isascii() and codigo.isdigit():
        # Un codigo numerico diferente nunca se tapa con similitud de palabras.
        return 'CODIGO' if codigo == _codigo(fila['codigo']) else None
    esperado, observado = _nombre(relacion.estudio.nombre), _nombre(fila['practica'])
    return 'NOMBRE_EQUIVALENTE' if esperado and esperado == observado else None


def _medico_coincide(medico, nombres):
    esperado = _tokens_nombre_medico(f'{medico.last_name} {medico.first_name}')
    # No atribuir una practica por un nombre solo, solicitante, tecnico u operador.
    return len(esperado) >= 2 and all((medico.last_name, medico.first_name)) and any(
        esperado.issubset(_tokens_nombre_medico(nombre)) for nombre in nombres
    )


def _snapshot_linea_respaldo(sesion, registro, relacion, linea, firma_fuentes):
    estudio = relacion.estudio
    snapshot = {
        'version_reglas': 'RESPALDO_ORIGEN_V1',
        'firma_fuentes': firma_fuentes,
        'sesion_id': sesion.pk,
        'registro_id': registro.pk,
        'linea_id': relacion.pk,
        'profesional_id': registro.medico_id,
        'paciente_clave': _paciente_clave(registro.dni_paciente),
        'fecha_del_informe': registro.fecha_del_informe,
        'estudio': {
            'id': estudio.pk,
            'tipo': estudio.tipo,
            'codigo': estudio.codigo,
            'nombre': estudio.nombre,
            'cantidad_declarada': relacion.cantidad,
            'cantidad_liquidable': relacion.cantidad_liquidable,
        },
        'estado_respaldo': linea['estado'],
        'evidencia': linea['evidencia'],
    }
    serializado = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str,
    )
    return hashlib.sha256(serializado.encode('utf-8')).hexdigest(), json.loads(serializado)


def construir_preview_respaldo_fuentes(*, sesion, batch_eges_ids, lote_netterm_ids, filtros=None):
    desde = date(sesion.año, sesion.mes, 1)
    hasta = date(sesion.año, sesion.mes, monthrange(sesion.año, sesion.mes)[1])
    registros_qs = sesion.practicas.filter(anulado=False).select_related('medico').prefetch_related(
        'registroestudio_set__estudio',
    ).order_by('fecha_del_informe', 'pk')
    if registros_qs.count() > MAX_REGISTROS_RESPALDO:
        raise ValidationError('La sesión supera el límite de 10000 registros para este respaldo.')
    # Se evalua toda la sesion antes de filtrar/paginar: un filtro no puede ocultar
    # otro registro que pretenda reutilizar la misma evidencia.
    registros = list(registros_qs)
    preview = construir_preview_conciliacion(
        batch_eges_ids=batch_eges_ids, lote_netterm_ids=lote_netterm_ids,
        fecha_desde=desde, fecha_hasta=hasta,
    )
    eg_datos = {f['id']: f for caso in preview['resultados'] for f in caso['eges']}
    nt_casos = {c['netterm']['id']: c for c in preview['resultados'] if c['netterm']}
    eg_medicos = {f.pk: (f.medico_informante, f.medico_actuante)
                  for f in EgesRow.objects.filter(pk__in=eg_datos).only('pk', 'medico_informante', 'medico_actuante')}
    nt_medicos = {f.pk: (f.normalizados_json.get('informante'),)
                  for f in NettermFila.objects.filter(pk__in=nt_casos).only('pk', 'normalizados_json')}
    indice = defaultdict(list)
    for fila in eg_datos.values():
        indice[(fila['paciente_clave'], fila['fecha_turno'])].append({
            **fila, 'origen': 'EGES', 'nombres': eg_medicos[fila['id']],
            'realizada': realizada_eges(fila),
            'bloqueada': _texto_normalizado(fila['estado']) in {'ANULADO', 'CANCELADO'},
            'eges_vinculado': fila['id'],
        })
    for caso in nt_casos.values():
        fila = caso['netterm']
        modalidad = 'ECO' if fila['modalidad'] in {'ECO_GENERAL', 'DOP', 'ECOCAR'} else fila['modalidad']
        indice[(fila['paciente_clave'], fila['fecha_pedido'])].append({
            **fila, 'modalidad': modalidad, 'origen': 'NETTERM', 'nombres': nt_medicos[fila['id']],
            'realizada': realizada_netterm(fila),
            'bloqueada': (fila['vigencia_incierta'] or fila['anulado'] or caso['contradiccion_anulacion']
                          or caso['estado'] == 'AMBIGUO'
                          or (caso['estado'] == 'CONFLICTO' and not caso['identidad_coincidente'])),
            'eges_vinculado': caso['eges'][0]['id'] if caso['identidad_coincidente'] else None,
        })
    candidatos, usuarios_evidencia = {}, defaultdict(set)
    for registro in registros:
        clave = _paciente_clave(registro.dni_paciente)
        for relacion in registro.registroestudio_set.all():
            posibles = []
            if clave:
                for fila in indice.get((clave, registro.fecha_del_informe), []):
                    metodo = _compatible(relacion, fila)
                    if metodo:
                        posibles.append((fila, metodo))
                        usuarios_evidencia[(fila['origen'], fila['id'])].add(relacion.pk)
            candidatos[relacion.pk] = posibles
    resultados = []
    for registro in registros:
        lineas = []
        for relacion in registro.registroestudio_set.all():
            posibles = candidatos[relacion.pk]
            eges = [(f, m) for f, m in posibles if f['origen'] == 'EGES']
            netterm = [(f, m) for f, m in posibles if f['origen'] == 'NETTERM']
            # EGES conserva prioridad. Netterm no levanta una contradiccion EGES
            # de identidad/autoria; complementa su ausencia o falta de realizacion.
            preferidos = eges or netterm
            if len(eges) == 1:
                principal = eges[0][0]
                if (not principal['bloqueada'] and not principal['realizada']
                        and _medico_coincide(registro.medico, principal['nombres'])
                        and len(usuarios_evidencia[('EGES', principal['id'])]) == 1):
                    complemento = [(f, m) for f, m in netterm if f['eges_vinculado'] == principal['id']]
                    if complemento:
                        preferidos = complemento
            estado, fuente, motivos, evidencia = 'SIN_RESPALDO', None, [], []
            reafirmado = False
            if preferidos:
                estado = 'REVISAR'
                if len(preferidos) != 1:
                    motivos.append('Hay varias prácticas posibles; no se elige una repetición arbitrariamente.')
                else:
                    fila, metodo = preferidos[0]
                    medico_ok = _medico_coincide(registro.medico, fila['nombres'])
                    libre = len(usuarios_evidencia[(fila['origen'], fila['id'])]) == 1
                    if not libre:
                        motivos.append('La misma evidencia es candidata para más de una línea profesional.')
                    if fila['bloqueada']:
                        motivos.append('El origen tiene anulación, ambigüedad, vigencia incierta o identidad contradictoria.')
                    if not medico_ok:
                        motivos.append('El informante/actuante no acredita inequívocamente al profesional.')
                    if not fila['realizada']:
                        motivos.append('La realización no está confirmada por el origen.')
                    if libre and not fila['bloqueada'] and medico_ok and fila['realizada']:
                        fuente = fila['origen']
                        estado = f'OK_{fuente}'
                        evidencia = [{'origen': fuente, 'fila_id': fila['id'], 'metodo': metodo}]
                        if fuente == 'EGES':
                            complementos = [f for f, _ in netterm if f['eges_vinculado'] == fila['id']
                                            and not f['bloqueada'] and f['realizada']]
                            reafirmado = len(complementos) == 1
                            if reafirmado:
                                evidencia.append({'origen': 'NETTERM', 'fila_id': complementos[0]['id'], 'metodo': 'CORRESPONDENCIA_ORIGEN'})
                                if not _medico_coincide(registro.medico, complementos[0]['nombres']):
                                    motivos.append('Netterm difiere en informante; conserva el respaldo EGES.')
            else:
                motivos.append('Sin correspondencia inequívoca por DNI, fecha y código o nombre equivalente.')
            lineas.append({
                'relacion_id': relacion.pk, 'practica': relacion.estudio.nombre,
                'cantidad_declarada': relacion.cantidad, 'estado': estado, 'fuente': fuente,
                'reafirmado_netterm': reafirmado, 'motivos': motivos, 'evidencia': evidencia,
                'cantidad_economica_validada': False, 'horario_economico_validado': False,
            })
            firma_validacion, snapshot_validacion = _snapshot_linea_respaldo(
                sesion, registro, relacion, lineas[-1], preview['firma_snapshot'],
            )
            lineas[-1]['firma_validacion'] = firma_validacion
            lineas[-1]['snapshot_validacion'] = snapshot_validacion
        ok = sum(l['estado'].startswith('OK_') for l in lineas)
        estado = ('OK_RESPALDO' if lineas and ok == len(lineas) else 'PARCIAL' if ok
                  else 'REVISAR' if any(l['estado'] == 'REVISAR' for l in lineas) else 'SIN_RESPALDO')
        resultados.append({'registro': registro, 'estado_respaldo': estado, 'lineas': lineas})
    lineas_por_clave = {
        (linea['relacion_id'], linea['firma_validacion']): linea
        for resultado in resultados for linea in resultado['lineas']
    }
    if lineas_por_clave:
        validaciones = ValidacionRespaldoFuenteRegistro.objects.filter(
            linea_estudio_id__in={linea_id for linea_id, _ in lineas_por_clave},
            firma_fuentes=preview['firma_snapshot'],
        ).select_related('validado_por')
        for validacion in validaciones:
            linea = lineas_por_clave.get((validacion.linea_estudio_id, validacion.firma_snapshot))
            if linea:
                linea['validacion_persistida'] = validacion
    for linea in lineas_por_clave.values():
        linea.setdefault('validacion_persistida', None)
    filtros = filtros or {}
    # Estos filtros afectan solo la presentacion, nunca la unicidad de la evidencia.
    if filtros.get('profesional'):
        resultados = [r for r in resultados if str(r['registro'].medico_id) == str(filtros['profesional'])]
    if filtros.get('estado_respaldo'):
        resultados = [r for r in resultados if r['estado_respaldo'] == filtros['estado_respaldo']]
    resumen = Counter(r['estado_respaldo'] for r in resultados)
    return {
        'version_reglas': 'RESPALDO_ORIGEN_V1', 'sesion': sesion, 'resultados': resultados,
        'resumen': dict(resumen), 'total': len(resultados), 'modifica_valores_economicos': False,
        'firma_fuentes': preview['firma_snapshot'],
        'batch_eges_ids': preview['batch_eges_ids'], 'lote_netterm_ids': preview['lote_netterm_ids'],
    }


def registrar_validacion_respaldo_fuente(
    *, sesion, linea_id, batch_eges_ids, lote_netterm_ids, firma_esperada, usuario,
):
    try:
        linea_id = int(linea_id)
    except (TypeError, ValueError):
        raise ValidationError('La línea profesional indicada no es válida.') from None
    if not isinstance(firma_esperada, str) or len(firma_esperada) != 64:
        raise ValidationError('La firma del respaldo no es válida; vuelve a cargar la consulta.')

    try:
        with transaction.atomic():
            relacion = RegistroEstudio.objects.select_for_update().filter(
                pk=linea_id,
                registro__sesion_contable=sesion,
                registro__anulado=False,
            ).select_related('registro', 'estudio').first()
            if relacion is None:
                raise ValidationError('La línea profesional ya no pertenece a esta sesión.')
            preview = construir_preview_respaldo_fuentes(
                sesion=sesion,
                batch_eges_ids=batch_eges_ids,
                lote_netterm_ids=lote_netterm_ids,
            )
            linea = next((
                linea
                for resultado in preview['resultados']
                for linea in resultado['lineas']
                if linea['relacion_id'] == relacion.pk
            ), None)
            if linea is None or linea['estado'] not in {'OK_EGES', 'OK_NETTERM'}:
                raise ValidationError('La línea ya no tiene respaldo inequívoco para validar.')
            if linea['firma_validacion'] != firma_esperada:
                raise ValidationError('Las fuentes o el registro cambiaron; vuelve a cargar el preview.')
            validacion, creada = _persistir_validacion_respaldo(relacion, linea, preview, usuario)
            return validacion, creada
    except IntegrityError:
        validacion = ValidacionRespaldoFuenteRegistro.objects.filter(
            linea_estudio_id=linea_id,
            firma_snapshot=firma_esperada,
        ).first()
        if validacion:
            return validacion, False
        raise ValidationError('La validación cambió en paralelo; vuelve a cargar el preview.') from None


def _persistir_validacion_respaldo(relacion, linea, preview, usuario):
    return ValidacionRespaldoFuenteRegistro.objects.get_or_create(
        linea_estudio=relacion,
        firma_snapshot=linea['firma_validacion'],
        defaults={
            'firma_fuentes': preview['firma_fuentes'],
            'version_reglas': preview['version_reglas'],
            'lotes_eges_ids': preview['batch_eges_ids'],
            'lotes_netterm_ids': preview['lote_netterm_ids'],
            'evidencia_json': linea['evidencia'],
            'snapshot_json': linea['snapshot_validacion'],
            'validado_por': usuario,
        },
    )


def registrar_validaciones_respaldo_fuentes(
    *, sesion, linea_ids, batch_eges_ids, lote_netterm_ids, firma_fuentes_esperada,
    pagina, filtros=None, usuario,
):
    try:
        ids = [int(value) for value in linea_ids]
        pagina = int(pagina)
    except (TypeError, ValueError):
        raise ValidationError('La selección de líneas no es válida.') from None
    if not ids or len(ids) > 50 or len(ids) != len(set(ids)):
        raise ValidationError('Selecciona entre 1 y 50 líneas distintas de esta página.')
    if pagina < 1:
        raise ValidationError('La página seleccionada no es válida.')

    creadas = 0
    existentes = 0
    try:
        with transaction.atomic():
            relaciones_bloqueadas = list(RegistroEstudio.objects.select_for_update().filter(
                pk__in=ids,
                registro__sesion_contable=sesion,
                registro__anulado=False,
            ).values_list('pk', flat=True))
            if len(relaciones_bloqueadas) != len(ids):
                raise ValidationError('Una o más líneas ya no pertenecen a esta sesión.')
            relaciones_por_id = {
                relacion.pk: relacion
                for relacion in RegistroEstudio.objects.filter(pk__in=relaciones_bloqueadas).select_related(
                    'registro', 'estudio',
                )
            }
            preview = construir_preview_respaldo_fuentes(
                sesion=sesion,
                batch_eges_ids=batch_eges_ids,
                lote_netterm_ids=lote_netterm_ids,
                filtros=filtros,
            )
            if preview['firma_fuentes'] != firma_fuentes_esperada:
                raise ValidationError('Las fuentes cambiaron; vuelve a cargar el preview antes de confirmar.')
            pagina_actual = Paginator(preview['resultados'], 50).get_page(pagina)
            lineas_visibles = {
                linea['relacion_id']: linea
                for resultado in pagina_actual.object_list
                for linea in resultado['lineas']
            }
            if any(linea_id not in lineas_visibles for linea_id in ids):
                raise ValidationError('La selección contiene líneas que no están visibles en esta página.')
            if any(lineas_visibles[linea_id]['estado'] not in {'OK_EGES', 'OK_NETTERM'} for linea_id in ids):
                raise ValidationError('Solo se pueden confirmar líneas con OK inequívoco de respaldo.')
            for linea_id in ids:
                _, creada = _persistir_validacion_respaldo(
                    relaciones_por_id[linea_id], lineas_visibles[linea_id], preview, usuario,
                )
                creadas += int(creada)
                existentes += int(not creada)
    except IntegrityError:
        raise ValidationError('Una o más líneas se confirmaron en paralelo; vuelve a cargar la página.') from None
    return {'creadas': creadas, 'existentes': existentes, 'total': len(ids)}
