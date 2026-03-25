import json
import csv
import urllib.request
import urllib.error
from decimal import Decimal
from datetime import date, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Max

from django.forms import inlineformset_factory
from .decorators import vivienda_required
from .models import ConfiguracionMeta, Cotizacion, Snapshot, CapitalItem, Conversion
from .forms import (
    ConfiguracionMetaForm,
    CotizacionForm,
    SnapshotForm,
    CapitalItemFormSet,
    CapitalItemForm,
    ConversionForm,
)


# ─────────────────────────────────────────────
# API interna: cotización hoy via Bluelytics
# ─────────────────────────────────────────────

@vivienda_required
def api_cotizacion_hoy(request):
    """
    Consulta la API de Bluelytics y devuelve los valores del día.
    Si falla, devuelve {'error': ...} para que el front muestre input manual.
    """
    url = 'https://api.bluelytics.com.ar/v2/latest'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
        return JsonResponse({
            'ok': True,
            'blue_compra': data['blue']['value_buy'],
            'blue_venta': data['blue']['value_sell'],
            'oficial_compra': data['oficial']['value_buy'],
            'oficial_venta': data['oficial']['value_sell'],
            'mep': data.get('blue_euro', {}).get('value_sell', 0),  # fallback
        })
    except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
        return JsonResponse({'ok': False, 'error': str(e)})


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────

@vivienda_required
def dashboard(request):
    config = ConfiguracionMeta.get_config()
    snapshots = list(Snapshot.objects.prefetch_related('items').order_by('fecha'))
    ultimo = snapshots[-1] if snapshots else None
    conversiones_recientes = Conversion.objects.order_by('-fecha', '-creada')[:5]

    # Progreso hacia la meta
    progreso_pct = None
    falta_usd = None
    if config and ultimo:
        meta = config.meta_usd
        total = ultimo.total_usd_calculado
        if meta > 0:
            progreso_pct = min(float(total / meta * 100), 100)
        falta_usd = max(meta - total, Decimal('0'))

    # Proyección lineal: "en cuántos meses llegamos"
    proyeccion_meses = None
    proyeccion_fecha = None
    if config and len(snapshots) >= 2:
        # Variación promedio mensual en USD
        variaciones = []
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1]
            curr = snapshots[i]
            dias = (curr.fecha - prev.fecha).days
            if dias > 0:
                var_mensual = float(curr.total_usd_calculado - prev.total_usd_calculado) / dias * 30
                variaciones.append(var_mensual)
        if variaciones:
            var_prom = sum(variaciones) / len(variaciones)
            if var_prom > 0 and falta_usd is not None:
                proyeccion_meses = round(float(falta_usd) / var_prom)
                if proyeccion_meses >= 0:
                    proyeccion_fecha = date.today() + timedelta(days=proyeccion_meses * 30)

    # Datos para Chart.js evolución
    chart_labels = [s.fecha.strftime('%b %Y') for s in snapshots]
    chart_data = [float(s.total_usd_calculado) for s in snapshots]
    chart_meta = float(config.meta_usd) if config else None

    # Datos para stacked bar (desglose por moneda en el tiempo)
    all_monedas = []
    seen = set()
    for s in snapshots:
        for item in s.items.all():
            if item.moneda not in seen:
                all_monedas.append(item.moneda)
                seen.add(item.moneda)
    chart_desglose_datasets = []
    MONEDA_COLORS = {
        'USD': 'rgba(16, 185, 129, 0.85)',
        'ARS': 'rgba(251, 191, 36, 0.85)',
        'EUR': 'rgba(59, 130, 246, 0.85)',
        'BRL': 'rgba(249, 115, 22, 0.85)',
        'otro': 'rgba(156, 163, 175, 0.85)',
    }
    for moneda in all_monedas:
        totales = []
        for s in snapshots:
            total = sum(
                item.monto_usd for item in s.items.all()
                if item.moneda == moneda and item.monto_usd
            )
            totales.append(float(total))
        chart_desglose_datasets.append({
            'label': moneda,
            'data': totales,
            'backgroundColor': MONEDA_COLORS.get(moneda, 'rgba(156,163,175,0.85)'),
        })

    # Variaciones para el historial
    variaciones = {}
    for i, s in enumerate(snapshots):
        if i > 0:
            variaciones[s.pk] = float(s.total_usd_calculado - snapshots[i-1].total_usd_calculado)

    # Promedio mensual de ahorro (para pre-llenar el simulador)
    var_prom_mensual = None
    if len(snapshots) >= 2:
        vars_list = []
        for i in range(1, len(snapshots)):
            dias = (snapshots[i].fecha - snapshots[i-1].fecha).days
            if dias > 0:
                vars_list.append(
                    float(snapshots[i].total_usd_calculado - snapshots[i-1].total_usd_calculado) / dias * 30
                )
        if vars_list:
            var_prom_mensual = round(sum(vars_list) / len(vars_list), 2)

    # Alerta de meta alcanzada (>= 90%)
    alerta_meta = progreso_pct is not None and progreso_pct >= 90

    # Desglose por moneda del último snapshot
    desglose_moneda = {}
    if ultimo:
        for item in ultimo.items.all():
            moneda = item.moneda
            desglose_moneda[moneda] = desglose_moneda.get(moneda, Decimal('0')) + item.monto_usd

    return render(request, 'ahorro_vivienda/dashboard.html', {
        'config': config,
        'ultimo': ultimo,
        'snapshots': snapshots,
        'conversiones_recientes': conversiones_recientes,
        'progreso_pct': progreso_pct,
        'falta_usd': falta_usd,
        'proyeccion_meses': proyeccion_meses,
        'proyeccion_fecha': proyeccion_fecha,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'chart_meta': json.dumps(chart_meta),
        'alerta_meta': alerta_meta,
        'desglose_moneda': desglose_moneda,
        'chart_desglose_datasets': json.dumps(chart_desglose_datasets),
        'variaciones': variaciones,
        'var_prom_mensual': var_prom_mensual,
    })


