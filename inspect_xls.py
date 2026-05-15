import pandas as pd
import xlrd
import os

files = [
    "Prácticas-Ecografías.xls",
    "Prácticas-mamografías.xls",
    "Prácticas-radiología.xls",
    "Prácticas-Resonancias.xls",
    "Prácticas-Tomografías.xls"
]
base_path = r"docs\eges_excels"

def inspect_file(file_name):
    path = os.path.join(base_path, file_name)
    print(f"\n--- Archivo: {file_name} ---")
    try:
        wb = xlrd.open_workbook(path)
        sheet_names = wb.sheet_names()
        print(f"Hojas: {sheet_names}")
        
        for sheet_name in sheet_names:
            df = pd.read_excel(path, sheet_name=sheet_name, engine="xlrd")
            print(f"\nHora: {sheet_name} | Dimensiones: {df.shape}")
            print("Primeras 15 filas:")
            print(df.head(15).to_string())
            
            # Alerta Angio en Tomografías
            if "Tomografías" in file_name:
                for idx, row in df.iterrows():
                    row_str = " ".join(map(str, row.values)).lower()
                    if "angio" in row_str and "contrast" not in row_str:
                        # Nota: Si el usuario dice que Angio siempre implica contraste, 
                        # buscamos casos donde diga Angio pero falte la mención de contraste explícita o sea "sin contraste"
                        if "sin contraste" in row_str or "sin contr" in row_str:
                             print(f"!!! ALERTA: Detectado Angio-TC 'sin contraste' en fila {idx}")
    except Exception as e:
        print(f"Error procesando {file_name}: {e}")

for f in files:
    inspect_file(f)
