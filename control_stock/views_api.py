"""
Endpoints JSON para el escáner de stock:
  - api_buscar_producto        GET  ?codigo=<barras>&area_id=<int>
  - api_analizar_foto          POST {imagen_base64, area_id}
  - api_registrar_movimiento   POST {codigo_barras, area_id, tipo, cantidad, numero_lote, fecha_vencimiento, ...}
  - api_anular_movimiento      POST /api/anular/<mov_id>/
  - api_salida_rapida          POST {producto_id, area_id, cantidad, tipo}
  - api_lotes_producto         GET  ?producto_id=<int>&area_id=<int>
  - api_uso_rapido             POST {lote_id, cantidad, observacion}
  - api_buscar_global          GET  ?q=<string>
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from django.db.models import Sum
from .models import Producto, AreaServicio, StockPorArea, LoteEnArea, MovimientoStock
from .services import buscar_en_api_externa, analizar_foto_producto

logger = logging.getLogger(__name__)

# Roles que pueden operar stock
ROLES_STOCK = (
    'medico_staff', 'medico_residente', 'jefe_residentes',
    'instructor_residentes', 'jefe_servicio', 'cardiologo',
    'tecnico', 'enfermeria',
)


def _check_rol(request):
    return request.user.is_superuser or getattr(request.user, 'rol', None) in ROLES_STOCK


@require_GET
@login_required
def api_buscar_producto(request):
    """
    GET /stock/api/buscar/?codigo=<barras>
    Busca primero en la DB local, luego en UPCItemDB.
    """
    if not _check_rol(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'error': 'Se requiere el parámetro "codigo"'}, status=400)

    area_id_qs = request.GET.get('area_id', '').strip()

    def _stock_en_area(producto_obj):
        """Retorna la cantidad en stock para el área solicitada, o None si no se pidió."""
        if not area_id_qs:
            return None
        try:
            s = StockPorArea.objects.get(producto=producto_obj, area_id=int(area_id_qs))
            return s.cantidad
        except (StockPorArea.DoesNotExist, ValueError):
            return 0

    # 1. Buscar en la base de datos local
    try:
        producto = Producto.objects.get(codigo_barras=codigo)
        return JsonResponse({
            'encontrado': True,
            'es_nuevo': False,
            'fuente': 'local',
            'stock_en_area': _stock_en_area(producto),
            'producto': {
                'id': producto.id,
                'codigo_barras': producto.codigo_barras,
                'nombre': producto.nombre,
                'descripcion': producto.descripcion,
                'categoria': producto.categoria,
                'unidad_medida': producto.unidad_medida,
                'stock_minimo': producto.stock_minimo,
                'imagen_url': producto.imagen_url,
            },
        })
    except Producto.DoesNotExist:
        pass

    # 2. Consultar API externa
    datos_api = buscar_en_api_externa(codigo)
    if datos_api:
        return JsonResponse({
            'encontrado': True,
            'es_nuevo': True,
            'fuente': 'api_externa',
            'stock_en_area': None,
            'producto': {
                'id': None,
                'codigo_barras': codigo,
                'nombre': datos_api.get('nombre', ''),
                'descripcion': datos_api.get('descripcion', ''),
                'categoria': 'otro',
                'unidad_medida': 'unidad',
                'stock_minimo': 0,
                'imagen_url': datos_api.get('imagen_url', ''),
            },
        })

    # 3. Producto desconocido
    return JsonResponse({
        'encontrado': False,
        'es_nuevo': True,
        'fuente': None,
        'stock_en_area': None,
        'producto': {
            'id': None,
            'codigo_barras': codigo,
            'nombre': '',
            'descripcion': '',
            'categoria': 'descartable',
            'unidad_medida': 'unidad',
            'stock_minimo': 0,
            'imagen_url': '',
        },
    })


@require_POST
@login_required
def api_analizar_foto(request):
    """
    POST /stock/api/analizar-foto/
    Body JSON: {imagen_base64: string, area_id: int (opcional)}
    Llama a GPT-4o-mini Vision y retorna datos extraídos del packaging.
    """
    if not _check_rol(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    imagen_base64 = body.get('imagen_base64', '').strip()
    if not imagen_base64:
        return JsonResponse({'error': 'Se requiere imagen_base64'}, status=400)

    # Validación básica: la cadena debe ser razonablemente larga para ser una imagen
    # Eliminar prefix data URI para medir
    raw = imagen_base64.split(',', 1)[-1]
    if len(raw) < 100:
        return JsonResponse({'error': 'Imagen inválida o demasiado pequeña'}, status=400)

    resultado = analizar_foto_producto(imagen_base64)

    # Si se detectó un código de barras, buscar también en la DB local
    area_id_body = body.get('area_id')
    producto_local = None

    def _build_producto_local(p, es_sugerencia=False):
        stock_en_area = None
        if area_id_body:
            try:
                s = StockPorArea.objects.get(producto=p, area_id=int(area_id_body))
                stock_en_area = s.cantidad
            except (StockPorArea.DoesNotExist, ValueError):
                stock_en_area = 0
        return {
            'id': p.id,
            'codigo_barras': p.codigo_barras,
            'nombre': p.nombre,
            'descripcion': p.descripcion,
            'categoria': p.categoria,
            'unidad_medida': p.unidad_medida,
            'stock_minimo': p.stock_minimo,
            'imagen_url': p.imagen_url,
            'stock_en_area': stock_en_area,
            'es_sugerencia': es_sugerencia,
        }

    if resultado.get('codigo_barras'):
        try:
            p = Producto.objects.get(codigo_barras=resultado['codigo_barras'])
            producto_local = _build_producto_local(p, es_sugerencia=False)
        except Producto.DoesNotExist:
            pass

    # Fallback: buscar por nombre si la IA no detectó código o no lo encontró en DB
    if not producto_local and resultado.get('nombre'):
        nombre_ia = resultado['nombre'].strip()
        if nombre_ia:
            from django.db.models import Q
            # Búsqueda exacta por nombre completo
            p = Producto.objects.filter(nombre__icontains=nombre_ia).first()
            if not p:
                # Búsqueda por las palabras significativas (≥4 chars)
                palabras = [w for w in nombre_ia.split() if len(w) >= 4]
                if palabras:
                    q = Q()
                    for palabra in palabras[:3]:
                        q |= Q(nombre__icontains=palabra)
                    p = Producto.objects.filter(q).first()
            if p:
                producto_local = _build_producto_local(p, es_sugerencia=True)

    return JsonResponse({
        'ia_resultado': resultado,
        'producto_local': producto_local,
    })


@require_POST
@login_required
def api_registrar_movimiento(request):
    """
    POST /stock/api/movimiento/
    Registra una ENTRADA o SALIDA, gestionando el LoteEnArea correspondiente.

    Body JSON:
    {
        codigo_barras, area_id, tipo ('entrada'|'salida'|'uso'|'descarte'|'ajuste'),
        cantidad, observacion, fecha_vencimiento ('YYYY-MM-DD'), numero_lote,
        # Si producto es nuevo:
        nombre, descripcion, categoria, unidad_medida, stock_minimo, imagen_url
    }
    """
    if not _check_rol(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    codigo_barras = (body.get('codigo_barras') or '').strip()
    area_id       = body.get('area_id')
    tipo          = (body.get('tipo') or '').strip()
    cantidad_raw  = body.get('cantidad')

    # Para ajuste/descarte: si no viene codigo_barras pero sí lote_id, resolver producto y área desde el lote
    if not codigo_barras and tipo in ('ajuste', 'descarte') and body.get('lote_id'):
        try:
            _lote_ref = LoteEnArea.objects.select_related('stock__producto', 'stock__area').get(pk=body.get('lote_id'))
            codigo_barras = _lote_ref.stock.producto.codigo_barras
            if not area_id:
                area_id = _lote_ref.stock.area_id
        except LoteEnArea.DoesNotExist:
            return JsonResponse({'error': 'Lote no encontrado.'}, status=404)

    if not codigo_barras:
        return JsonResponse({'error': 'Se requiere codigo_barras'}, status=400)

    TIPOS_VALIDOS = {
        MovimientoStock.TIPO_ENTRADA, MovimientoStock.TIPO_SALIDA,
        MovimientoStock.TIPO_USO, MovimientoStock.TIPO_DESCARTE, MovimientoStock.TIPO_AJUSTE,
    }
    if tipo not in TIPOS_VALIDOS:
        return JsonResponse({'error': f'tipo inválido. Opciones: {", ".join(TIPOS_VALIDOS)}'}, status=400)

    # Descarte/ajuste requieren motivo
    if tipo in MovimientoStock.TIPOS_REQUIEREN_MOTIVO:
        if not (body.get('observacion') or '').strip():
            return JsonResponse({'error': f'El tipo "{tipo}" requiere ingresar un motivo en observación'}, status=400)
        # Solo roles autorizados pueden descartar/ajustar
        rol = getattr(request.user, 'rol', None)
        if not request.user.is_superuser and rol not in MovimientoStock.ROLES_PUEDEN_DESCARTAR:
            return JsonResponse({'error': 'Sin permisos para descartar o ajustar inventario'}, status=403)

    try:
        cantidad = int(cantidad_raw)
        if cantidad <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({'error': 'cantidad debe ser un entero positivo'}, status=400)

    try:
        area = AreaServicio.objects.get(pk=area_id, activa=True)
    except AreaServicio.DoesNotExist:
        return JsonResponse({'error': 'Área no encontrada o inactiva'}, status=404)

    producto, creado = Producto.objects.get_or_create(
        codigo_barras=codigo_barras,
        defaults={
            'nombre': body.get('nombre', codigo_barras),
            'descripcion': body.get('descripcion', ''),
            'categoria': body.get('categoria', 'descartable'),
            'unidad_medida': body.get('unidad_medida', 'unidad'),
            'stock_minimo': int(body.get('stock_minimo', 0) or 0),
            'imagen_url': body.get('imagen_url', ''),
            'creado_por': request.user,
        },
    )

    from datetime import date as date_type
    fecha_vencimiento = None
    raw_fecha = (body.get('fecha_vencimiento') or '').strip()
    if raw_fecha:
        try:
            fecha_vencimiento = date_type.fromisoformat(raw_fecha)
        except ValueError:
            pass

    numero_lote = (body.get('numero_lote') or '').strip()
    es_entrada  = tipo == MovimientoStock.TIPO_ENTRADA
    es_salida   = tipo in (MovimientoStock.TIPO_SALIDA, MovimientoStock.TIPO_USO,
                           MovimientoStock.TIPO_DESCARTE)
    es_ajuste   = tipo == MovimientoStock.TIPO_AJUSTE
    # Para ajuste: incremento=True → suma al lote; incremento=False → resta del lote
    ajuste_incremento = bool(body.get('incremento', False))

    with transaction.atomic():
        stock, _ = StockPorArea.objects.select_for_update().get_or_create(
            producto=producto, area=area, defaults={'cantidad': 0},
        )

        lote_obj = None

        if es_entrada:
            # Buscar lote existente con mismo número y fecha, o crear uno nuevo
            lote_obj, _ = LoteEnArea.objects.get_or_create(
                stock=stock,
                numero_lote=numero_lote,
                fecha_vencimiento=fecha_vencimiento,
                defaults={'cantidad': 0, 'activo': True},
            )
            lote_obj.cantidad += cantidad
            lote_obj.activo = True
            lote_obj.save(update_fields=['cantidad', 'activo'])

        elif es_salida:
            if stock.cantidad < cantidad:
                return JsonResponse({
                    'error': f'Stock insuficiente. Disponible: {stock.cantidad} {producto.get_unidad_medida_display()}.'
                }, status=400)

            # Descontar del lote más próximo a vencer (FEFO)
            # Si se indica lote específico, descontar de ese; si no, FEFO automático
            lote_id_solicitado = body.get('lote_id')
            restante = cantidad

            if lote_id_solicitado:
                try:
                    lote_obj = LoteEnArea.objects.select_for_update().get(
                        pk=lote_id_solicitado, stock=stock, activo=True
                    )
                    if lote_obj.cantidad < restante:
                        return JsonResponse({
                            'error': f'El lote seleccionado solo tiene {lote_obj.cantidad} unidades.'
                        }, status=400)
                    lote_obj.cantidad -= restante
                    if lote_obj.cantidad == 0:
                        lote_obj.activo = False
                    lote_obj.save(update_fields=['cantidad', 'activo'])
                    restante = 0
                except LoteEnArea.DoesNotExist:
                    return JsonResponse({'error': 'Lote no encontrado en este área'}, status=404)
            else:
                # FEFO: lotes con fecha primero, luego sin fecha; ambos ordenados por creado_en
                lotes_fefo = LoteEnArea.objects.select_for_update().filter(
                    stock=stock, activo=True
                ).order_by(
                    models.Case(
                        models.When(fecha_vencimiento__isnull=True, then=1),
                        default=0,
                        output_field=models.IntegerField(),
                    ),
                    'fecha_vencimiento', 'creado_en'
                )
                for lote in lotes_fefo:
                    if restante <= 0:
                        break
                    descuento = min(lote.cantidad, restante)
                    lote.cantidad -= descuento
                    if lote.cantidad == 0:
                        lote.activo = False
                    lote.save(update_fields=['cantidad', 'activo'])
                    restante -= descuento
                    if lote_obj is None:
                        lote_obj = lote  # para el movimiento, guardar el primer lote tocado

        elif es_ajuste:
            # Ajuste de inventario sobre un lote específico obligatorio
            lote_id_solicitado = body.get('lote_id')
            if not lote_id_solicitado:
                return JsonResponse({'error': 'El ajuste requiere indicar el lote.'}, status=400)
            try:
                lote_obj = LoteEnArea.objects.select_for_update().get(
                    pk=lote_id_solicitado, stock=stock
                )
            except LoteEnArea.DoesNotExist:
                return JsonResponse({'error': 'Lote no encontrado en este área.'}, status=404)

            if ajuste_incremento:
                lote_obj.cantidad += cantidad
                lote_obj.activo = True
            else:
                if lote_obj.cantidad < cantidad:
                    return JsonResponse({
                        'error': f'El lote solo tiene {lote_obj.cantidad} unidades; no se puede restar {cantidad}.'
                    }, status=400)
                lote_obj.cantidad -= cantidad
                if lote_obj.cantidad == 0:
                    lote_obj.activo = False
            lote_obj.save(update_fields=['cantidad', 'activo'])

        # Recalcular el total agregado
        stock.recalcular()

        mov = MovimientoStock.objects.create(
            tipo=tipo,
            lote=lote_obj,
            producto=producto,
            area=area,
            cantidad=cantidad,
            usuario=request.user,
            observacion=(body.get('observacion') or '').strip(),
            fecha_vencimiento=fecha_vencimiento,
            numero_lote=numero_lote,
        )

    verbo = {'entrada': 'Entrada', 'salida': 'Salida', 'uso': 'Uso',
             'descarte': 'Descarte', 'ajuste': 'Ajuste'}.get(tipo, tipo.capitalize())
    return JsonResponse({
        'ok': True,
        'mensaje': f'{verbo} registrado: {cantidad} × {producto.nombre} — Stock: {stock.cantidad} {producto.get_unidad_medida_display()}',
        'stock_actual': stock.cantidad,
        'bajo_minimo': stock.bajo_minimo,
        'producto_creado': creado,
        'movimiento_id': mov.pk,
    })


@require_POST
@login_required
def api_anular_movimiento(request, mov_id):
    """
    POST /stock/api/anular/<mov_id>/
    Anula un movimiento revirtiendo el efecto sobre el lote y el stock total.
    Permisos: propio usuario en ventana de 24 h, o rol autorizado siempre.
    """
    if not _check_rol(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    try:
        mov = MovimientoStock.objects.select_related('producto', 'area', 'lote').get(pk=mov_id)
    except MovimientoStock.DoesNotExist:
        return JsonResponse({'error': 'Movimiento no encontrado'}, status=404)

    if not mov.puede_anular(request.user):
        if mov.anulado:
            return JsonResponse({'error': 'Este movimiento ya fue anulado'}, status=400)
        return JsonResponse({'error': 'No tenés permiso para anular este movimiento'}, status=403)

    es_entrada = mov.tipo == MovimientoStock.TIPO_ENTRADA
    tipo_inverso = MovimientoStock.TIPO_SALIDA if es_entrada else MovimientoStock.TIPO_ENTRADA

    with transaction.atomic():
        stock = StockPorArea.objects.select_for_update().get(
            producto=mov.producto, area=mov.area
        )

        # Revertir sobre el lote si existe
        if mov.lote:
            lote = LoteEnArea.objects.select_for_update().get(pk=mov.lote_id)
            if es_entrada:
                # Anular entrada = quitar del lote
                lote.cantidad = max(0, lote.cantidad - mov.cantidad)
                lote.activo = lote.cantidad > 0
            else:
                # Anular salida/uso = devolver al lote
                lote.cantidad += mov.cantidad
                lote.activo = True
            lote.save(update_fields=['cantidad', 'activo'])
        else:
            # Movimiento legacy sin lote: operar directamente sobre el total
            if tipo_inverso == MovimientoStock.TIPO_SALIDA:
                if stock.cantidad < mov.cantidad:
                    return JsonResponse({
                        'error': f'No se puede anular: stock actual ({stock.cantidad}) < cantidad a descontar ({mov.cantidad}).'
                    }, status=400)

        stock.recalcular()

        MovimientoStock.objects.create(
            tipo=tipo_inverso,
            lote=mov.lote,
            producto=mov.producto,
            area=mov.area,
            cantidad=mov.cantidad,
            usuario=request.user,
            observacion=f'Anulación de movimiento #{mov.pk}',
            anulacion_de=mov,
        )
        mov.anulado = True
        mov.save(update_fields=['anulado'])

    return JsonResponse({
        'ok': True,
        'mensaje': f'Movimiento anulado. Stock actual: {stock.cantidad} {mov.producto.get_unidad_medida_display()}',
        'stock_actual': stock.cantidad,
        'bajo_minimo': stock.bajo_minimo,
    })


@require_POST
@login_required
def api_salida_rapida(request):
    """
    POST /stock/api/salida-rapida/
    Body JSON: {producto_id, area_id, cantidad, tipo ('salida'|'entrada'|'uso'), observacion}
    Registra movimiento desde detalle_area sin escanear; usa FEFO automático.
    """
    if not _check_rol(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    producto_id = body.get('producto_id')
    area_id     = body.get('area_id')
    cantidad_raw = body.get('cantidad', 1)
    tipo_mov    = (body.get('tipo') or 'uso').strip().lower()

    TIPOS_SALIDA_VALIDOS = ('salida', 'uso')
    TIPOS_ENTRADA_VALIDOS = ('entrada',)
    if tipo_mov not in TIPOS_SALIDA_VALIDOS + TIPOS_ENTRADA_VALIDOS:
        return JsonResponse({'error': 'tipo debe ser "uso", "salida" o "entrada"'}, status=400)

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
        stock = StockPorArea.objects.select_for_update().filter(
            producto=producto, area=area
        ).first()
        if not stock:
            stock = StockPorArea.objects.create(producto=producto, area=area, cantidad=0)

        lote_obj = None

        if tipo_mov in TIPOS_SALIDA_VALIDOS:
            if stock.cantidad < cantidad:
                return JsonResponse({
                    'error': f'Stock insuficiente. Disponible: {stock.cantidad} {producto.get_unidad_medida_display()}.'
                }, status=400)
            # FEFO automático
            restante = cantidad
            lotes_fefo = LoteEnArea.objects.select_for_update().filter(
                stock=stock, activo=True
            ).order_by(
                models.Case(
                    models.When(fecha_vencimiento__isnull=True, then=1),
                    default=0,
                    output_field=models.IntegerField(),
                ),
                'fecha_vencimiento', 'creado_en'
            )
            for lote in lotes_fefo:
                if restante <= 0:
                    break
                descuento = min(lote.cantidad, restante)
                lote.cantidad -= descuento
                if lote.cantidad == 0:
                    lote.activo = False
                lote.save(update_fields=['cantidad', 'activo'])
                restante -= descuento
                if lote_obj is None:
                    lote_obj = lote
        else:
            # Entrada: crear/actualizar lote genérico (sin lote/fecha)
            lote_obj, _ = LoteEnArea.objects.get_or_create(
                stock=stock, numero_lote='', fecha_vencimiento=None,
                defaults={'cantidad': 0, 'activo': True},
            )
            lote_obj.cantidad += cantidad
            lote_obj.activo = True
            lote_obj.save(update_fields=['cantidad', 'activo'])

        stock.recalcular()

        tipo_constante = {
            'salida': MovimientoStock.TIPO_SALIDA,
            'uso':    MovimientoStock.TIPO_USO,
            'entrada': MovimientoStock.TIPO_ENTRADA,
        }[tipo_mov]

        mov = MovimientoStock.objects.create(
            tipo=tipo_constante,
            lote=lote_obj,
            producto=producto,
            area=area,
            cantidad=cantidad,
            usuario=request.user,
            observacion=(body.get('observacion') or '').strip(),
        )

    accion = {'salida': 'Salida', 'uso': 'Uso registrado', 'entrada': 'Entrada'}[tipo_mov]
    return JsonResponse({
        'ok': True,
        'mensaje': f'{accion}: {cantidad} × {producto.nombre}. Stock: {stock.cantidad} {producto.get_unidad_medida_display()}',
        'stock_actual': stock.cantidad,
        'bajo_minimo': stock.bajo_minimo,
        'movimiento_id': mov.pk,
    })


@require_GET
@login_required
def api_lotes_producto(request):
    """
    GET /stock/api/lotes/?producto_id=<int>&area_id=<int>
    Retorna los lotes activos de un producto en un área, ordenados FEFO.
    Usado por el modal del escáner y el drawer de detalle_area.
    """
    if not _check_rol(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    producto_id = request.GET.get('producto_id')
    area_id     = request.GET.get('area_id')

    if not producto_id or not area_id:
        return JsonResponse({'error': 'Se requieren producto_id y area_id'}, status=400)

    try:
        stock = StockPorArea.objects.get(producto_id=int(producto_id), area_id=int(area_id))
    except (StockPorArea.DoesNotExist, ValueError):
        return JsonResponse({'lotes': [], 'stock_total': 0})

    from django.db import models as dj_models
    lotes = LoteEnArea.objects.filter(stock=stock, activo=True).order_by(
        dj_models.Case(
            dj_models.When(fecha_vencimiento__isnull=True, then=1),
            default=0,
            output_field=dj_models.IntegerField(),
        ),
        'fecha_vencimiento', 'creado_en'
    )

    from django.utils import timezone as tz
    hoy = tz.now().date()

    lotes_data = []
    for l in lotes:
        vencido    = bool(l.fecha_vencimiento and l.fecha_vencimiento < hoy)
        vence_hoy  = bool(l.fecha_vencimiento and l.fecha_vencimiento == hoy)
        vence_pronto = bool(
            l.fecha_vencimiento and not vencido and not vence_hoy
            and l.fecha_vencimiento <= hoy + tz.timedelta(days=30)
        )
        lotes_data.append({
            'id': l.pk,
            'numero_lote': l.numero_lote or '',
            'fecha_vencimiento': l.fecha_vencimiento.isoformat() if l.fecha_vencimiento else None,
            'cantidad': l.cantidad,
            'vencido': vencido,
            'vence_hoy': vence_hoy,
            'vence_pronto': vence_pronto,
        })

    return JsonResponse({
        'lotes': lotes_data,
        'stock_total': stock.cantidad,
        'producto_nombre': stock.producto.nombre,
        'unidad': stock.producto.get_unidad_medida_display(),
    })


# ── Fase 1: buscador global ────────────────────────────────────
@require_GET
@login_required
def api_buscar_global(request):
    if not _check_rol(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'resultados': []})

    stocks = StockPorArea.objects.filter(
        producto__nombre__icontains=q,
        area__activa=True,
    ).select_related('producto', 'area').order_by('producto__nombre', 'area__nombre')

    productos: dict = {}
    for s in stocks:
        pid = s.producto.id
        if pid not in productos:
            productos[pid] = {
                'id': pid,
                'nombre': s.producto.nombre,
                'categoria': s.producto.get_categoria_display(),
                'unidad': s.producto.get_unidad_medida_display(),
                'codigo_barras': s.producto.codigo_barras,
                'stocks': [],
            }
        productos[pid]['stocks'].append({
            'area_id': s.area.id,
            'area_nombre': s.area.nombre,
            'cantidad': s.cantidad,
            'bajo_minimo': s.bajo_minimo,
        })

    return JsonResponse({'resultados': list(productos.values())})


# ── Fase D: búsqueda por nombre para el escáner ────────────────
@require_GET
@login_required
def api_buscar_por_nombre(request):
    """
    GET /stock/api/buscar-nombre/?q=<texto>&area_id=<int>
    Devuelve hasta 15 productos cuyo nombre contiene el texto.
    Misma estructura por item que la respuesta de api_buscar_producto.
    """
    if not _check_rol(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'resultados': []})

    area_id_qs = request.GET.get('area_id', '').strip()

    productos = Producto.objects.filter(nombre__icontains=q).order_by('nombre')[:15]

    resultados = []
    for p in productos:
        stock_en_area = None
        if area_id_qs:
            try:
                s = StockPorArea.objects.get(producto=p, area_id=int(area_id_qs))
                stock_en_area = s.cantidad
            except (StockPorArea.DoesNotExist, ValueError):
                stock_en_area = 0
        resultados.append({
            'id': p.id,
            'nombre': p.nombre,
            'codigo_barras': p.codigo_barras,
            'categoria': p.categoria,
            'unidad_medida': p.unidad_medida,
            'stock_en_area': stock_en_area,
            'imagen_url': p.imagen_url or '',
        })

    return JsonResponse({'resultados': resultados})


@require_POST
@login_required
def api_reportar_lote(request):
    """
    POST /stock/api/reportar-lote/
    Cualquier usuario autenticado puede reportar un lote como candidato a descarte.
    Body JSON: {lote_id: int}
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    lote_id = body.get('lote_id')
    if not lote_id:
        return JsonResponse({'error': 'Se requiere lote_id'}, status=400)

    try:
        lote = LoteEnArea.objects.select_related('stock__producto', 'stock__area').get(pk=lote_id)
    except LoteEnArea.DoesNotExist:
        return JsonResponse({'error': 'Lote no encontrado'}, status=404)

    lote.reportado_para_descarte = True
    lote.reportado_por = request.user
    lote.reportado_en = timezone.now()
    lote.save(update_fields=['reportado_para_descarte', 'reportado_por', 'reportado_en'])

    return JsonResponse({
        'ok': True,
        'mensaje': f'Lote de {lote.stock.producto.nombre} reportado para descarte.',
    })


