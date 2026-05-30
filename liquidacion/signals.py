"""
Signals para el módulo liquidacion/

Implementan comportamientos automáticos en base a eventos de modelos:
- Recálculo de montos cuando se editan estudios
- Validaciones automáticas
- Auditoría (quién cambió qué)
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import RegistroEstudiosPorMedico, RegistroEstudio
from .services import clasificar_horario_residencia_por_proxy
import logging

logger = logging.getLogger('liquidacion.signals')


@receiver(post_save, sender=RegistroEstudio)
def recalcular_cantidad_regiones_cuando_estudio_cambia(sender, instance, created, **kwargs):
    """
    Signal: Cuando se crea o modifica un RegistroEstudio,
    recalcula la cantidad_regiones del registro padre.
    
    Ejemplo:
    - Dr. registra: ECO ABDOMINAL (1 región)
    - Luego agrega: ECO GYNECOLOGICO (2 regiones)
    - Signal recalcula: cantidad_regiones = 3
    """
    registro = instance.registro
    
    # Calcular total de regiones sumando todos los estudios
    total_regiones = 0
    for estudio_registro in registro.registroestudio_set.all():
        # cantidad_regiones_default × cantidad (para bilateral, etc.)
        total_regiones += (
            estudio_registro.estudio.conteo_regiones_default * estudio_registro.cantidad
        )
    
    if registro.cantidad_regiones != total_regiones:
        logger.info(
            f"✅ Recalculando regiones automáticas: "
            f"Registro #{registro.id} | "
            f"{registro.cantidad_regiones} → {total_regiones}"
        )
        
        # Actualizar sin disparar post_save nuevamente
        RegistroEstudiosPorMedico.objects.filter(id=registro.id).update(
            cantidad_regiones=total_regiones
        )

    # Clasificación canónica residencia+ECO una vez que existe M2M real.
    tiene_eco = registro.registroestudio_set.filter(estudio__tipo='ECO').exists()
    nuevo_horario = clasificar_horario_residencia_por_proxy(
        rol=registro.medico.rol,
        fecha_registro=registro.fecha_registro,
        tiene_eco=tiene_eco,
    )
    if nuevo_horario and registro.horario in [None, '', 'NA']:
        logger.info(
            f"✅ Recalculando horario automático (post-M2M): "
            f"Registro #{registro.id} | "
            f"{registro.horario} → {nuevo_horario}"
        )
        RegistroEstudiosPorMedico.objects.filter(id=registro.id).update(
            horario=nuevo_horario
        )
        registro.horario = nuevo_horario
    
    # También recalcular monto (ya que regiones afectan el monto)
    nuevo_monto = registro.calcular_monto()
    if registro.monto_calculado != nuevo_monto:
        logger.info(
            f"✅ Recalculando monto automático (desde signal cantidad_regiones): "
            f"Registro #{registro.id} | "
            f"${registro.monto_calculado} → ${nuevo_monto}"
        )
        RegistroEstudiosPorMedico.objects.filter(id=registro.id).update(
            monto_calculado=nuevo_monto
        )
