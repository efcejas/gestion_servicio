# -*- coding: utf-8 -*-
"""
Utilidades para detección de conflictos en el sistema de consultorios.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import BloqueHorario


class ConflictDetector:
    """
    Clase para detectar y reportar conflictos en la asignación de bloques horarios.
    """
    
    @staticmethod
    def _vigencias_se_superponen(fecha_inicio_a, fecha_fin_a, fecha_inicio_b, fecha_fin_b):
        """Determina si dos rangos de vigencia se superponen."""
        if not fecha_inicio_a or not fecha_inicio_b:
            return True

        fin_a = fecha_fin_a or fecha_inicio_b.__class__.max
        fin_b = fecha_fin_b or fecha_inicio_a.__class__.max
        return fecha_inicio_a <= fin_b and fecha_inicio_b <= fin_a

    @staticmethod
    def verificar_conflictos(consultorio, profesional_interno=None, profesional_externo=None,
                            dia_semana=None, hora_inicio=None, hora_fin=None, excluir_id=None,
                            fecha_inicio_vigencia=None, fecha_fin_vigencia=None):
        """
        Verifica todos los tipos de conflictos para un bloque horario.
        
        Args:
            consultorio: Instancia de Consultorio
            profesional_interno: Instancia de User (opcional)
            profesional_externo: Instancia de ProfesionalExterno (opcional)
            dia_semana: Día de la semana (0-6)
            hora_inicio: Hora de inicio
            hora_fin: Hora de fin
            excluir_id: ID de bloque a excluir (para ediciones)
        
        Returns:
            dict con estructura:
            {
                'tiene_conflictos': bool,
                'conflictos_consultorio': QuerySet,
                'conflictos_profesional': QuerySet,
                'mensajes': list
            }
        """
        resultado = {
            'tiene_conflictos': False,
            'conflictos_consultorio': None,
            'conflictos_profesional': None,
            'mensajes': []
        }
        
        # 1. Verificar conflictos en el consultorio
        conflictos_consultorio = BloqueHorario.objects.conflictos_consultorio(
            consultorio=consultorio,
            dia_semana=dia_semana,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            excluir_id=excluir_id
        )
        conflictos_consultorio = [
            conflicto for conflicto in conflictos_consultorio
            if ConflictDetector._vigencias_se_superponen(
                fecha_inicio_vigencia,
                fecha_fin_vigencia,
                conflicto.fecha_inicio_vigencia,
                conflicto.fecha_fin_vigencia,
            )
        ]
        
        if conflictos_consultorio:
            resultado['tiene_conflictos'] = True
            resultado['conflictos_consultorio'] = conflictos_consultorio
            
            for conflicto in conflictos_consultorio:
                prof_nombre = conflicto.nombre_profesional()
                resultado['mensajes'].append(
                    f"Conflicto en {consultorio.nombre}: {prof_nombre} ya tiene un bloque "
                    f"el {conflicto.get_dia_semana_display()} de {conflicto.hora_inicio} a {conflicto.hora_fin}"
                )
        
        # 2. Verificar conflictos del profesional
        conflictos_profesional = None
        
        if profesional_interno:
            conflictos_profesional = BloqueHorario.objects.conflictos_profesional_interno(
                user=profesional_interno,
                dia_semana=dia_semana,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                excluir_id=excluir_id
            )
        elif profesional_externo:
            conflictos_profesional = BloqueHorario.objects.conflictos_profesional_externo(
                profesional_externo=profesional_externo,
                dia_semana=dia_semana,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                excluir_id=excluir_id
            )
        if conflictos_profesional is not None:
            conflictos_profesional = [
                conflicto for conflicto in conflictos_profesional
                if ConflictDetector._vigencias_se_superponen(
                    fecha_inicio_vigencia,
                    fecha_fin_vigencia,
                    conflicto.fecha_inicio_vigencia,
                    conflicto.fecha_fin_vigencia,
                )
            ]
        
        if conflictos_profesional:
            resultado['tiene_conflictos'] = True
            resultado['conflictos_profesional'] = conflictos_profesional
            
            prof_nombre = profesional_interno.get_full_name() if profesional_interno else profesional_externo.nombre_completo()
            
            for conflicto in conflictos_profesional:
                resultado['mensajes'].append(
                    f"Conflicto de profesional: {prof_nombre} ya está asignado en "
                    f"{conflicto.consultorio.nombre} el {conflicto.get_dia_semana_display()} "
                    f"de {conflicto.hora_inicio} a {conflicto.hora_fin}"
                )
        
        return resultado
    
    @staticmethod
    def validar_bloque(bloque):
        """
        Valida un bloque horario completo antes de guardarlo.
        Lanza ValidationError si hay conflictos.
        
        Args:
            bloque: Instancia de BloqueHorario
        
        Raises:
            ValidationError: Si hay conflictos
        """
        profesional_interno = bloque.profesional_interno
        profesional_externo = bloque.profesional_externo
        
        resultado = ConflictDetector.verificar_conflictos(
            consultorio=bloque.consultorio,
            profesional_interno=profesional_interno,
            profesional_externo=profesional_externo,
            dia_semana=bloque.dia_semana,
            hora_inicio=bloque.hora_inicio,
            hora_fin=bloque.hora_fin,
            excluir_id=bloque.id if bloque.id else None,
            fecha_inicio_vigencia=bloque.fecha_inicio_vigencia,
            fecha_fin_vigencia=bloque.fecha_fin_vigencia,
        )
        
        if resultado['tiene_conflictos']:
            raise ValidationError({
                '__all__': resultado['mensajes']
            })
    
    @staticmethod
    def obtener_disponibilidad_consultorio(consultorio, dia_semana, hora_inicio=None, hora_fin=None, fecha=None):
        """
        Obtiene información sobre la disponibilidad de un consultorio.
        
        Args:
            consultorio: Instancia de Consultorio
            dia_semana: Día de la semana (0-6)
            hora_inicio: Hora inicio para verificar (opcional)
            hora_fin: Hora fin para verificar (opcional)
        
        Returns:
            dict con información de disponibilidad
        """
        fecha = fecha or timezone.now().date()
        bloques_dia = BloqueHorario.objects.vigentes(fecha).filter(
            consultorio=consultorio,
            dia_semana=dia_semana
        ).order_by('hora_inicio')
        
        disponibilidad = {
            'consultorio': consultorio.nombre,
            'dia': dia_semana,
            'bloques_ocupados': [],
            'esta_disponible': True
        }
        
        for bloque in bloques_dia:
            disponibilidad['bloques_ocupados'].append({
                'profesional': bloque.nombre_profesional(),
                'hora_inicio': bloque.hora_inicio,
                'hora_fin': bloque.hora_fin,
                'tipo_actividad': bloque.get_tipo_actividad_display()
            })
            
            # Si se especificó un rango, verificar solapamiento
            if hora_inicio and hora_fin:
                if bloque.hora_inicio < hora_fin and bloque.hora_fin > hora_inicio:
                    disponibilidad['esta_disponible'] = False
        
        return disponibilidad
    
    @staticmethod
    def sugerir_horarios_disponibles(consultorio, dia_semana, duracion_horas=4, fecha=None):
        """
        Sugiere horarios disponibles en un consultorio para un día específico.
        
        Args:
            consultorio: Instancia de Consultorio
            dia_semana: Día de la semana (0-6)
            duracion_horas: Duración deseada del bloque en horas
        
        Returns:
            list de tuplas (hora_inicio, hora_fin) sugeridas
        """
        from datetime import time, datetime, timedelta
        from django.utils import timezone

        fecha = fecha or timezone.now().date()
        
        bloques_ocupados = BloqueHorario.objects.vigentes(fecha).filter(
            consultorio=consultorio,
            dia_semana=dia_semana
        ).order_by('hora_inicio')
        
        # Horario de trabajo típico: 8:00 a 20:00
        hora_apertura = time(8, 0)
        hora_cierre = time(20, 0)
        
        sugerencias = []
        
        # Convertir a datetime para facilitar cálculos
        fecha_base = datetime.today()
        inicio_jornada = datetime.combine(fecha_base, hora_apertura)
        fin_jornada = datetime.combine(fecha_base, hora_cierre)
        duracion_delta = timedelta(hours=duracion_horas)
        
        # Si no hay bloques, toda la jornada está disponible
        if not bloques_ocupados.exists():
            tiempo_actual = inicio_jornada
            while tiempo_actual + duracion_delta <= fin_jornada:
                sugerencias.append((
                    tiempo_actual.time(),
                    (tiempo_actual + duracion_delta).time()
                ))
                tiempo_actual += timedelta(hours=1)  # Incrementar cada hora
            
            return sugerencias[:5]  # Retornar máximo 5 sugerencias
        
        # Buscar espacios libres entre bloques ocupados
        tiempo_actual = inicio_jornada
        
        for bloque in bloques_ocupados:
            bloque_inicio = datetime.combine(fecha_base, bloque.hora_inicio)
            bloque_fin = datetime.combine(fecha_base, bloque.hora_fin)
            
            # Verificar si hay espacio antes del bloque ocupado
            while tiempo_actual + duracion_delta <= bloque_inicio:
                sugerencias.append((
                    tiempo_actual.time(),
                    (tiempo_actual + duracion_delta).time()
                ))
                tiempo_actual += timedelta(hours=1)
                
                if len(sugerencias) >= 5:
                    return sugerencias
            
            # Avanzar al final del bloque ocupado
            tiempo_actual = max(tiempo_actual, bloque_fin)
        
        # Verificar espacio después del último bloque
        while tiempo_actual + duracion_delta <= fin_jornada:
            sugerencias.append((
                tiempo_actual.time(),
                (tiempo_actual + duracion_delta).time()
            ))
            tiempo_actual += timedelta(hours=1)
            
            if len(sugerencias) >= 5:
                break
        
        return sugerencias


def formatear_conflictos_html(resultado_conflictos):
    """
    Formatea los conflictos detectados en HTML para mostrar en el admin.
    
    Args:
        resultado_conflictos: Resultado del método verificar_conflictos()
    
    Returns:
        str con HTML formateado
    """
    if not resultado_conflictos['tiene_conflictos']:
        return '<span style="color: green;">✓ Sin conflictos</span>'
    
    html = '<div style="color: red; font-weight: bold;">⚠ CONFLICTOS DETECTADOS:</div><ul>'
    
    for mensaje in resultado_conflictos['mensajes']:
        html += f'<li>{mensaje}</li>'
    
    html += '</ul>'
    
    return html