# ─────────────────────────────────────────────
# Snapshots
# ─────────────────────────────────────────────

@vivienda_required
def lista_snapshots(request):
    snapshots_qs = list(Snapshot.objects.prefetch_related('items').order_by('fecha'))
    config = ConfiguracionMeta.get_config()
    # Calcular variaciones
    variaciones = {}
    for i, s in enumerate(snapshots_qs):
        if i > 0:
            variaciones[s.pk] = float(s.total_usd_calculado - snapshots_qs[i-1].total_usd_calculado)
    snapshots = list(reversed(snapshots_qs))  # mostrar más reciente primero
    return render(request, 'ahorro_vivienda/lista_snapshots.html', {
        'snapshots': snapshots,
        'config': config,
        'variaciones': variaciones,
    })


@vivienda_required
def nuevo_snapshot(request):
    hoy = date.today()
    cotizacion_existente = Cotizacion.mas_cercana(hoy)
    # Último blue registrado para alerta de cotización inusual
    ultimo_blue = None
    last_cot = Cotizacion.objects.order_by('-fecha').first()
    if last_cot:
        ultimo_blue = float(last_cot.blue_venta)

    if request.method == 'POST':
        snapshot_form = SnapshotForm(request.POST)
        cot_form = CotizacionForm(request.POST, prefix='cot')

        # Si la cotización ya existe para esa fecha, usarla y no validar el form de cotización
        snapshot_fecha = request.POST.get('fecha')
        cot_existente_para_fecha = None
        if snapshot_fecha:
            try:
                from datetime import date as date_cls
                fecha_obj = date_cls.fromisoformat(snapshot_fecha)
                cot_existente_para_fecha = Cotizacion.objects.filter(fecha=fecha_obj).first()
            except ValueError:
                pass

        if snapshot_form.is_valid():
            snapshot = snapshot_form.save(commit=False)
            snapshot.creado_por = request.user

            # Determinar cotización
            if cot_existente_para_fecha:
                snapshot.cotizacion = cot_existente_para_fecha
                snapshot.save()
            elif cot_form.is_valid():
                cotizacion, _ = Cotizacion.objects.update_or_create(
                    fecha=cot_form.cleaned_data['fecha'],
                    defaults={**cot_form.cleaned_data, 'fuente': cot_form.cleaned_data.get('fuente', 'manual')}
                )
                snapshot.cotizacion = cotizacion
                snapshot.save()
            else:
                # Sin cotización válida: no guardar el snapshot
                messages.error(request, 'Ingresá las cotizaciones del día o buscalas con la API antes de guardar.')
                formset = CapitalItemFormSet(request.POST)
                return render(request, 'ahorro_vivienda/nuevo_snapshot.html', {
                    'snapshot_form': snapshot_form,
                    'cot_form': cot_form,
                    'formset': formset,
                    'cotizacion_existente': cotizacion_existente,
                    'ultimo_blue': ultimo_blue,
                })

            formset = CapitalItemFormSet(request.POST, instance=snapshot)
            if formset.is_valid():
                items = formset.save(commit=False)
                for item in items:
                    item.save()
                for deleted in formset.deleted_objects:
                    deleted.delete()
                snapshot.recalcular_total()
                messages.success(request, f'Snapshot del {snapshot.fecha.strftime("%d/%m/%Y")} guardado. Total: USD {snapshot.total_usd_calculado:,.2f}')
                return redirect('ahorro_vivienda:detalle_snapshot', pk=snapshot.pk)
            else:
                # Formset inválido: borrar el snapshot creado y mostrar errores
                snapshot.delete()
                messages.error(request, 'Revisá los datos de los ítems.')
        else:
            formset = CapitalItemFormSet(request.POST)
    else:
        snapshot_form = SnapshotForm(initial={'fecha': hoy})
        if cotizacion_existente:
            cot_form = CotizacionForm(instance=cotizacion_existente, prefix='cot',
                                      initial={'fecha': hoy})
        else:
            cot_form = CotizacionForm(prefix='cot', initial={'fecha': hoy})
        # Pre-poblar con los ítems del último snapshot
        # inlineformset_factory(extra=0) ignora initial=[]; necesitamos extra=N dinámico
        ultimo = Snapshot.objects.order_by('-fecha').first()
        if ultimo:
            initial_data = [
                {
                    'nombre': item.nombre,
                    'tipo': item.tipo,
                    'moneda': item.moneda,
                    'monto_original': item.monto_original,
                    'cotizacion_tipo': item.cotizacion_tipo,
                    'cotizacion_manual': item.cotizacion_manual,
                    'orden': item.orden,
                }
                for item in ultimo.items.order_by('orden')
            ]
            PreloadFormSet = inlineformset_factory(
                Snapshot, CapitalItem, form=CapitalItemForm,
                extra=len(initial_data), can_delete=True,
                min_num=0, validate_min=False,
            )
            formset = PreloadFormSet(initial=initial_data)
        else:
            PreloadFormSet = inlineformset_factory(
                Snapshot, CapitalItem, form=CapitalItemForm,
                extra=1, can_delete=True,
                min_num=1, validate_min=True,
            )
            formset = PreloadFormSet()

    return render(request, 'ahorro_vivienda/nuevo_snapshot.html', {
        'snapshot_form': snapshot_form,
        'cot_form': cot_form,
        'formset': formset,
        'cotizacion_existente': cotizacion_existente,
        'ultimo_blue': ultimo_blue,
    })


