"""
Vistas para médicos de guardia.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse

from .models import PedidoEstudio, MedicoGuardia


@login_required
def mis_estudios_pendientes(request):
    """
    Vista para que los médicos vean sus estudios pendientes.
    Filtrada automáticamente por especialidad del médico.
    """
    # Buscar si el usuario tiene un perfil de médico guardia
    try:
        medico = MedicoGuardia.objects.get(usuario=request.user)
    except MedicoGuardia.DoesNotExist:
        messages.error(
            request, 
            "No tienes un perfil de médico de guardia configurado. "
            "Contacta al administrador."
        )
        return redirect('pedidos_estudios:dashboard')
    
    # Verificar que esté activo
    if not medico.activo:
        messages.warning(
            request,
            "Tu perfil de médico está inactivo. "
            "Contacta al administrador para activarlo."
        )
    
    # Filtrar estudios según especialidad
    estudios = PedidoEstudio.objects.select_related(
        'paciente', 'tipo_estudio', 'medico_asignado'
    ).exclude(
        estado='REALIZADO'
    ).order_by('-prioridad', 'fecha_solicitud')
    
    # Aplicar filtro por especialidad
    if medico.especialidad == 'DOPPLER':
        # Solo dopplers
        estudios = estudios.filter(
            Q(tipo_estudio__nombre__icontains='doppler') &
            ~Q(tipo_estudio__nombre__icontains='ecocardio')
        )
    elif medico.especialidad == 'ECOCARDIO':
        # Solo ecocardiogramas
        estudios = estudios.filter(
            Q(tipo_estudio__nombre__icontains='ecocardio') |
            Q(tipo_estudio__nombre__icontains='eco cardio')
        )
    # Si es 'AMBOS', no filtra
    
    # Estadísticas
    total_estudios = estudios.count()
    urgentes = estudios.filter(prioridad='URGENTE').count()
    hoy = timezone.localtime(timezone.now()).date()
    estudios_hoy = estudios.filter(fecha_solicitud__date=hoy).count()
    
    context = {
        'medico': medico,
        'estudios': estudios,
        'total_estudios': total_estudios,
        'urgentes': urgentes,
        'estudios_hoy': estudios_hoy,
    }
    
    return render(request, 'pedidos_estudios/mis_estudios.html', context)


@login_required
def marcar_realizado(request, pedido_id):
    """
    Marca un estudio como realizado.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    # Verificar que el usuario es un médico de guardia
    try:
        medico = MedicoGuardia.objects.get(usuario=request.user)
    except MedicoGuardia.DoesNotExist:
        return JsonResponse({
            'error': 'No tienes permisos para realizar esta acción'
        }, status=403)
    
    # Obtener el pedido
    pedido = get_object_or_404(PedidoEstudio, id=pedido_id)
    
    # Verificar que el médico puede realizar este tipo de estudio
    if not medico.puede_realizar_estudio(pedido.tipo_estudio.nombre if pedido.tipo_estudio else ''):
        return JsonResponse({
            'error': 'No puedes realizar este tipo de estudio según tu especialidad'
        }, status=403)
    
    # Cambiar estado
    pedido.estado = 'REALIZADO'
    pedido.fecha_realizacion = timezone.now()
    
    # Asignar el médico si no estaba asignado
    if not pedido.medico_asignado:
        pedido.medico_asignado = request.user
    
    pedido.save()
    
    messages.success(
        request,
        f'Estudio marcado como realizado: {pedido.paciente.nombre_completo} - '
        f'{pedido.tipo_estudio.nombre if pedido.tipo_estudio else pedido.descripcion_estudio}'
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'mensaje': 'Estudio marcado como realizado'
        })
    
    return redirect('pedidos_estudios:mis_estudios')


