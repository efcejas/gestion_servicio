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
    r"\bCARDIACO\b", r"\bCARDIAC\b",
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