@require_POST
@login_required
def api_descarte_masivo(request):
    """
    POST /stock/api/descarte-masivo/
    Descarta múltiples lotes en una sola operación.
    Body JSON: {lote_ids: [int, ...], observacion: str}
    Solo roles autorizados (misma lógica que api_registrar_movimiento para descarte).
    """
    if not _check_rol(request):
        return JsonResponse({'error': 'Sin permisos'}, status=403)

    rol = getattr(request.user, 'rol', None)
    if not request.user.is_superuser and rol not in MovimientoStock.ROLES_PUEDEN_DESCARTAR:
        return JsonResponse({'error': 'Sin permisos para descartar inventario'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    lote_ids = body.get('lote_ids', [])
    observacion = (body.get('observacion') or '').strip()

    if not lote_ids:
        return JsonResponse({'error': 'Se requiere al menos un lote_id'}, status=400)
    if not observacion:
        return JsonResponse({'error': 'Se requiere un motivo para el descarte'}, status=400)
    if len(lote_ids) > 50:
        return JsonResponse({'error': 'Máximo 50 lotes por operación'}, status=400)

    descartados = 0
    errores = []

    with transaction.atomic():
        for lote_id in lote_ids:
            try:
                lote = LoteEnArea.objects.select_for_update().select_related(
                    'stock__producto', 'stock__area'
                ).get(pk=lote_id, activo=True)

                cantidad = lote.cantidad
                lote.cantidad = 0
                lote.activo = False
                lote.reportado_para_descarte = False
                lote.save(update_fields=['cantidad', 'activo', 'reportado_para_descarte'])

                stock = lote.stock
                stock.recalcular()

                MovimientoStock.objects.create(
                    producto=stock.producto,
                    area=stock.area,
                    tipo=MovimientoStock.TIPO_DESCARTE,
                    cantidad=cantidad,
                    lote=lote,
                    numero_lote=lote.numero_lote,
                    fecha_vencimiento=lote.fecha_vencimiento,
                    usuario=request.user,
                    observacion=observacion,
                )
                descartados += 1

            except LoteEnArea.DoesNotExist:
                errores.append(f'Lote {lote_id} no encontrado o ya inactivo')

    return JsonResponse({
        'ok': True,
        'descartados': descartados,
        'errores': errores,
    })