def mis_estudios_token(request, token):
    """
    Vista para médicos externos (sin login) usando token de acceso.
    No requiere autenticación.
    """
    # Buscar médico por token
    try:
        medico = MedicoGuardia.objects.get(token_acceso=token)
    except MedicoGuardia.DoesNotExist:
        messages.error(
            request,
            "Token de acceso inválido o expirado. Contacta al administrador."
        )
        return render(request, 'pedidos_estudios/token_invalido.html', status=403)
    
    # Verificar que esté activo
    if not medico.activo:
        messages.warning(
            request,
            "Tu perfil de médico está inactivo. "
            "Contacta al administrador para activarlo."
        )
    
    # Filtrar estudios según especialidad (igual que la vista con login)
    estudios = PedidoEstudio.objects.select_related(
        'paciente', 'tipo_estudio', 'medico_asignado'
    ).exclude(
        estado='REALIZADO'
    ).order_by('-prioridad', 'fecha_solicitud')
    
    # Aplicar filtro por especialidad
    if medico.especialidad == 'DOPPLER':
        estudios = estudios.filter(
            Q(tipo_estudio__nombre__icontains='doppler') &
            ~Q(tipo_estudio__nombre__icontains='ecocardio')
        )
    elif medico.especialidad == 'ECOCARDIO':
        estudios = estudios.filter(
            Q(tipo_estudio__nombre__icontains='ecocardio') |
            Q(tipo_estudio__nombre__icontains='eco cardio')
        )
    
    # Estadísticas
    total_estudios = estudios.count()
    urgentes = estudios.filter(prioridad='URGENTE').count()
    hoy = timezone.localtime(timezone.now()).date()
    estudios_hoy = estudios.filter(fecha_solicitud__date=hoy).count()
    
    context = {
        'medico': medico,
        'estudios': estudios,
        'total_estudios': total_estudios,
        'urgentes': urgentes,
        'estudios_hoy': estudios_hoy,
        'token': token,  # Para usar en los formularios
        'es_acceso_token': True,  # Flag para identificar tipo de acceso
    }
    
    return render(request, 'pedidos_estudios/mis_estudios.html', context)


def marcar_realizado_token(request, token, pedido_id):
    """
    Marca un estudio como realizado usando token (sin login).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    # Verificar token
    try:
        medico = MedicoGuardia.objects.get(token_acceso=token)
    except MedicoGuardia.DoesNotExist:
        return JsonResponse({
            'error': 'Token de acceso inválido'
        }, status=403)
    
    # Obtener el pedido
    pedido = get_object_or_404(PedidoEstudio, id=pedido_id)
    
    # Verificar que el médico puede realizar este tipo de estudio
    if not medico.puede_realizar_estudio(pedido.tipo_estudio.nombre if pedido.tipo_estudio else ''):
        return JsonResponse({
            'error': 'No puedes realizar este tipo de estudio según tu especialidad'
        }, status=403)
    
    # Cambiar estado
    pedido.estado = 'REALIZADO'
    pedido.fecha_realizacion = timezone.now()
    
    # Asignar el médico si no estaba asignado
    # Si el médico tiene usuario, usarlo; sino, guardar en observaciones
    if not pedido.medico_asignado and medico.usuario:
        pedido.medico_asignado = medico.usuario
    
    # Agregar observación sobre quién realizó el estudio (si no tiene usuario asignado)
    if not pedido.medico_asignado:
        nota_realizacion = f"\n[{timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')}] Realizado por: {medico.nombre_completo}"
        if pedido.observaciones:
            pedido.observaciones += nota_realizacion
        else:
            pedido.observaciones = nota_realizacion.strip()
    
    pedido.save()
    
    messages.success(
        request,
        f'Estudio marcado como realizado: {pedido.paciente.nombre_completo} - '
        f'{pedido.tipo_estudio.nombre if pedido.tipo_estudio else pedido.descripcion_estudio}'
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'mensaje': 'Estudio marcado como realizado'
        })
    
    return redirect('pedidos_estudios:mis_estudios_token', token=token)
