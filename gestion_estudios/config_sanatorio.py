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
    'MODO': 'Versión completa — Gestión integral del servicio',
    'MODULOS_ACTIVOS': {
        'equipos': True,
        'eventos': True,
        'guardias': True,
        'liquidacion': True,
        'dictado': False,  # ❌ Desactivado por ahora
    },
    'SERVICIOS_DISPONIBLES': [
        ('tomografia', 'Tomografía'),
        ('resonancia', 'Resonancia'),
        ('ecografia', 'Ecografía'),
        ('radiologia', 'Radiología'),
    ],
    # Colores del tema (hexadecimal)
    'COLOR_PRIMARIO': '#164569',    # Azul oscuro médico (original Dupuytren)
    'COLOR_SECUNDARIO': '#4b49c0',  # Morado médico (contrasta con logo)
}


# ============================================================================
# CONFIGURACIÓN: SANATORIO COLEGIALES
# ============================================================================
CONFIG_COLEGIALES = {
    'NOMBRE_SANATORIO': 'Sanatorio Colegiales',
    'ZONA_HORARIA': 'America/Argentina/Buenos_Aires',
    'MODO': 'Modo herramientas internas — Jefatura y seguimiento',
    'MODULOS_ACTIVOS': {
        'equipos': True,       # ✅ Activo - empezamos por aquí
        'eventos': False,      # ❌ Desactivado por ahora
        'guardias': False,     # ❌ Desactivado por ahora
        'liquidacion': False,  # ❌ Desactivado por ahora
        'dictado': False,      # ❌ Desactivado por ahora
    },
    'SERVICIOS_DISPONIBLES': [
        ('tomografia', 'Tomografía'),
        ('rayos', 'Rayos X'),
        ('ecografia', 'Ecografía'),
    ],
    # Colores del tema (hexadecimal)
    'COLOR_PRIMARIO': '#047857',    # Green-700 (verde oscuro - contrasta con logo)
    'COLOR_SECUNDARIO': '#1e40af',  # Blue-800 (azul oscuro - profesional)
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
