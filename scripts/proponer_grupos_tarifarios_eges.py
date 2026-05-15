import argparse
import os
import re
import unicodedata

import pandas as pd


DEFAULT_INPUT_FILE = os.path.join("docs", "eges_excels", "eges_practicas_normalizadas.csv")
DEFAULT_OUTPUT_DIR = os.path.join("docs", "eges_excels")


def strip_accents(text):
    normalized = unicodedata.normalize("NFD", str(text))
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def normalize(text):
    return re.sub(r"\s+", " ", strip_accents(text).upper()).strip()


def infer_modalidad(file_name):
    file_name = normalize(file_name)
    if "TOMOGRAF" in file_name:
        return "TOM"
    if "RESONANC" in file_name:
        return "RES"
    if "ECOGRAF" in file_name:
        return "ECO"
    if "RADIOLOG" in file_name:
        return "RAD"
    if "MAMOGRAF" in file_name:
        return "MAM"
    return "OTRA"


def infer_subtipo(modalidad, base_practica):
    texto = normalize(base_practica)

    if modalidad == "TOM":
        if "ANGIO" in texto:
            return "ANGIO"
        if "CON CONTRASTE" in texto or "CTE" in texto or "CON C" in texto:
            return "CONTRASTE"
        if "SIN CONTRASTE" in texto or "S/C" in texto:
            return "SIN_CONTRASTE"
        return "SIMPLE"

    if modalidad == "RES":
        if "ANGIO" in texto:
            return "ANGIO"
        if "DIFUS" in texto:
            return "DIFUSION"
        if "CON CONTRASTE" in texto or "CTE" in texto or "CON C" in texto:
            return "CONTRASTE"
        if "SIN CONTRASTE" in texto or "S/C" in texto:
            return "SIN_CONTRASTE"
        return "SIMPLE"

    if modalidad == "ECO":
        if "ECOCARDIO" in texto or "CARDIO" in texto:
            return "ECOCARDIO"
        if "DOPPLER" in texto or "ECODOPPLER" in texto or "DOPPLER" in texto:
            return "DOPPLER"
        return "ECOGRAFIA"

    if modalidad == "RAD":
        return "RADIOGRAFIA"

    if modalidad == "MAM":
        return "MAMOGRAFIA"

    return "OTRO"


def build_group_code(modalidad, subtipo):
    return f"{modalidad}_{subtipo}"


def build_group_name(modalidad, subtipo):
    names = {
        "TOM_SIMPLE": "Tomografía simple",
        "TOM_CONTRASTE": "Tomografía con contraste",
        "TOM_SIN_CONTRASTE": "Tomografía sin contraste",
        "TOM_ANGIO": "Tomografía Angio",
        "RES_SIMPLE": "Resonancia simple",
        "RES_CONTRASTE": "Resonancia con contraste",
        "RES_SIN_CONTRASTE": "Resonancia sin contraste",
        "RES_ANGIO": "Resonancia Angio",
        "RES_DIFUSION": "Resonancia difusión",
        "ECO_ECOGRAFIA": "Ecografía",
        "ECO_DOPPLER": "Doppler",
        "ECO_ECOCARDIO": "Ecocardiograma",
        "RAD_RADIOGRAFIA": "Radiografía",
        "MAM_MAMOGRAFIA": "Mamografía",
    }
    return names.get(f"{modalidad}_{subtipo}", f"{modalidad} {subtipo}")


def main():
    parser = argparse.ArgumentParser(description="Propone grupos tarifarios desde el normalizado EGES")
    parser.add_argument("--input-file", default=DEFAULT_INPUT_FILE, help="CSV normalizado de EGES")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Carpeta de salida")
    parser.add_argument("--detalle-name", default="eges_mapa_practicas_a_grupos.csv", help="CSV detalle fila a fila")
    parser.add_argument("--resumen-name", default="eges_grupos_propuestos.csv", help="CSV resumen por grupo")
    args = parser.parse_args()

    input_file = os.path.abspath(args.input_file)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_csv(input_file)
    df = df[~df["es_material"]].copy()

    df["modalidad"] = df["archivo"].apply(infer_modalidad)
    df["subtipo_propuesto"] = df.apply(lambda row: infer_subtipo(row["modalidad"], row["base_practica"]), axis=1)
    df["grupo_codigo_propuesto"] = df.apply(lambda row: build_group_code(row["modalidad"], row["subtipo_propuesto"]), axis=1)
    df["grupo_nombre_propuesto"] = df.apply(lambda row: build_group_name(row["modalidad"], row["subtipo_propuesto"]), axis=1)

    detalle_cols = [
        "archivo",
        "hoja",
        "fila_excel",
        "prestacion",
        "nombre_original",
        "base_practica",
        "modalidad",
        "subtipo_propuesto",
        "grupo_codigo_propuesto",
        "grupo_nombre_propuesto",
        "angio",
        "con_contraste",
        "sin_contraste",
        "difusion",
        "observacion",
    ]
    detalle = df[detalle_cols].sort_values(["modalidad", "grupo_codigo_propuesto", "archivo", "fila_excel"])

    resumen = (
        detalle.groupby(["modalidad", "subtipo_propuesto", "grupo_codigo_propuesto", "grupo_nombre_propuesto"], as_index=False)
        .agg(
            cantidad_practicas=("prestacion", "count"),
            ejemplos=("base_practica", lambda values: " | ".join(list(pd.unique(values))[:5])),
        )
        .sort_values(["modalidad", "cantidad_practicas", "grupo_codigo_propuesto"], ascending=[True, False, True])
    )

    detalle_path = os.path.join(output_dir, args.detalle_name)
    resumen_path = os.path.join(output_dir, args.resumen_name)

    detalle.to_csv(detalle_path, index=False, encoding="utf-8-sig")
    resumen.to_csv(resumen_path, index=False, encoding="utf-8-sig")

    print(f"Detalle generado: {detalle_path}")
    print(f"Resumen generado: {resumen_path}")
    print(f"Prácticas analizadas: {len(detalle)}")
    print(f"Grupos propuestos: {len(resumen)}")


if __name__ == "__main__":
    main()