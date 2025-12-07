"""
Configuración específica por sanatorio.
Cambiar SANATORIO_ACTIVO para alternar entre Dupuytren y Colegiales.
"""

# ============================================================================
# SELECCIONAR SANATORIO ACTIVO
# ============================================================================
SANATORIO_ACTIVO = 'colegiales'  # Opciones: 'dupuytren' o 'colegiales'


# ============================================================================
# CONFIGURACIÓN: SANATORIO DUPUYTREN
# ============================================================================
CONFIG_DUPUYTREN = {
    'NOMBRE_SANATORIO': 'Sanatorio Dupuytren',
    'ZONA_HORARIA': 'America/Argentina/Buenos_Aires',
    'SERVICIOS_DISPONIBLES': [
        ('tomografia', 'Tomografía'),
        ('resonancia', 'Resonancia'),
        ('ecografia', 'Ecografía'),
        ('radiologia', 'Radiología'),
    ],
}


# ============================================================================
# CONFIGURACIÓN: SANATORIO COLEGIALES
# ============================================================================
CONFIG_COLEGIALES = {
    'NOMBRE_SANATORIO': 'Sanatorio Colegiales',
    'ZONA_HORARIA': 'America/Argentina/Buenos_Aires',
    'SERVICIOS_DISPONIBLES': [
        ('tomografia', 'Tomografía'),
        ('rayos', 'Rayos X'),
        ('ecografia', 'Ecografía'),
    ],
}


# ============================================================================
# OBTENER CONFIGURACIÓN ACTIVA
# ============================================================================
def get_config():
    """Retorna la configuración del sanatorio activo"""
    if SANATORIO_ACTIVO == 'dupuytren':
        return CONFIG_DUPUYTREN
    elif SANATORIO_ACTIVO == 'colegiales':
        return CONFIG_COLEGIALES
    else:
        raise ValueError(
            f"SANATORIO_ACTIVO '{SANATORIO_ACTIVO}' no es válido. "
            f"Opciones: 'dupuytren' o 'colegiales'"
        )


# Variable global para usar en settings.py
CONFIG = get_config()
