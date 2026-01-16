# -*- coding: utf-8 -*-
"""
Managers personalizados para consultas complejas en el sistema de consultorios.
"""

from django.db import models
from django.db.models import Q, Count, F
from django.utils import timezone
from datetime import date, time, timedelta


class BloqueHorarioManager(models.Manager):
    """Manager personalizado para BloqueHorario con queries optimizadas"""
    
    def activos(self):
        """Retorna solo bloques activos"""
        return self.filter(estado='ACTIVO')
    
    def vigentes(self, fecha=None):
        """
        Retorna bloques vigentes en una fecha específica.
        Si no se especifica fecha, usa la fecha actual.
        """
        if fecha is None:
            fecha = timezone.now().date()
        
        return self.filter(
            estado='ACTIVO',
            fecha_inicio_vigencia__lte=fecha
        ).filter(
            Q(fecha_fin_vigencia__isnull=True) | Q(fecha_fin_vigencia__gte=fecha)
        )
    
    def por_consultorio(self, consultorio):
        """Retorna bloques de un consultorio específico"""
        return self.filter(consultorio=consultorio)
    
    def por_profesional_interno(self, user):
        """Retorna bloques de un profesional interno (usuario)"""
        return self.filter(profesional_interno=user)
    
    def por_profesional_externo(self, profesional_externo):
        """Retorna bloques de un profesional externo"""
        return self.filter(profesional_externo=profesional_externo)
    
    def por_dia_semana(self, dia_semana):
        """Retorna bloques de un día específico de la semana (0-6)"""
        return self.filter(dia_semana=dia_semana)
    
    def por_tipo_actividad(self, tipo_actividad):
        """Retorna bloques de un tipo de actividad específico"""
        return self.filter(tipo_actividad=tipo_actividad)
    
    def en_rango_horario(self, hora_inicio, hora_fin):
        """
        Retorna bloques que se superponen con un rango horario.
        """
        return self.filter(
            Q(hora_inicio__lt=hora_fin) & Q(hora_fin__gt=hora_inicio)
        )
    
    def disponibles_en_fecha(self, consultorio, fecha):
        """
        Retorna bloques disponibles en un consultorio para una fecha específica.
        """
        dia_semana = fecha.weekday()  # 0=Lunes, 6=Domingo
        
        return self.vigentes(fecha).filter(
            consultorio=consultorio,
            dia_semana=dia_semana
        ).select_related(
            'consultorio',
            'profesional_interno',
            'profesional_externo',
            'equipo'
        )
    
    def conflictos_consultorio(self, consultorio, dia_semana, hora_inicio, hora_fin, excluir_id=None):
        """
        Detecta conflictos de horario en un consultorio específico.
        
        Args:
            consultorio: Instancia de Consultorio
            dia_semana: Día de la semana (0-6)
            hora_inicio: Hora de inicio del bloque
            hora_fin: Hora de fin del bloque
            excluir_id: ID del bloque a excluir (para ediciones)
        
        Returns:
            QuerySet de bloques en conflicto
        """
        qs = self.activos().filter(
            consultorio=consultorio,
            dia_semana=dia_semana
        ).filter(
            Q(hora_inicio__lt=hora_fin) & Q(hora_fin__gt=hora_inicio)
        )
        
        if excluir_id:
            qs = qs.exclude(id=excluir_id)
        
        return qs.select_related('profesional_interno', 'profesional_externo')
    
    def conflictos_profesional_interno(self, user, dia_semana, hora_inicio, hora_fin, excluir_id=None):
        """
        Detecta conflictos de horario para un profesional interno.
        Un profesional no puede estar en dos consultorios al mismo tiempo.
        """
        qs = self.activos().filter(
            profesional_interno=user,
            dia_semana=dia_semana
        ).filter(
            Q(hora_inicio__lt=hora_fin) & Q(hora_fin__gt=hora_inicio)
        )
        
        if excluir_id:
            qs = qs.exclude(id=excluir_id)
        
        return qs.select_related('consultorio')
    
    def conflictos_profesional_externo(self, profesional_externo, dia_semana, hora_inicio, hora_fin, excluir_id=None):
        """
        Detecta conflictos de horario para un profesional externo.
        """
        qs = self.activos().filter(
            profesional_externo=profesional_externo,
            dia_semana=dia_semana
        ).filter(
            Q(hora_inicio__lt=hora_fin) & Q(hora_fin__gt=hora_inicio)
        )
        
        if excluir_id:
            qs = qs.exclude(id=excluir_id)
        
        return qs.select_related('consultorio')
    
    def ocupacion_semanal(self, consultorio):
        """
        Calcula las horas de ocupación por día de la semana para un consultorio.
        
        Returns:
            dict: {dia_semana: total_horas}
        """
        bloques = self.activos().filter(consultorio=consultorio)
        
        ocupacion = {dia: 0 for dia in range(7)}
        
        for bloque in bloques:
            duracion = bloque.duracion_horas()
            ocupacion[bloque.dia_semana] += duracion
        
        return ocupacion
    
    def resumen_por_consultorio(self):
        """
        Genera un resumen de bloques activos por consultorio.
        
        Returns:
            QuerySet anotado con conteo de bloques
        """
        from consultorios.models import Consultorio
        
        return Consultorio.objects.annotate(
            total_bloques=Count('bloques_horarios', filter=Q(bloques_horarios__estado='ACTIVO'))
        ).order_by('-total_bloques')
    
    def proximos_bloques(self, dias=7):
        """
        Retorna los bloques de los próximos N días.
        """
        hoy = timezone.now().date()
        fecha_limite = hoy + timedelta(days=dias)
        
        # Obtener los días de la semana en el rango
        bloques_proximos = []
        fecha_actual = hoy
        
        while fecha_actual <= fecha_limite:
            dia_semana = fecha_actual.weekday()
            bloques_dia = self.vigentes(fecha_actual).filter(dia_semana=dia_semana)
            bloques_proximos.extend(bloques_dia)
            fecha_actual += timedelta(days=1)
        
        return bloques_proximos


