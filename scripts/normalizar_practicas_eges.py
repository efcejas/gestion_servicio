import argparse
import os
import re
import unicodedata

import pandas as pd


DEFAULT_INPUT_DIR = os.path.join("docs", "eges_excels")
DEFAULT_OUTPUT_DIR = os.path.join("docs", "eges_excels")

MATERIAL_PATTERNS = [
    r"\bAGUJA\b",
    r"^BIOPSIA\b",
    r"\bPUNCION\b",
    r"\bPUNCIÓN\b",
    r"\bCATETER\b",
    r"\bCATÉTER\b",
    r"^CONTRASTE$",
    r"\bINYECTOR\b",
    r"\bBOMBA\b",
    r"\bKIT\b",
    r"\bSUERO\b",
    r"\bFILTRO\b",
    r"\bLLAVE\b",
    r"\bJERINGA\b",
    r"\bMATERIAL\b",
    r"\bINSUMO\b",
    r"\bACCESORIO\b",
    r"\bABBOCATH\b",
    r"\bANEST\b",
]

MODIFIER_PATTERNS = {
    "angio": [r"\bANGIO"],
    "con_contraste": [r"\bCON\s+CONTRASTE\b", r"\bCON\s*/\s*CTE\b", r"\bCON\s+C\b", r"\bC/C\b"],
    "sin_contraste": [r"\bSIN\s+CONTRASTE\b", r"\bSIN\s*/\s*CTE\b", r"\bS/C\b"],
    "difusion": [r"\bDIFUSION\b", r"\bDIFUSIÓN\b"],
}

REMOVE_PATTERNS = [
    r"\bANGIO(GRAFIA|GRAFÍA)?\b",
    r"\bCON\s+CONTRASTE\b",
    r"\bSIN\s+CONTRASTE\b",
    r"\bCON\s*/\s*CTE\b",
    r"\bSIN\s*/\s*CTE\b",
    r"\bCON\s+C\b",
    r"\bC/C\b",
    r"\bS/C\b",
    r"\bDIFUSION\b",
    r"\bDIFUSIÓN\b",
]


def strip_accents(text):
    normalized = unicodedata.normalize("NFD", str(text))
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def normalize_for_match(text):
    return re.sub(r"\s+", " ", strip_accents(text).upper()).strip()


def detect_patterns(text, patterns):
    return any(re.search(pattern, text) for pattern in patterns)


def clean_base_name(text):
    base = strip_accents(text).upper()
    for pattern in REMOVE_PATTERNS:
        base = re.sub(pattern, " ", base)
    base = re.sub(r"[^A-Z0-9/()+\- ]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    return base


def build_row_record(file_name, sheet_name, row_number, row_values):
    values = ["" if pd.isna(value) else str(value) for value in row_values]
    raw_text = " | ".join(values).strip()
    normalized_text = normalize_for_match(raw_text)

    prestacion = values[0].strip() if values else ""
    nombre = values[2].strip() if len(values) > 2 else ""
    if not nombre and len(values) > 1:
        nombre = values[1].strip()

    is_material = detect_patterns(normalized_text, MATERIAL_PATTERNS)
    modifiers = {key: detect_patterns(normalized_text, patterns) for key, patterns in MODIFIER_PATTERNS.items()}
    has_any_modifier = any(modifiers.values())
    base_name = clean_base_name(nombre or raw_text)

    observations = []
    if is_material:
        observations.append("posible_material_o_insumo")
    if modifiers.get("angio") and not (modifiers.get("con_contraste") or modifiers.get("sin_contraste")):
        observations.append("angio_sin_contraste_explicito")
    if modifiers.get("angio") and modifiers.get("sin_contraste"):
        observations.append("angio_con_sin_contraste_incompatible")
    if base_name in {"", prestacion.upper(), normalize_for_match(nombre)}:
        observations.append("base_no_separada")

    return {
        "archivo": file_name,
        "hoja": sheet_name,
        "fila_excel": row_number,
        "prestacion": prestacion,
        "nombre_original": nombre,
        "texto_completo": raw_text,
        "base_practica": base_name,
        "angio": modifiers["angio"],
        "con_contraste": modifiers["con_contraste"],
        "sin_contraste": modifiers["sin_contraste"],
        "difusion": modifiers["difusion"],
        "es_material": is_material,
        "tiene_modificador": has_any_modifier,
        "observacion": ";".join(observations),
    }


def process_file(file_path):
    file_name = os.path.basename(file_path)
    workbook = pd.ExcelFile(file_path, engine="xlrd")
    records = []

    for sheet_name in workbook.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine="xlrd")
        for index, row in df.iterrows():
            records.append(build_row_record(file_name, sheet_name, index + 2, row.values))

    return records


def main():
    parser = argparse.ArgumentParser(description="Normaliza prácticas EGES desde libros .xls")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR, help="Carpeta con los .xls de EGES")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Carpeta donde guardar CSV de salida")
    parser.add_argument("--output-name", default="eges_practicas_normalizadas.csv", help="Nombre del CSV principal")
    parser.add_argument("--dudosas-name", default="eges_practicas_dudosas.csv", help="Nombre del CSV con casos dudosos")
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    files = sorted(
        file_name
        for file_name in os.listdir(input_dir)
        if file_name.lower().endswith(".xls")
    )

    if not files:
        raise SystemExit(f"No se encontraron archivos .xls en {input_dir}")

    all_records = []
    for file_name in files:
        file_path = os.path.join(input_dir, file_name)
        all_records.extend(process_file(file_path))

    df = pd.DataFrame(all_records)
    df = df.sort_values(["archivo", "hoja", "fila_excel"]).reset_index(drop=True)

    normalized_path = os.path.join(output_dir, args.output_name)
    doubtful_path = os.path.join(output_dir, args.dudosas_name)

    df.to_csv(normalized_path, index=False, encoding="utf-8-sig")
    doubtful_df = df[(df["es_material"]) | (df["observacion"] != "")]
    doubtful_df.to_csv(doubtful_path, index=False, encoding="utf-8-sig")

    total = len(df)
    dudosas = len(doubtful_df)
    angio_sospechosas = len(df[df["observacion"].str.contains("angio", case=False, na=False)])

    print(f"Archivos procesados: {len(files)}")
    print(f"Filas totales: {total}")
    print(f"Casos dudosos: {dudosas}")
    print(f"Casos angio con alerta: {angio_sospechosas}")
    print(f"CSV principal: {normalized_path}")
    print(f"CSV dudosas: {doubtful_path}")


if __name__ == "__main__":
    main()