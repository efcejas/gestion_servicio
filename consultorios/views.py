# -*- coding: utf-8 -*-
"""
Vistas para la app consultorios.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView
from django.utils import timezone
from datetime import date, timedelta

from .models import (
    Consultorio,
    BloqueHorario,
    ProfesionalExterno,
    DiaSemana,
    EstadoBloque
)
from .utils import ConflictDetector


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
    ).order_by('consultorio', 'hora_inicio')[:10]
    
    context = {
        'total_consultorios': total_consultorios,
        'consultorios_activos': consultorios_activos,
        'total_bloques': total_bloques,
        'total_profesionales_externos': total_profesionales_externos,
        'consultorios_top': consultorios_top,
        'bloques_hoy': bloques_hoy,
        'dia_hoy': DiaSemana(dia_semana_hoy).label,
        'fecha_hoy': hoy,
    }
    
    return render(request, 'consultorios/dashboard.html', context)

