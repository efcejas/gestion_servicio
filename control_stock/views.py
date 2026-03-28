from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, Q, Prefetch
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
import csv

from accounts.decorators import role_required
from .models import AreaServicio, Producto, StockPorArea, MovimientoStock, LoteEnArea
from .forms import ProductoForm, FiltroHistorialForm

ROLES_STOCK = (
    'medico_staff', 'medico_residente', 'jefe_residentes',
    'instructor_residentes', 'jefe_servicio', 'cardiologo',
    'tecnico', 'enfermeria',
)

ROLES_GESTION = ('jefe_servicio', 'jefe_residentes', 'instructor_residentes', 'medico_staff')


@role_required(*ROLES_STOCK)
def dashboard(request):
    # Prefetch con join a producto para usar el caché en Python (evita N+1)
    areas = AreaServicio.objects.filter(activa=True).prefetch_related(
        Prefetch('stock_items', queryset=StockPorArea.objects.select_related('producto'))
    )
    fecha_alerta = timezone.now().date() + timezone.timedelta(days=30)
    hoy = timezone.now().date()

    areas_data = []
    for area in areas:
        cached_items = list(area.stock_items.all())  # usa prefetch; sin hit a la DB
        items_total = len(cached_items)
        bajo_minimo_count = sum(1 for s in cached_items if s.bajo_minimo)
        vencimientos_proximos = MovimientoStock.objects.filter(
            area=area,
            tipo=MovimientoStock.TIPO_ENTRADA,
            fecha_vencimiento__isnull=False,
            fecha_vencimiento__lte=fecha_alerta,
            fecha_vencimiento__gte=hoy,
        ).values('producto').distinct().count()

        areas_data.append({
            'area': area,
            'items_total': items_total,
            'bajo_minimo_count': bajo_minimo_count,
            'vencimientos_proximos': vencimientos_proximos,
            'tiene_alertas': bajo_minimo_count > 0 or vencimientos_proximos > 0,
        })

    return render(request, 'control_stock/dashboard.html', {
        'areas_data': areas_data,
        'total_areas': len(areas_data),
    })


@role_required(*ROLES_STOCK)
def detalle_area(request, area_id):
    area = get_object_or_404(AreaServicio, pk=area_id, activa=True)
    fecha_alerta = timezone.now().date() + timezone.timedelta(days=30)

    stock_items = StockPorArea.objects.filter(area=area).select_related('producto').order_by('producto__nombre')

    # Enriquecer cada ítem con info de vencimiento
    items_data = []
    for item in stock_items:
        ultimo_mov_entrada = MovimientoStock.objects.filter(
            producto=item.producto,
            area=area,
            tipo=MovimientoStock.TIPO_ENTRADA,
            fecha_vencimiento__isnull=False,
        ).order_by('-fecha').first()

        vencimiento = ultimo_mov_entrada.fecha_vencimiento if ultimo_mov_entrada else None
        vence_pronto = vencimiento and vencimiento <= fecha_alerta and vencimiento >= timezone.now().date()
        vencido = vencimiento and vencimiento < timezone.now().date()

        items_data.append({
            'stock': item,
            'vencimiento': vencimiento,
            'vence_pronto': vence_pronto,
            'vencido': vencido,
        })

    return render(request, 'control_stock/detalle_area.html', {
        'area': area,
        'items_data': items_data,
    })


@role_required(*ROLES_STOCK)
def scanner(request, area_id=None):
    areas = AreaServicio.objects.filter(activa=True).order_by('nombre')
    area_seleccionada = None
    if area_id:
        area_seleccionada = get_object_or_404(AreaServicio, pk=area_id, activa=True)

    return render(request, 'control_stock/scanner.html', {
        'areas': areas,
        'area_seleccionada': area_seleccionada,
    })


