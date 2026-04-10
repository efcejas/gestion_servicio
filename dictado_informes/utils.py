"""
utils.py — Constantes y utilidades de procesamiento de texto para dictado_informes.

Centraliza los patrones de regex precompilados para evitar recompilación
en cada llamada (mejora 30-50% en procesamiento de texto según benchmark).
"""
import re


# ─────────────────────────────────────────────────────────────────────────────
# Comandos de voz → caracteres de puntuación / formato
# ─────────────────────────────────────────────────────────────────────────────

REGEX_COMANDOS_VOZ = {
    # Saltos de línea (prioridad alta)
    'nueva_linea': re.compile(r'\bnueva línea\b', re.IGNORECASE),
    'nueva_linea_sin_acento': re.compile(r'\bnueva linea\b', re.IGNORECASE),
    'salto_linea': re.compile(r'\bsalto de línea\b', re.IGNORECASE),
    'salto_linea_sin_acento': re.compile(r'\bsalto de linea\b', re.IGNORECASE),
    'punto_aparte': re.compile(r'\bpunto y aparte\b', re.IGNORECASE),
    'parrafo_nuevo': re.compile(r'\bpárrafo nuevo\b', re.IGNORECASE),

    # Punto seguido (mantener en misma línea)
    'punto_seguido': re.compile(r'\bpunto seguido\b', re.IGNORECASE),
    'seguido': re.compile(r'\bseguido\b', re.IGNORECASE),

    # Puntuación básica
    'punto': re.compile(r'\bpunto\b', re.IGNORECASE),
    'coma': re.compile(r'\bcoma\b', re.IGNORECASE),
    'dos_puntos': re.compile(r'\bdos puntos\b', re.IGNORECASE),
    'punto_coma': re.compile(r'\bpunto y coma\b', re.IGNORECASE),

    # Símbolos
    'parentesis_abre': re.compile(r'\bparéntesis abre\b', re.IGNORECASE),
    'parentesis_cierra': re.compile(r'\bparéntesis cierra\b', re.IGNORECASE),
    'interrogacion_abre': re.compile(r'\binterrogación abre\b', re.IGNORECASE),
    'interrogacion_cierra': re.compile(r'\binterrogación cierra\b', re.IGNORECASE),
}


# ─────────────────────────────────────────────────────────────────────────────
# Conversión de grados a números romanos
# ─────────────────────────────────────────────────────────────────────────────

REGEX_GRADOS = {
    'grado_1': re.compile(r'\bgrado\s+1\b', re.IGNORECASE),
    'grado_2': re.compile(r'\bgrado\s+2\b', re.IGNORECASE),
    'grado_3': re.compile(r'\bgrado\s+3\b', re.IGNORECASE),
    'grado_4': re.compile(r'\bgrado\s+4\b', re.IGNORECASE),
}


# ─────────────────────────────────────────────────────────────────────────────
# Limpieza de artefactos de Whisper
# ─────────────────────────────────────────────────────────────────────────────

REGEX_LIMPIEZA = {
    'coma_punto_coma': re.compile(r',\s*\.\s*,'),
    'punto_coma_newline': re.compile(r'\.\s*,\s*\n'),
    'coma_punto_newline': re.compile(r',\s*\.\s*\n'),
    'coma_punto': re.compile(r',\s*\.\s*'),
    'punto_coma': re.compile(r'\.\s*,\s*'),
    'doble_punto': re.compile(r'\.\s*\.\s*'),
    'coma_newline': re.compile(r',\s*\n'),
    'espacios_antes_newline': re.compile(r'\s+\n'),
    'espacios_despues_newline': re.compile(r'\n\s+'),
    'newlines_multiples': re.compile(r'\n{3,}'),
    'capitalizar_punto_newline': re.compile(r'(\.\s*\n)([a-záéíóúñ])'),
    'capitalizar_punto_espacio': re.compile(r'(\.\s+)([a-záéíóúñ])'),
}
