"""
Vistas para gestión de pedidos de estudios médicos.
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import PedidoEstudio, PacienteEstudio, TipoEstudio, LogProcesamientoEmail
from .forms import (
    PedidoEstudioForm, 
    PacienteEstudioForm, 
    FiltroPedidosForm,
    RevisarPedidoForm
)
from .services.procesador import procesar_emails_ahora
from .services.gmail_service import verificar_configuracion_gmail

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Dashboard principal de pedidos de estudios."""
    
    # Estadísticas generales
    total_pedidos = PedidoEstudio.objects.count()
    pendientes = PedidoEstudio.objects.filter(estado='PENDIENTE').count()
    requieren_revision = PedidoEstudio.objects.filter(requiere_revision=True).count()
    urgentes = PedidoEstudio.objects.filter(prioridad='URGENTE', estado__in=['PENDIENTE', 'PROCESANDO']).count()
    
    # Pedidos recientes
    pedidos_recientes = PedidoEstudio.objects.select_related(
        'paciente', 'tipo_estudio'
    ).order_by('-fecha_creacion')[:10]
    
    # Estadísticas por estado
    stats_por_estado = PedidoEstudio.objects.values('estado').annotate(
        total=Count('id')
    ).order_by('estado')
    
    # Logs recientes de procesamiento
    logs_recientes = LogProcesamientoEmail.objects.order_by('-fecha_procesamiento')[:5]
    
    context = {
        'total_pedidos': total_pedidos,
        'pendientes': pendientes,
        'requieren_revision': requieren_revision,
        'urgentes': urgentes,
        'pedidos_recientes': pedidos_recientes,
        'stats_por_estado': stats_por_estado,
        'logs_recientes': logs_recientes,
    }
    
    return render(request, 'pedidos_estudios/dashboard.html', context)


@login_required
def lista_pedidos(request):
    """Lista de pedidos con filtros."""
    
    pedidos = PedidoEstudio.objects.select_related(
        'paciente', 'tipo_estudio', 'medico_asignado'
    ).order_by('-fecha_solicitud')
    
    # Aplicar filtros
    form = FiltroPedidosForm(request.GET)
    
    if form.is_valid():
        if form.cleaned_data.get('estado'):
            pedidos = pedidos.filter(estado=form.cleaned_data['estado'])
        
        if form.cleaned_data.get('prioridad'):
            pedidos = pedidos.filter(prioridad=form.cleaned_data['prioridad'])
        
        if form.cleaned_data.get('tipo_estudio'):
            pedidos = pedidos.filter(tipo_estudio=form.cleaned_data['tipo_estudio'])
        
        if form.cleaned_data.get('requiere_revision'):
            pedidos = pedidos.filter(requiere_revision=True)
        
        if form.cleaned_data.get('fecha_desde'):
            pedidos = pedidos.filter(fecha_solicitud__gte=form.cleaned_data['fecha_desde'])
        
        if form.cleaned_data.get('fecha_hasta'):
            pedidos = pedidos.filter(fecha_solicitud__lte=form.cleaned_data['fecha_hasta'])
        
        if form.cleaned_data.get('buscar'):
            busqueda = form.cleaned_data['buscar']
            pedidos = pedidos.filter(
                Q(paciente__nombre_completo__icontains=busqueda) |
                Q(descripcion_estudio__icontains=busqueda) |
                Q(medico_solicitante__icontains=busqueda)
            )
    
    context = {
        'pedidos': pedidos,
        'form': form,
    }
    
    return render(request, 'pedidos_estudios/lista_pedidos.html', context)


@login_required
def detalle_pedido(request, pk):
    """Detalle de un pedido específico."""
    
    pedido = get_object_or_404(
        PedidoEstudio.objects.select_related(
            'paciente', 'tipo_estudio', 'medico_asignado',
            'revisado_por', 'creado_por'
        ).prefetch_related('adjuntos', 'logs_procesamiento'),
        pk=pk
    )
    
    context = {
        'pedido': pedido,
    }
    
    return render(request, 'pedidos_estudios/detalle_pedido.html', context)


@login_required
def revisar_pedido(request, pk):
    """Revisión y edición de un pedido."""
    
    pedido = get_object_or_404(PedidoEstudio, pk=pk)
    
    if request.method == 'POST':
        form = RevisarPedidoForm(request.POST, instance=pedido)
        
        if form.is_valid():
            form.save()
            
            # Marcar como revisado
            if pedido.requiere_revision:
                pedido.marcar_como_procesado(usuario=request.user)
            
            messages.success(request, f'Pedido #{pedido.id} revisado correctamente')
            return redirect('pedidos_estudios:detalle_pedido', pk=pedido.id)
    else:
        form = RevisarPedidoForm(instance=pedido)
    
    context = {
        'pedido': pedido,
        'form': form,
    }
    
    return render(request, 'pedidos_estudios/revisar_pedido.html', context)


@login_required
@require_POST
def cambiar_estado(request, pk):
    """Cambia el estado de un pedido (AJAX)."""
    
    pedido = get_object_or_404(PedidoEstudio, pk=pk)
    nuevo_estado = request.POST.get('estado')
    
    if nuevo_estado in dict(PedidoEstudio.ESTADOS):
        pedido.estado = nuevo_estado
        pedido.save()
        
        return JsonResponse({
            'success': True,
            'mensaje': f'Estado actualizado a {pedido.get_estado_display()}'
        })
    
    return JsonResponse({
        'success': False,
        'error': 'Estado inválido'
    }, status=400)


@login_required
def procesar_emails_manual(request):
    """Vista para procesar emails manualmente."""
    
    if request.method == 'POST':
        try:
            max_emails = int(request.POST.get('max_emails', 10))
            
            # Procesar emails
            stats = procesar_emails_ahora(max_emails=max_emails)
            
            messages.success(
                request,
                f'Procesamiento completado: {stats["exitosos"]} exitosos, '
                f'{stats["errores"]} errores, {stats["duplicados"]} duplicados'
            )
        
        except Exception as e:
            logger.error(f"Error al procesar emails: {e}", exc_info=True)
            messages.error(request, f'Error al procesar emails: {str(e)}')
        
        return redirect('pedidos_estudios:dashboard')
    
    return render(request, 'pedidos_estudios/procesar_emails.html')


@login_required
def verificar_gmail(request):
    """Verifica la configuración de Gmail."""
    
    exito, mensaje = verificar_configuracion_gmail()
    
    context = {
        'exito': exito,
        'mensaje': mensaje,
    }
    
    return render(request, 'pedidos_estudios/verificar_gmail.html', context)


@login_required
def logs_procesamiento(request):
    """Lista de logs de procesamiento."""
    
    logs = LogProcesamientoEmail.objects.select_related(
        'pedido_creado'
    ).order_by('-fecha_procesamiento')[:100]
    
    context = {
        'logs': logs,
    }
    
    return render(request, 'pedidos_estudios/logs_procesamiento.html', context)