@role_required(*ROLES_STOCK)
def historial(request):
    form = FiltroHistorialForm(request.GET or None)
    movimientos = MovimientoStock.objects.select_related(
        'producto', 'area', 'usuario'
    ).order_by('-fecha')

    if form.is_valid():
        if form.cleaned_data.get('area'):
            movimientos = movimientos.filter(area=form.cleaned_data['area'])
        if form.cleaned_data.get('tipo'):
            movimientos = movimientos.filter(tipo=form.cleaned_data['tipo'])
        if form.cleaned_data.get('fecha_desde'):
            movimientos = movimientos.filter(fecha__date__gte=form.cleaned_data['fecha_desde'])
        if form.cleaned_data.get('fecha_hasta'):
            movimientos = movimientos.filter(fecha__date__lte=form.cleaned_data['fecha_hasta'])
        if form.cleaned_data.get('q'):
            movimientos = movimientos.filter(producto__nombre__icontains=form.cleaned_data['q'])

    paginator = Paginator(movimientos, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    for mov in page_obj:
        mov.puede_anular_flag = mov.puede_anular(request.user)

    get_params = request.GET.copy()
    get_params.pop('page', None)

    return render(request, 'control_stock/historial.html', {
        'movimientos': page_obj,
        'form': form,
        'page_obj': page_obj,
        'query_string': get_params.urlencode(),
    })


@role_required(*ROLES_STOCK)
def crear_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save(commit=False)
            producto.creado_por = request.user
            producto.save()
            messages.success(request, f'Producto "{producto.nombre}" registrado correctamente.')
            return redirect('control_stock:dashboard')
    else:
        codigo_inicial = request.GET.get('codigo', '')
        form = ProductoForm(initial={'codigo_barras': codigo_inicial})

    return render(request, 'control_stock/crear_producto.html', {'form': form})


@role_required(*ROLES_GESTION)
def editar_producto(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, f'Producto "{producto.nombre}" actualizado.')
            return redirect('control_stock:dashboard')
    else:
        form = ProductoForm(instance=producto)

    return render(request, 'control_stock/crear_producto.html', {
        'form': form,
        'producto': producto,
        'editando': True,
    })


# ── Fase 3: exportar historial CSV ────────────────────────────
@role_required(*ROLES_STOCK)
def exportar_historial_csv(request):
    form = FiltroHistorialForm(request.GET or None)
    movimientos = MovimientoStock.objects.select_related(
        'producto', 'area', 'usuario'
    ).order_by('-fecha')

    if form.is_valid():
        if form.cleaned_data.get('area'):
            movimientos = movimientos.filter(area=form.cleaned_data['area'])
        if form.cleaned_data.get('tipo'):
            movimientos = movimientos.filter(tipo=form.cleaned_data['tipo'])
        if form.cleaned_data.get('fecha_desde'):
            movimientos = movimientos.filter(fecha__date__gte=form.cleaned_data['fecha_desde'])
        if form.cleaned_data.get('fecha_hasta'):
            movimientos = movimientos.filter(fecha__date__lte=form.cleaned_data['fecha_hasta'])
        if form.cleaned_data.get('q'):
            movimientos = movimientos.filter(producto__nombre__icontains=form.cleaned_data['q'])

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f'historial_stock_{timezone.now().strftime("%Y%m%d_%H%M")}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Fecha', 'Tipo', 'Producto', 'Código', 'Área', 'Cantidad',
                     'Usuario', 'Vencimiento', 'Lote', 'Observación', 'Anulado'])

    for mov in movimientos.iterator():
        writer.writerow([
            mov.fecha.strftime('%d/%m/%Y %H:%M'),
            'Entrada' if mov.tipo == 'entrada' else 'Salida',
            mov.producto.nombre,
            mov.producto.codigo_barras,
            mov.area.nombre,
            mov.cantidad,
            mov.usuario.get_full_name() or mov.usuario.username,
            mov.fecha_vencimiento.strftime('%d/%m/%Y') if mov.fecha_vencimiento else '',
            mov.numero_lote or '',
            mov.observacion or '',
            'Sí' if mov.anulado else 'No',
        ])

    return response


# ── Fase 1: buscador global ────────────────────────────────────
@role_required(*ROLES_STOCK)
def buscar_producto(request):
    areas = AreaServicio.objects.filter(activa=True).order_by('nombre')
    return render(request, 'control_stock/buscar.html', {'areas': areas})


# ── Fase 2: vencimientos próximos ─────────────────────────────
@role_required(*ROLES_STOCK)
def vencimientos(request):
    try:
        dias = max(1, min(365, int(request.GET.get('dias', 30))))
    except (ValueError, TypeError):
        dias = 30

    area_id = request.GET.get('area_id')
    hoy = timezone.now().date()
    fecha_limite = hoy + timezone.timedelta(days=dias)

    areas = AreaServicio.objects.filter(activa=True).order_by('nombre')
    area_filtro = None
    if area_id:
        area_filtro = get_object_or_404(AreaServicio, pk=area_id, activa=True)

    stock_qs = StockPorArea.objects.select_related('producto', 'area').filter(area__activa=True)
    if area_filtro:
        stock_qs = stock_qs.filter(area=area_filtro)

    # Buscar directamente en LoteEnArea (autoridad sobre vencimientos)
    lotes = LoteEnArea.objects.filter(
        stock__in=stock_qs,
        activo=True,
        fecha_vencimiento__isnull=False,
        fecha_vencimiento__lte=fecha_limite,
    ).select_related('stock__producto', 'stock__area').order_by('fecha_vencimiento')

    items = [
        {
            'stock': lote.stock,
            'lote': lote,
            'vencimiento': lote.fecha_vencimiento,
            'vencido': lote.fecha_vencimiento < hoy,
            'vence_hoy': lote.fecha_vencimiento == hoy,
            'vence_semana': hoy <= lote.fecha_vencimiento <= hoy + timezone.timedelta(days=7),
            'reportado': lote.reportado_para_descarte,
        }
        for lote in lotes
    ]

    puede_descartar = (
        request.user.is_superuser
        or getattr(request.user, 'rol', None) in MovimientoStock.ROLES_PUEDEN_DESCARTAR
    )

    return render(request, 'control_stock/vencimientos.html', {
        'items': items,
        'areas': areas,
        'area_filtro': area_filtro,
        'dias': dias,
        'hoy': hoy,
        'puede_descartar': puede_descartar,
    })


# ── Fase 4: historial de un producto en un área (JSON) ────────
@login_required
def historial_producto_area(request, area_id, producto_id):
    area = get_object_or_404(AreaServicio, pk=area_id, activa=True)
    producto = get_object_or_404(Producto, pk=producto_id)

    movimientos = MovimientoStock.objects.filter(
        producto=producto,
        area=area,
    ).select_related('usuario').order_by('-fecha')[:30]

    data = [{
        'id': mov.id,
        'tipo': mov.tipo,
        'cantidad': mov.cantidad,
        'fecha': mov.fecha.isoformat(),
        'usuario': mov.usuario.get_full_name() or mov.usuario.username,
        'observacion': mov.observacion or '',
        'anulado': mov.anulado,
        'fecha_vencimiento': mov.fecha_vencimiento.strftime('%d/%m/%Y') if mov.fecha_vencimiento else None,
        'numero_lote': mov.numero_lote or None,
    } for mov in movimientos]

    return JsonResponse({'movimientos': data, 'producto': producto.nombre, 'area': area.nombre})
