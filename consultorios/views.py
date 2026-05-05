# -*- coding: utf-8 -*-
"""
Vistas para la app consultorios.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model

from .models import (
    AccionEGES,
    AusenciaCobertura,
    BloqueHorario,
    Consultorio,
    DiaSemana,
    EstadoAusenciaCobertura,
    EstadoBloque,
    EstadoSolicitudExtra,
    EstadoTareaEGES,
    OrigenTareaEGES,
    ProfesionalExterno,
    SolicitudAgendaExtra,
    TareaAgendaEGES,
    TipoActividad,
)
from .utils import ConflictDetector
from .forms import BloqueHorarioForm, AusenciaCoberturaForm, ConsultorioForm, ProfesionalExternoForm
from .services import sugerir_cobertura, SinResidentesDisponiblesError, BloqueNoCubreError

User = get_user_model()


def usuario_puede_gestionar_bloques(user):
    """Permisos para alta/edición de bloques en UI operativa."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.rol in {
        'jefe_servicio',
        'administrativo',
        'jefe_residentes',
        'instructor_residentes',
        'medico_staff',
    }


class GestionBloquesMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restringe la gestión de bloques a perfiles operativos autorizados."""

    def test_func(self):
        return usuario_puede_gestionar_bloques(self.request.user)


class ConsultoriosListView(LoginRequiredMixin, ListView):
    """
    Vista de lista de consultorios con información de disponibilidad.
    """
    model = Consultorio
    template_name = 'consultorios/consultorios_list.html'
    context_object_name = 'consultorios'
    
    def get_queryset(self):
        """Solo consultorios activos con estadísticas"""
        return Consultorio.objects.disponibilidad_resumida().filter(esta_activo=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_consultorios'] = Consultorio.objects.count()
        context['consultorios_activos'] = Consultorio.objects.activos().count()
        context['total_bloques_activos'] = BloqueHorario.objects.activos().count()
        context['puede_gestionar_bloques'] = usuario_puede_gestionar_bloques(self.request.user)
        return context


class ConsultorioDetailView(LoginRequiredMixin, DetailView):
    """
    Vista de detalle de un consultorio mostrando disponibilidad semanal.
    """
    model = Consultorio
    template_name = 'consultorios/consultorio_detail.html'
    context_object_name = 'consultorio'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        consultorio = self.object
        
        # Obtener bloques activos agrupados por día
        dias_semana = []
        for dia in DiaSemana:
            bloques = BloqueHorario.objects.activos().filter(
                consultorio=consultorio,
                dia_semana=dia.value
            ).order_by('hora_inicio').select_related(
                'profesional_interno',
                'profesional_externo',
                'equipo'
            )
            
            # Calcular ocupación del día
            total_horas = sum(bloque.duracion_horas() for bloque in bloques)
            
            dias_semana.append({
                'dia': dia.label,
                'dia_value': dia.value,
                'bloques': bloques,
                'total_horas': total_horas,
                'tiene_bloques': bloques.exists()
            })
        
        context['dias_semana'] = dias_semana
        
        # Equipos asignados
        context['equipos_asignados'] = consultorio.equipos_asignados()
        
        # Estadísticas
        context['total_bloques'] = BloqueHorario.objects.activos().filter(
            consultorio=consultorio
        ).count()
        
        # Ocupación semanal
        ocupacion = BloqueHorario.objects.ocupacion_semanal(consultorio)
        context['ocupacion_semanal'] = ocupacion
        context['total_horas_semana'] = sum(ocupacion.values())
        context['puede_gestionar_bloques'] = usuario_puede_gestionar_bloques(self.request.user)
        
        return context


class BloqueHorarioCreateView(GestionBloquesMixin, CreateView):
    """Alta operativa de bloques horarios desde la UI del módulo."""
    model = BloqueHorario
    form_class = BloqueHorarioForm
    template_name = 'consultorios/bloque_form.html'

    def get_initial(self):
        initial = super().get_initial()
        consultorio_id = self.request.GET.get('consultorio')
        dia_semana = self.request.GET.get('dia_semana')

        if consultorio_id:
            initial['consultorio'] = consultorio_id
        if dia_semana is not None:
            initial['dia_semana'] = dia_semana

        return initial

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'consultorios:disponibilidad_dia',
            kwargs={
                'pk': self.object.consultorio_id,
                'dia_semana': self.object.dia_semana,
            }
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Crear Bloque Horario'
        context['boton_accion'] = 'Crear bloque'
        return context


class BloqueHorarioUpdateView(GestionBloquesMixin, UpdateView):
    """Edición operativa de bloques horarios."""
    model = BloqueHorario
    form_class = BloqueHorarioForm
    template_name = 'consultorios/bloque_form.html'

    def get_success_url(self):
        return reverse(
            'consultorios:disponibilidad_dia',
            kwargs={
                'pk': self.object.consultorio_id,
                'dia_semana': self.object.dia_semana,
            }
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Bloque Horario'
        context['boton_accion'] = 'Guardar cambios'
        return context


@login_required
def disponibilidad_consultorio_dia(request, pk, dia_semana):
    """
    Vista que muestra la disponibilidad de un consultorio en un día específico.
    """
    consultorio = get_object_or_404(Consultorio, pk=pk)
    
    # Obtener nombre del día
    try:
        dia_obj = DiaSemana(int(dia_semana))
        dia_nombre = dia_obj.label
    except (ValueError, KeyError):
        dia_nombre = f"Día {dia_semana}"
    
    # Obtener bloques del día
    bloques = BloqueHorario.objects.activos().filter(
        consultorio=consultorio,
        dia_semana=dia_semana
    ).order_by('hora_inicio').select_related(
        'profesional_interno',
        'profesional_externo',
        'equipo'
    )
    
    # Calcular estadísticas
    total_horas = sum(bloque.duracion_horas() for bloque in bloques)
    profesionales_distintos = len(set(
        [b.profesional_interno_id for b in bloques if b.profesional_interno] +
        [b.profesional_externo_id for b in bloques if b.profesional_externo]
    ))
    
    # Obtener disponibilidad
    disponibilidad = ConflictDetector.obtener_disponibilidad_consultorio(
        consultorio=consultorio,
        dia_semana=int(dia_semana)
    )
    
    # Sugerencias de horarios disponibles
    sugerencias = ConflictDetector.sugerir_horarios_disponibles(
        consultorio=consultorio,
        dia_semana=int(dia_semana),
        duracion_horas=4
    )
    
    # Equipos del consultorio
    equipos_disponibles = [asig.equipo for asig in consultorio.equipos_asignados()]
    
    # Todos los días para el selector
    todos_dias = [{'label': dia.label, 'value': dia.value} for dia in DiaSemana]
    
    context = {
        'consultorio': consultorio,
        'dia_semana': int(dia_semana),
        'dia_nombre': dia_nombre,
        'bloques_activos': bloques,
        'disponibilidad': disponibilidad,
        'horarios_sugeridos': sugerencias,
        'tiene_bloques': bloques.exists(),
        'total_horas': total_horas,
        'profesionales_distintos': profesionales_distintos,
        'equipos_disponibles': equipos_disponibles,
        'todos_dias': todos_dias,
        'puede_gestionar_bloques': usuario_puede_gestionar_bloques(request.user),
    }
    
    return render(request, 'consultorios/disponibilidad_dia.html', context)


@login_required
def dashboard_consultorios(request):
    """
    Dashboard general de consultorios con resumen visual.
    """
    # Estadísticas generales
    total_consultorios = Consultorio.objects.count()
    consultorios_activos = Consultorio.objects.activos().count()
    total_bloques = BloqueHorario.objects.activos().count()
    total_profesionales_externos = ProfesionalExterno.objects.activos().count()
    
    # Consultorios con más bloques
    consultorios_top = Consultorio.objects.disponibilidad_resumida().filter(esta_activo=True).order_by('-total_bloques')[:5]
    
    # Bloques de hoy
    hoy = timezone.now().date()
    dia_semana_hoy = hoy.weekday()
    bloques_hoy = BloqueHorario.objects.vigentes(hoy).filter(
        dia_semana=dia_semana_hoy
    ).select_related(
        'consultorio',
        'profesional_interno',
        'profesional_externo'
    ).order_by('consultorio__nombre', 'hora_inicio')[:10]

    # Mostrar solo bloques relevantes para operación (internos médicos o externos activos)
    bloques_hoy = [
        b for b in bloques_hoy
        if (
            b.profesional_externo_id or
            (b.profesional_interno_id and b.profesional_interno.rol in {
                'medico_staff',
                'jefe_residentes',
                'instructor_residentes',
                'medico_residente',
            })
        )
    ]
    
    context = {
        'total_consultorios': total_consultorios,
        'consultorios_activos': consultorios_activos,
        'total_bloques': total_bloques,
        'total_profesionales_externos': total_profesionales_externos,
        'consultorios_top': consultorios_top,
        'bloques_hoy': bloques_hoy,
        'dia_hoy': DiaSemana(dia_semana_hoy).label,
        'fecha_hoy': hoy,
        'puede_gestionar_bloques': usuario_puede_gestionar_bloques(request.user),
    }
    
    return render(request, 'consultorios/dashboard.html', context)


@login_required
def grilla_semanal(request):
    """
    Grilla semanal: matriz consultorios × días con los bloques de cada celda.

    Estructura de contexto:
      grilla = [
        {
          'consultorio': <Consultorio>,
          'dias': [
            {
              'dia': DiaSemana,
              'dia_value': int,
              'bloques': [<BloqueHorario>, ...],
              'es_hoy': bool,
            },
            ...  # 7 entradas, Lun-Dom
          ]
        },
        ...
      ]
    """
    hoy_dia_semana = timezone.now().date().weekday()  # 0=Lunes

    consultorios_activos = (
        Consultorio.objects.activos()
        .order_by('nombre')
    )

    # Prefetch de todos los bloques activos para evitar N+1
    todos_bloques = (
        BloqueHorario.objects.activos()
        .select_related('profesional_interno', 'profesional_externo')
        .order_by('hora_inicio')
    )

    # Indexar: {(consultorio_id, dia_semana): [bloque, ...]}
    indice = {}
    for bloque in todos_bloques:
        key = (bloque.consultorio_id, bloque.dia_semana)
        indice.setdefault(key, []).append(bloque)

    dias = list(DiaSemana)

    grilla = []
    for consultorio in consultorios_activos:
        dias_fila = []
        for dia in dias:
            bloques_celda = indice.get((consultorio.pk, dia.value), [])
            dias_fila.append({
                'dia': dia,
                'dia_value': dia.value,
                'bloques': bloques_celda,
                'es_hoy': dia.value == hoy_dia_semana,
            })
        grilla.append({
            'consultorio': consultorio,
            'dias': dias_fila,
        })

    dias_cabecera = [
        {'label': dia.label, 'value': dia.value, 'es_hoy': dia.value == hoy_dia_semana}
        for dia in dias
    ]

    context = {
        'grilla': grilla,
        'dias_cabecera': dias_cabecera,
        'puede_gestionar_bloques': usuario_puede_gestionar_bloques(request.user),
    }
    return render(request, 'consultorios/grilla_semanal.html', context)


# ---------------------------------------------------------------------------
# Circuito ausencias / coberturas
# ---------------------------------------------------------------------------

def _fechas_del_bloque_en_rango(dia_semana: int, fecha_inicio, fecha_fin):
    """
    Retorna la lista de fechas en [fecha_inicio, fecha_fin] cuyo weekday()
    coincide con dia_semana (0=Lunes … 6=Domingo).
    Límite de seguridad: máximo 365 días de rango.
    """
    from datetime import timedelta
    if fecha_fin < fecha_inicio:
        return []
    delta = (fecha_fin - fecha_inicio).days
    delta = min(delta, 364)  # tope de seguridad
    return [
        fecha_inicio + timedelta(days=i)
        for i in range(delta + 1)
        if (fecha_inicio + timedelta(days=i)).weekday() == dia_semana
    ]


@login_required
def reportar_ausencia(request, pk):
    """
    GET : Muestra el formulario para reportar ausencia (puntual o rango).
    POST: Para un día único → crea 1 AusenciaCobertura y muestra candidatos inline.
          Para un rango   → detecta las fechas del día de semana del bloque dentro
                            del rango, crea un registro por cada una y redirige a
                            la grilla con mensaje resumen.
    """
    if not usuario_puede_gestionar_bloques(request.user):
        raise PermissionDenied

    bloque = get_object_or_404(
        BloqueHorario.objects.select_related(
            'consultorio', 'profesional_interno', 'profesional_externo'
        ),
        pk=pk,
    )

    form = AusenciaCoberturaForm(request.POST or None)
    ausencia = None
    candidatos = None
    advertencias = []
    error_cobertura = None
    ausencia_existente = None

    if request.method == 'POST' and form.is_valid():
        fecha_inicio = form.cleaned_data['fecha_ausencia']
        fecha_fin = form.cleaned_data.get('fecha_fin_ausencia')
        motivo = form.cleaned_data['motivo']
        detalle_motivo = form.cleaned_data.get('detalle_motivo', '')

        es_rango = bool(fecha_fin and fecha_fin != fecha_inicio)

        if es_rango:
            # ── Modo rango: generar una ausencia por cada ocurrencia del día ──
            fechas = _fechas_del_bloque_en_rango(bloque.dia_semana, fecha_inicio, fecha_fin)
            creadas = 0
            omitidas = 0
            for fecha in fechas:
                if AusenciaCobertura.objects.filter(bloque=bloque, fecha_ausencia=fecha).exists():
                    omitidas += 1
                    continue
                nueva = AusenciaCobertura(
                    bloque=bloque,
                    fecha_ausencia=fecha,
                    fecha_fin_ausencia=fecha_fin,
                    profesional_ausente_interno=bloque.profesional_interno,
                    profesional_ausente_externo=bloque.profesional_externo,
                    motivo=motivo,
                    detalle_motivo=detalle_motivo,
                    estado=EstadoAusenciaCobertura.REPORTADA,
                    reportado_por=request.user,
                )
                nueva.save()
                # Proponer cobertura para el primero disponible
                if bloque.permite_cobertura_residente:
                    try:
                        res = sugerir_cobertura(bloque, fecha)
                        if res['candidatos']:
                            nueva.residente_sugerido = res['candidatos'][0]['usuario']
                            nueva.estado = EstadoAusenciaCobertura.PROPUESTA
                            nueva.save(update_fields=['residente_sugerido', 'estado', 'fecha_modificacion'])
                    except (SinResidentesDisponiblesError, BloqueNoCubreError):
                        pass
                creadas += 1

            partes = [f'{creadas} ausencia{"s" if creadas != 1 else ""} registrada{"s" if creadas != 1 else ""}']
            if omitidas:
                partes.append(f'{omitidas} ya existía{"n" if omitidas != 1 else ""}')
            messages.success(request, f'{bloque.nombre_profesional} — {", ".join(partes)} ({fecha_inicio} → {fecha_fin}).')
            return redirect('consultorios:grilla_semanal')

        else:
            # ── Modo día único: mostrar candidatos inline ──
            try:
                ausencia_existente = AusenciaCobertura.objects.get(
                    bloque=bloque, fecha_ausencia=fecha_inicio
                )
                form.add_error(
                    'fecha_ausencia',
                    'Ya existe una ausencia registrada para este bloque en esa fecha.'
                )
            except AusenciaCobertura.DoesNotExist:
                ausencia = AusenciaCobertura(
                    bloque=bloque,
                    fecha_ausencia=fecha_inicio,
                    profesional_ausente_interno=bloque.profesional_interno,
                    profesional_ausente_externo=bloque.profesional_externo,
                    motivo=motivo,
                    detalle_motivo=detalle_motivo,
                    estado=EstadoAusenciaCobertura.REPORTADA,
                    reportado_por=request.user,
                )
                ausencia.save()

                if bloque.permite_cobertura_residente:
                    try:
                        resultado = sugerir_cobertura(bloque, fecha_inicio)
                        candidatos = resultado['candidatos']
                        advertencias = resultado.get('advertencias', [])
                        if candidatos:
                            ausencia.residente_sugerido = candidatos[0]['usuario']
                            ausencia.estado = EstadoAusenciaCobertura.PROPUESTA
                            ausencia.save(update_fields=['residente_sugerido', 'estado', 'fecha_modificacion'])
                    except (SinResidentesDisponiblesError, BloqueNoCubreError) as exc:
                        error_cobertura = str(exc)

    return render(request, 'consultorios/reportar_ausencia.html', {
        'bloque': bloque,
        'form': form,
        'ausencia': ausencia,
        'candidatos': candidatos,
        'advertencias': advertencias,
        'error_cobertura': error_cobertura,
        'ausencia_existente': ausencia_existente,
    })


@require_POST
@login_required
def confirmar_cobertura(request, ausencia_pk, residente_pk):
    """
    POST: Confirma la cobertura de una ausencia asignando al residente elegido.
    Actualiza estado → CONFIRMADA y residente_asignado.
    """
    if not usuario_puede_gestionar_bloques(request.user):
        raise PermissionDenied

    ausencia = get_object_or_404(AusenciaCobertura, pk=ausencia_pk)
    residente = get_object_or_404(User, pk=residente_pk, is_active=True)

    if getattr(residente, 'rol', None) != 'medico_residente':
        raise PermissionDenied

    ausencia.residente_asignado = residente
    ausencia.estado = EstadoAusenciaCobertura.CONFIRMADA
    ausencia.save()

    nombre = residente.get_full_name() or residente.username
    messages.success(request, f'Cobertura confirmada: {nombre} cubrirá el bloque del {ausencia.fecha_ausencia}.')
    return redirect('consultorios:ausencias_pendientes')


@login_required
def ausencias_pendientes(request):
    """Lista de ausencias sin cobertura confirmada, ordenadas por fecha."""
    if not usuario_puede_gestionar_bloques(request.user):
        raise PermissionDenied

    ausencias = (
        AusenciaCobertura.objects
        .filter(estado__in=[EstadoAusenciaCobertura.REPORTADA, EstadoAusenciaCobertura.PROPUESTA])
        .select_related(
            'bloque__consultorio',
            'bloque__profesional_interno',
            'bloque__profesional_externo',
            'profesional_ausente_interno',
            'profesional_ausente_externo',
            'residente_sugerido',
            'reportado_por',
        )
        .order_by('fecha_ausencia', 'bloque__consultorio__nombre')
    )

    return render(request, 'consultorios/ausencias_pendientes.html', {
        'ausencias': ausencias,
        'total': ausencias.count(),
    })


@login_required
def ausencias_historial(request):
    """Historial completo de ausencias con filtros básicos."""
    if not usuario_puede_gestionar_bloques(request.user):
        raise PermissionDenied

    estado_filter = request.GET.get('estado', '')
    consultorio_filter = request.GET.get('consultorio', '')

    ausencias = (
        AusenciaCobertura.objects
        .select_related(
            'bloque__consultorio',
            'bloque__profesional_interno',
            'bloque__profesional_externo',
            'profesional_ausente_interno',
            'profesional_ausente_externo',
            'residente_asignado',
            'residente_sugerido',
            'reportado_por',
        )
        .order_by('-fecha_ausencia', 'bloque__consultorio__nombre')
    )

    if estado_filter:
        ausencias = ausencias.filter(estado=estado_filter)
    if consultorio_filter:
        ausencias = ausencias.filter(bloque__consultorio_id=consultorio_filter)

    consultorios = Consultorio.objects.activos().order_by('nombre')

    return render(request, 'consultorios/ausencias_historial.html', {
        'ausencias': ausencias,
        'total': ausencias.count(),
        'consultorios': consultorios,
        'estados': EstadoAusenciaCobertura.choices,
        'estado_filter': estado_filter,
        'consultorio_filter': consultorio_filter,
    })


# ---------------------------------------------------------------------------
# CRUD Consultorios (salas)
# ---------------------------------------------------------------------------

class ConsultorioCreateView(GestionBloquesMixin, CreateView):
    model = Consultorio
    form_class = ConsultorioForm
    template_name = 'consultorios/consultorio_form.html'

    def get_success_url(self):
        return reverse('consultorios:lista')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Consultorio'
        ctx['boton_accion'] = 'Crear consultorio'
        return ctx


class ConsultorioUpdateView(GestionBloquesMixin, UpdateView):
    model = Consultorio
    form_class = ConsultorioForm
    template_name = 'consultorios/consultorio_form.html'

    def get_success_url(self):
        return reverse('consultorios:detalle', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar — {self.object.nombre}'
        ctx['boton_accion'] = 'Guardar cambios'
        return ctx


# ---------------------------------------------------------------------------
# CRUD Profesionales Externos
# ---------------------------------------------------------------------------

@login_required
def profesionales_lista(request):
    """Lista de profesionales externos. Cualquier usuario logueado puede ver; solo gestores pueden editar."""
    puede_gestionar = usuario_puede_gestionar_bloques(request.user)

    profesionales = ProfesionalExterno.objects.order_by('apellido', 'nombre').select_related()
    solo_activos = request.GET.get('activos', '1') == '1'
    if solo_activos:
        profesionales = profesionales.filter(esta_activo=True)

    return render(request, 'consultorios/profesionales_lista.html', {
        'profesionales': profesionales,
        'solo_activos': solo_activos,
        'total': profesionales.count(),
        'puede_gestionar': puede_gestionar,
    })


class ProfesionalExternoCreateView(GestionBloquesMixin, CreateView):
    model = ProfesionalExterno
    form_class = ProfesionalExternoForm
    template_name = 'consultorios/profesional_form.html'

    def get_success_url(self):
        return reverse('consultorios:profesionales_lista')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Profesional Externo'
        ctx['boton_accion'] = 'Agregar profesional'
        return ctx


class ProfesionalExternoUpdateView(GestionBloquesMixin, UpdateView):
    model = ProfesionalExterno
    form_class = ProfesionalExternoForm
    template_name = 'consultorios/profesional_form.html'

    def get_success_url(self):
        return reverse('consultorios:profesionales_lista')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar — {self.object.nombre_completo()}'
        ctx['boton_accion'] = 'Guardar cambios'
        return ctx


# ---------------------------------------------------------------------------
# Bandeja EGES (administrativas)
# ---------------------------------------------------------------------------

def _es_administrativo(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return getattr(user, 'rol', None) in {'administrativo', 'jefe_servicio'}


def _es_jefe_servicio(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return getattr(user, 'rol', None) == 'jefe_servicio'


@login_required
def bandeja_eges(request):
    """
    Bandeja de TareaAgendaEGES pendientes para la administrativa.
    Muestra las tareas PENDIENTE ordenadas por fecha de creación.
    """
    if not _es_administrativo(request.user):
        raise PermissionDenied

    tareas = (
        TareaAgendaEGES.objects
        .filter(estado=EstadoTareaEGES.PENDIENTE)
        .select_related('consultorio', 'profesional_interno', 'profesional_externo', 'creado_por')
        .order_by('fecha_creacion')
    )

    return render(request, 'consultorios/bandeja_eges.html', {
        'tareas': tareas,
        'total_pendientes': tareas.count(),
    })


@require_POST
@login_required
def marcar_tarea_ejecutada(request, pk):
    """
    POST: Marca una TareaAgendaEGES como EJECUTADO.
    Captura notas opcionales de la administrativa.
    """
    if not _es_administrativo(request.user):
        raise PermissionDenied

    tarea = get_object_or_404(TareaAgendaEGES, pk=pk)

    if tarea.estado != EstadoTareaEGES.PENDIENTE:
        messages.warning(request, 'Esta tarea ya fue ejecutada anteriormente.')
        return redirect('consultorios:bandeja_eges')

    notas = request.POST.get('notas_ejecucion', '').strip()
    tarea.marcar_ejecutada(usuario=request.user, notas=notas)

    messages.success(
        request,
        f'Tarea marcada como ejecutada en EGES: {tarea.get_accion_display()} — {tarea.consultorio.nombre}.'
    )
    return redirect('consultorios:bandeja_eges')


@login_required
def historial_eges(request):
    """Historial de tareas EGES ejecutadas, visible para administrativos y jefatura."""
    if not _es_administrativo(request.user):
        raise PermissionDenied

    tareas = (
        TareaAgendaEGES.objects
        .filter(estado=EstadoTareaEGES.EJECUTADO)
        .select_related('consultorio', 'profesional_interno', 'profesional_externo', 'ejecutado_por')
        .order_by('-fecha_ejecucion')
    )

    return render(request, 'consultorios/historial_eges.html', {
        'tareas': tareas,
        'total': tareas.count(),
    })


# ---------------------------------------------------------------------------
# Solicitudes de agenda extra (jefe_servicio aprueba/rechaza)
# ---------------------------------------------------------------------------

@login_required
def solicitudes_extra_lista(request):
    """
    Lista de solicitudes de agenda extra.
    - Jefe de servicio: ve todas.
    - Otros roles: ve solo las propias.
    """
    es_jefe = _es_jefe_servicio(request.user)

    if es_jefe:
        solicitudes = SolicitudAgendaExtra.objects.select_related(
            'consultorio', 'profesional_interno', 'profesional_externo',
            'solicitante', 'resuelto_por', 'tarea_eges',
        ).order_by('-fecha_creacion')
    else:
        solicitudes = SolicitudAgendaExtra.objects.filter(
            solicitante=request.user
        ).select_related(
            'consultorio', 'profesional_interno', 'profesional_externo', 'tarea_eges',
        ).order_by('-fecha_creacion')

    pendientes = solicitudes.filter(estado=EstadoSolicitudExtra.PENDIENTE)

    return render(request, 'consultorios/solicitudes_extra_lista.html', {
        'solicitudes': solicitudes,
        'pendientes': pendientes,
        'total_pendientes': pendientes.count(),
        'es_jefe': es_jefe,
    })


@login_required
def solicitud_extra_nueva(request):
    """Formulario para crear una nueva solicitud de agenda extra."""
    from .forms import SolicitudAgendaExtraForm

    form = SolicitudAgendaExtraForm(request.POST or None, user=request.user)

    if request.method == 'POST' and form.is_valid():
        solicitud = form.save(commit=False)
        solicitud.solicitante = request.user
        solicitud.save()
        messages.success(
            request,
            f'Solicitud registrada para el {solicitud.fecha_solicitada}. '
            'El jefe de servicio recibirá la notificación.'
        )
        return redirect('consultorios:solicitudes_extra_lista')

    return render(request, 'consultorios/solicitud_extra_form.html', {
        'form': form,
        'titulo': 'Nueva solicitud de agenda extra',
        'boton_accion': 'Enviar solicitud',
    })


@require_POST
@login_required
def resolver_solicitud_extra(request, pk):
    """
    POST: Jefe aprueba o rechaza una SolicitudAgendaExtra.
    action = 'aprobar' | 'rechazar'
    """
    if not _es_jefe_servicio(request.user):
        raise PermissionDenied

    solicitud = get_object_or_404(SolicitudAgendaExtra, pk=pk)
    accion = request.POST.get('accion', '')
    observaciones = request.POST.get('observaciones_resolucion', '').strip()

    if accion == 'aprobar':
        try:
            solicitud.aprobar(jefe=request.user)
            messages.success(
                request,
                f'Solicitud aprobada. Se generó una tarea EGES para habilitar la agenda del {solicitud.fecha_solicitada}.'
            )
        except Exception as exc:
            messages.error(request, f'No se pudo aprobar: {exc}')

    elif accion == 'rechazar':
        try:
            solicitud.rechazar(jefe=request.user, observaciones=observaciones)
            messages.info(request, 'Solicitud rechazada.')
        except Exception as exc:
            messages.error(request, f'No se pudo rechazar: {exc}')

    else:
        messages.error(request, 'Acción no reconocida.')

    return redirect('consultorios:solicitudes_extra_lista')


# ---------------------------------------------------------------------------
# Agendas descubiertas (jefe de servicio)
# ---------------------------------------------------------------------------

@login_required
def agendas_descubiertas(request):
    """
    Vista para el jefe: bloques con ausencias sin cobertura confirmada
    en las próximas N semanas.
    """
    from datetime import timedelta

    user = request.user
    if not (user.is_superuser or getattr(user, 'rol', None) == 'jefe_servicio'):
        messages.error(request, 'No tienes permisos para ver agendas descubiertas.')
        return redirect('consultorios:dashboard')

    semanas = int(request.GET.get('semanas', 4))
    semanas = max(1, min(semanas, 12))

    hoy = timezone.now().date()
    hasta = hoy + timedelta(weeks=semanas)

    ausencias = (
        AusenciaCobertura.objects
        .filter(
            estado__in=[
                EstadoAusenciaCobertura.REPORTADA,
                EstadoAusenciaCobertura.PROPUESTA,
            ],
            fecha_ausencia__gte=hoy,
            fecha_ausencia__lte=hasta,
        )
        .select_related(
            'bloque__consultorio',
            'bloque__profesional_interno',
            'bloque__profesional_externo',
            'profesional_ausente_interno',
            'profesional_ausente_externo',
            'residente_sugerido',
        )
        .order_by('fecha_ausencia', 'bloque__consultorio__nombre')
    )

    from collections import defaultdict
    por_semana = defaultdict(list)
    for a in ausencias:
        lunes = a.fecha_ausencia - timedelta(days=a.fecha_ausencia.weekday())
        por_semana[lunes].append(a)

    semanas_lista = [
        {'lunes': lunes, 'ausencias': items}
        for lunes, items in sorted(por_semana.items())
    ]

    return render(request, 'consultorios/agendas_descubiertas.html', {
        'semanas_lista': semanas_lista,
        'total': len(ausencias),
        'semanas': semanas,
        'hasta': hasta,
        'opciones_semanas': [2, 4, 6, 8, 12],
    })