class ConsultorioManager(models.Manager):
    """Manager personalizado para Consultorio"""
    
    def activos(self):
        """Retorna solo consultorios activos"""
        return self.filter(esta_activo=True)
    
    def con_equipos(self):
        """Retorna consultorios que tienen equipos asignados"""
        return self.filter(asignaciones_equipos__isnull=False).distinct()
    
    def sin_equipos(self):
        """Retorna consultorios sin equipos asignados"""
        return self.exclude(asignaciones_equipos__isnull=False)
    
    def con_bloques_activos(self):
        """Retorna consultorios que tienen bloques horarios activos"""
        return self.filter(
            bloques_horarios__estado='ACTIVO'
        ).distinct()
    
    def disponibilidad_resumida(self):
        """
        Genera un resumen de disponibilidad para todos los consultorios.
        
        Returns:
            QuerySet anotado con estadísticas
        """
        return self.annotate(
            total_bloques=Count('bloques_horarios', filter=Q(bloques_horarios__estado='ACTIVO')),
            total_equipos=Count('asignaciones_equipos', filter=Q(asignaciones_equipos__es_permanente=True) | Q(
                asignaciones_equipos__fecha_inicio__lte=timezone.now().date(),
                asignaciones_equipos__fecha_fin__gte=timezone.now().date()
            ))
        ).order_by('nombre')


class ProfesionalExternoManager(models.Manager):
    """Manager personalizado para ProfesionalExterno"""
    
    def activos(self):
        """Retorna solo profesionales externos activos"""
        return self.filter(esta_activo=True)
    
    def con_bloques_activos(self):
        """Retorna profesionales externos que tienen bloques activos"""
        return self.filter(
            bloques_horarios__estado='ACTIVO'
        ).distinct()
    
    def por_especialidad(self, especialidad):
        """Retorna profesionales de una especialidad específica"""
        return self.filter(especialidad__icontains=especialidad)
