"""
Vista del Dashboard de Pedidos de Estudios.
Monitoreo en tiempo real de pedidos procesados automáticamente desde Gmail.
"""
import logging
from datetime import datetime, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator

from .models import PedidoEstudio, PacienteEstudio, LogProcesamientoEmail
from .forms import FiltroPedidosForm
from accounts.decorators import dashboard_pedidos_required

logger = logging.getLogger(__name__)


@dashboard_pedidos_required
def dashboard_pedidos(request):
    """
    Dashboard principal de pedidos de estudios.
    Muestra estadísticas, tabla de pedidos recientes y filtros.
    """
    
    # Obtener parámetros de filtro
    mostrar = request.GET.get('mostrar', 'todos')  # todos, urgentes, hoy, pendientes
    estado_filtro = request.GET.get('estado', '')
    prioridad_filtro = request.GET.get('prioridad', '')
    tipo_filtro = request.GET.get('tipo', '')
    search = request.GET.get('search', '')
    
    # Obtener fecha local (Argentina) no UTC
    hoy_local = timezone.localtime(timezone.now())
    hoy = hoy_local.date()
    
    # Query base
    pedidos = PedidoEstudio.objects.select_related(
        'paciente', 
        'tipo_estudio',
        'medico_asignado'
    ).order_by('-fecha_creacion')
    
    # Aplicar filtros rápidos
    if mostrar == 'urgentes':
        pedidos = pedidos.filter(prioridad='URGENTE')
    elif mostrar == 'hoy':
        pedidos = pedidos.filter(fecha_creacion__date=hoy)
    elif mostrar == 'pendientes':
        pedidos = pedidos.filter(estado='PENDIENTE')
    elif mostrar == 'revision':
        pedidos = pedidos.filter(requiere_revision=True)
    
    # Aplicar filtros avanzados
    if estado_filtro:
        pedidos = pedidos.filter(estado=estado_filtro)
    
    if prioridad_filtro:
        pedidos = pedidos.filter(prioridad=prioridad_filtro)
    
    if tipo_filtro:
        pedidos = pedidos.filter(tipo_estudio_id=tipo_filtro)
    
    if search:
        pedidos = pedidos.filter(
            Q(paciente__nombre_completo__icontains=search) |
            Q(paciente__dni__icontains=search) |
            Q(paciente__historia_clinica__icontains=search) |
            Q(descripcion_estudio__icontains=search)
        )
    
    # Paginación
    paginator = Paginator(pedidos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas generales (usando hoy ya definido arriba con localtime)
    stats = {
        'total': PedidoEstudio.objects.count(),
        'hoy': PedidoEstudio.objects.filter(fecha_creacion__date=hoy).count(),
        'urgentes': PedidoEstudio.objects.filter(
            prioridad='URGENTE', 
            estado__in=['PENDIENTE', 'PROCESANDO']
        ).count(),
        'pendientes': PedidoEstudio.objects.filter(estado='PENDIENTE').count(),
        'revision': PedidoEstudio.objects.filter(requiere_revision=True).count(),
        'realizados_hoy': PedidoEstudio.objects.filter(
            estado='REALIZADO',
            fecha_realizacion__date=hoy
        ).count(),
    }
    
    # Estadísticas por tipo de estudio (para el día)
    stats_tipos = PedidoEstudio.objects.filter(
        fecha_creacion__date=hoy
    ).values(
        'tipo_estudio__nombre'
    ).annotate(
        total=Count('id')
    ).order_by('-total')[:5]
    
    # Logs de procesamiento recientes
    logs_recientes = LogProcesamientoEmail.objects.select_related(
        'pedido'
    ).order_by('-fecha_procesamiento')[:5]
    
    # Últimos emails procesados
    ultimos_emails = LogProcesamientoEmail.objects.filter(
        resultado__in=['EXITO', 'MULTIPLES', 'PARCIAL']
    ).order_by('-fecha_procesamiento')[:3]
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'stats_tipos': stats_tipos,
        'logs_recientes': logs_recientes,
        'ultimos_emails': ultimos_emails,
        'mostrar': mostrar,
        'estado_filtro': estado_filtro,
        'prioridad_filtro': prioridad_filtro,
        'tipo_filtro': tipo_filtro,
        'search': search,
        'form': FiltroPedidosForm(request.GET or None),
    }
    
    return render(request, 'pedidos_estudios/dashboard.html', context)