@vivienda_required
def detalle_snapshot(request, pk):
    snapshot = get_object_or_404(Snapshot, pk=pk)
    config = ConfiguracionMeta.get_config()

    # Progreso para este snapshot
    progreso_pct = None
    if config and config.meta_usd > 0:
        progreso_pct = min(float(snapshot.total_usd_calculado / config.meta_usd * 100), 100)

    # Desglose por moneda
    desglose = {}
    for item in snapshot.items.all():
        desglose[item.moneda] = desglose.get(item.moneda, Decimal('0')) + item.monto_usd

    return render(request, 'ahorro_vivienda/detalle_snapshot.html', {
        'snapshot': snapshot,
        'config': config,
        'progreso_pct': progreso_pct,
        'desglose': desglose,
    })


# ─────────────────────────────────────────────
# Conversiones
# ─────────────────────────────────────────────

@vivienda_required
def lista_conversiones(request):
    conversiones = Conversion.objects.select_related('registrado_por').order_by('-fecha', '-creada')
    return render(request, 'ahorro_vivienda/lista_conversiones.html', {
        'conversiones': conversiones,
    })


@vivienda_required
def nueva_conversion(request):
    if request.method == 'POST':
        form = ConversionForm(request.POST)
        if form.is_valid():
            conversion = form.save(commit=False)
            conversion.registrado_por = request.user
            # Intentar asociar cotización de referencia para esa fecha
            cot = Cotizacion.mas_cercana(conversion.fecha)
            if cot:
                conversion.cotizacion_ref = cot
            conversion.save()
            messages.success(request, 'Conversión registrada correctamente.')
            return redirect('ahorro_vivienda:lista_conversiones')
    else:
        form = ConversionForm(initial={'fecha': date.today()})

    return render(request, 'ahorro_vivienda/nueva_conversion.html', {'form': form})


# ─────────────────────────────────────────────
# Configuración meta
# ─────────────────────────────────────────────

@vivienda_required
def configuracion(request):
    config = ConfiguracionMeta.get_config()
    if request.method == 'POST':
        form = ConfiguracionMetaForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración guardada.')
            return redirect('ahorro_vivienda:dashboard')
    else:
        form = ConfiguracionMetaForm(instance=config)
    return render(request, 'ahorro_vivienda/configuracion.html', {'form': form, 'config': config})


# ─────────────────────────────────────────────
# Export CSV
# ─────────────────────────────────────────────

@vivienda_required
def export_csv(request):
    """Exporta el historial de snapshots como CSV (compatible con Excel)."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="ahorro_vivienda.csv"'
    response.write('\ufeff')  # BOM para que Excel lo abra bien en UTF-8

    writer = csv.writer(response)
    writer.writerow(['Fecha', 'Total USD', 'Variación USD', 'Blue venta', 'Ítems', 'Notas'])

    snapshots = (
        Snapshot.objects.prefetch_related('items')
        .select_related('cotizacion')
        .order_by('fecha')
    )
    prev_total = None
    for snap in snapshots:
        if prev_total is not None:
            variacion = f"+{float(snap.total_usd_calculado - prev_total):.2f}" \
                if snap.total_usd_calculado >= prev_total \
                else f"{float(snap.total_usd_calculado - prev_total):.2f}"
        else:
            variacion = ''
        writer.writerow([
            snap.fecha.strftime('%d/%m/%Y'),
            f"{float(snap.total_usd_calculado):.2f}",
            variacion,
            f"{float(snap.cotizacion.blue_venta):.2f}" if snap.cotizacion else '',
            snap.items.count(),
            snap.notas,
        ])
        prev_total = snap.total_usd_calculado

    return response
