import re
import unicodedata


def strip_accents(text):
    normalized = unicodedata.normalize("NFD", str(text))
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalizado(text):
    return re.sub(r"\s+", " ", strip_accents(text).upper()).strip()


PATRONES_ANGIO = [r"\bANGIO"]
PATRONES_CON_CONTRASTE = [
    r"\bCON\s+CONTRASTE\b",
    r"\bCON\s*/\s*CTE\b",
    r"\bC/CONTRASTE\b",
    r"\bC/CONTR\b",
]
PATRONES_SIN_CONTRASTE = [
    r"\bSIN\s+CONTRASTE\b",
    r"\bSIN\s*/\s*CTE\b",
    r"\bS/CONTRASTE\b",
    r"\bS/CONTR\b",
]
PATRONES_DOPPLER = [r"\bDOPPLER\b", r"\bECODOPPLER\b"]

# Doppler cardíaco: palabras que indican estudio cardíaco
PATRONES_CARDIACO = [
    r"\bCARDIAC[OA]\b", r"\bCARDIAC\b",
    r"\bCARDIO\b",
    r"\bECOCARDIO\b",
]

# Transesofágico
PATRONES_TE = [r"\bTRANSESOFAGICO\b", r"\bETE\b", r"\bTRANS.?ESOFAGIC"]

# Eco especiales
PATRONES_STRESS   = [r"\bSTRESS\b", r"\bESTRES\b", r"\bDOBUTAMINA\b", r"\bDOBUTA\b"]
PATRONES_BURBUJA  = [r"\bBURBUJA\b", r"\bCONTRASTE\b"]  # Eco burbuja = eco con contraste


def detecta(nombre, patrones):
    texto = normalizado(nombre)
    return any(re.search(patron, texto) for patron in patrones)


def contextos_disponibles_para_estudio(tipo, nombre, codigo=None):
    """Retorna los contextos de ubicación que la UI debe ofrecer para un estudio.

    La regla clínica no es uniforme para todos los ECOCAR:
    - ETE / transesofágicos: Servicio + Quirófano
    - Eco/Doppler cardíaco transthorácico: Servicio + Lecho
    - Otros Doppler: Servicio + Lecho
    - El resto: solo Servicio
    """
    tipo_normalizado = (tipo or "").upper()
    nombre_normalizado = normalizado(nombre)
    codigo_normalizado = (codigo or "").upper()

    if tipo_normalizado == "ECOCAR":
        if detecta(nombre_normalizado, PATRONES_TE) or "TRANSESOF" in nombre_normalizado or "ETE" in nombre_normalizado:
            return ["SERVICIO", "QUIROFANO"]
        if detecta(nombre_normalizado, PATRONES_CARDIACO) or "ECODOPPLER CARDIACO" in nombre_normalizado or "CARDIACO" in nombre_normalizado:
            return ["SERVICIO", "LECHO"]
        return ["SERVICIO"]

    if tipo_normalizado == "DOP":
        return ["SERVICIO", "LECHO"]

    return ["SERVICIO"]


def es_estudio_cardiologico(tipo, nombre, codigo=None):
    """Determina si un estudio pertenece al circuito de cardiología.

    Reglas actuales de negocio:
    - Todo ECOCAR se considera cardiológico.
    - Estudios con nombre que contenga CARDIAC/CARDIO son cardiológicos.
    - ETE / transesofágicos se consideran cardiológicos aunque no digan CARDIO.
    """
    tipo_normalizado = (tipo or "").upper()
    nombre_normalizado = normalizado(nombre)
    codigo_normalizado = (codigo or "").upper()

    if tipo_normalizado == "ECOCAR":
        return True

    if detecta(nombre_normalizado, PATRONES_CARDIACO):
        return True

    if detecta(nombre_normalizado, PATRONES_TE) or "TRANSESOF" in nombre_normalizado or "ETE" in nombre_normalizado:
        return True

    if "CARDIO" in codigo_normalizado:
        return True

    return False


def inferir_codigo_grupo(tipo, nombre):
    """Retorna el código de grupo tarifario base sugerido para un estudio.

    Para estudios con contexto de ubicación (DOP, ECOCAR), retorna el grupo
    base SERVICIO. El resolver precio_para_os() aplica el sufijo _LECHO o
    _QUIROFANO dinámicamente según RegistroEstudio.contexto.
    """
    tipo_normalizado = (tipo or "").upper()

    if tipo_normalizado == "TOM":
        if detecta(nombre, PATRONES_ANGIO):
            return "TOM_ANGIO"
        if detecta(nombre, PATRONES_CON_CONTRASTE):
            return "TOM_CONTRASTE"
        if detecta(nombre, PATRONES_SIN_CONTRASTE):
            return "TOM_SIN_CONTRASTE"
        return "TOM_SIMPLE"

    if tipo_normalizado == "RES":
        if detecta(nombre, PATRONES_ANGIO):
            return "RES_ANGIO"
        if detecta(nombre, PATRONES_CON_CONTRASTE):
            return "RES_CONTRASTE"
        if detecta(nombre, PATRONES_SIN_CONTRASTE):
            return "RES_SIN_CONTRASTE"
        return "RES_SIMPLE"

    if tipo_normalizado == "ECO":
        if detecta(nombre, PATRONES_DOPPLER):
            return "ECO_DOPPLER"
        return "ECO_ECOGRAFIA"

    if tipo_normalizado == "DOP":
        # Doppler cardíaco vs periférico
        if detecta(nombre, PATRONES_CARDIACO):
            return "DOP_CARDIACO"
        return "DOP_PERIFERICO"

    if tipo_normalizado == "ECOCAR":
        if detecta(nombre, PATRONES_TE):
            return "ECO_TE"
        if detecta(nombre, PATRONES_STRESS):
            return "ECO_STRESS"
        if detecta(nombre, PATRONES_BURBUJA):
            return "ECO_BURBUJA"
        # Ecocardiograma cardíaco genérico → doppler cardíaco
        return "DOP_CARDIACO"

    if tipo_normalizado == "RAD":
        return "RAD_RADIOGRAFIA"

    if tipo_normalizado == "MAM":
        return "MAM_MAMOGRAFIA"

    return None
