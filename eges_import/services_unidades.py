"""Unidades estadísticas de RX conservando las cantidades originales."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation


PARES_RX = {'340301': '340302', '340211': '340212',
            '340209': '340210', '340201': '340202'}
FAMILIAS_RX = {codigo: principal for principal, adicional in PARES_RX.items()
               for codigo in (principal, adicional)}


def unidades_practica(item):
    return item.get('unidades_estadisticas', 1)


def aplicar_unidades_rx(practicas):
    """Absorbe un subsiguiente sólo dentro de un pedido ya vinculado a EGES.

    Una cantidad EGES mayor que uno aporta capacidad. El pedido, paciente,
    fecha y par de códigos deben coincidir y tener un único respaldo posible.
    """
    respaldos = defaultdict(list)
    for item in practicas:
        fila = item['fila']
        item['unidades_estadisticas'] = 1
        if fila['modalidad'] != 'RX' or 'fecha_turno' not in fila:
            continue
        try:
            cantidad = Decimal(str(fila.get('cantidad') or 1))
        except InvalidOperation:
            continue
        if not cantidad.is_finite() or cantidad < 1 or cantidad != cantidad.to_integral_value():
            continue
        item['unidades_estadisticas'] = int(cantidad)
        nt = item.get('netterm')
        if not nt or cantidad <= 1:
            continue
        familia = FAMILIAS_RX.get(str(nt['codigo']).split('/')[0])
        if familia and nt.get('pedido') and fila['paciente_clave']:
            clave = (nt['pedido'], fila['paciente_clave'], item['fecha_produccion'], familia)
            respaldos[clave].append(item)
    resultado = []
    for item in practicas:
        fila = item['fila']
        familia = FAMILIAS_RX.get(str(fila['codigo']).split('/')[0])
        clave = (fila.get('pedido'), fila['paciente_clave'], item['fecha_produccion'], familia)
        candidatas = respaldos.get(clave, [])
        if ('fecha_turno' not in fila and fila['modalidad'] == 'RX'
                and not fila.get('adicional_independiente') and len(candidatas) == 1):
            respaldo = candidatas[0]
            componentes = respaldo.setdefault('componentes_rx_netterm', [])
            if (len(componentes) < unidades_practica(respaldo) - 1
                    and fila['codigo'] != respaldo['netterm']['codigo']):
                componentes.append(fila['id'])
                continue
        resultado.append(item)
    return resultado
