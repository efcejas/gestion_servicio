"""Parcha api_salida_rapida para soportar tipo entrada/salida."""
path = r'c:\Dev\GitHub\gestion_servicio\control_stock\views_api.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Anclas únicas del bloque
START = '@require_POST\n@login_required\ndef api_salida_rapida(request):'
END_MARKER = "        'bajo_minimo': stock.bajo_minimo,\n    })\n"

idx_start = content.find(START)
if idx_start == -1:
    raise RuntimeError('START no encontrado')

# Buscar el END_MARKER *después* del START
idx_end = content.find(END_MARKER, idx_start)
if idx_end == -1:
    raise RuntimeError('END_MARKER no encontrado')

idx_end += len(END_MARKER)
old_block = content[idx_start:idx_end]

new_block = '''@require_POST
@login_required
def api_salida_rapida(request):
    """
    POST /stock/api/salida-rapida/
    Body JSON: {producto_id: int, area_id: int, cantidad: int, tipo: str, observacion: str}
    Registra una entrada o salida desde la vista de detalle del área sin escanear.
    tipo puede ser 'salida' (default) o 'entrada'.
    """
    if not _check_rol(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    producto_id = body.get('producto_id')
    area_id = body.get('area_id')
    cantidad_raw = body.get('cantidad', 1)
    tipo_mov = (body.get('tipo') or 'salida').strip().lower()

    if tipo_mov not in ('entrada', 'salida'):
        return JsonResponse({'error': 'tipo debe ser "entrada" o "salida"'}, status=400)

    try:
        cantidad = int(cantidad_raw)
        if cantidad <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({'error': 'cantidad debe ser un entero positivo'}, status=400)

    try:
        producto = Producto.objects.get(pk=producto_id)
    except Producto.DoesNotExist:
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)

    try:
        area = AreaServicio.objects.get(pk=area_id, activa=True)
    except AreaServicio.DoesNotExist:
        return JsonResponse({'error': 'Área no encontrada'}, status=404)

    with transaction.atomic():
        stock, _ = StockPorArea.objects.get_or_create(
            producto=producto,
            area=area,
            defaults={'cantidad': 0},
        )

        if tipo_mov == 'salida':
            if stock.cantidad < cantidad:
                return JsonResponse({
                    'error': f'Stock insuficiente. Disponible: {stock.cantidad} {producto.get_unidad_medida_display()}.'
                }, status=400)
            stock.cantidad -= cantidad
        else:
            stock.cantidad += cantidad

        stock.save()

        tipo_obj = MovimientoStock.TIPO_SALIDA if tipo_mov == 'salida' else MovimientoStock.TIPO_ENTRADA
        MovimientoStock.objects.create(
            tipo=tipo_obj,
            producto=producto,
            area=area,
            cantidad=cantidad,
            usuario=request.user,
            observacion=(body.get('observacion') or '').strip(),
        )

    accion = 'Salida' if tipo_mov == 'salida' else 'Entrada'
    return JsonResponse({
        'ok': True,
        'mensaje': f'\u221a {accion} de {cantidad} \u00d7 {producto.nombre}. Stock: {stock.cantidad} {producto.get_unidad_medida_display()}',
        'stock_actual': stock.cantidad,
        'bajo_minimo': stock.bajo_minimo,
    })
'''

content = content.replace(old_block, new_block)
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('OK - api_salida_rapida actualizada')
