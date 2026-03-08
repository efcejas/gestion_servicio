#!/usr/bin/env python
"""
🚀 BENCHMARK FASE 3: OPTIMIZACIONES DE REGEX

Script para medir la mejora de performance de regex precompilados
en el procesamiento de comandos de voz.

Compara:
- Versión anterior: compilar regex cada vez (lento)
- Versión nueva: regex precompilados (rápido)

Uso:
    python scripts/benchmark_fase3.py
"""
import time
import re
import statistics
from typing import List, Tuple


# ========================================
# VERSIÓN ANTERIOR (LENTA): Compilar cada vez
# ========================================
def procesar_comandos_voz_anterior(texto: str) -> str:
    """Versión anterior sin optimización"""
    if not texto:
        return texto
    
    # PASO 1: Reemplazar comandos de voz literales
    comandos = {
        # Saltos de línea (prioridad alta)
        r'\bnueva línea\b': '\n',
        r'\bnueva linea\b': '\n',
        r'\bsalto de línea\b': '\n',
        r'\bsalto de linea\b': '\n',
        r'\bpunto y aparte\b': '.\n\n',
        r'\bpárrafo nuevo\b': '\n\n',
        
        # Punto seguido (mantener en misma línea)
        r'\bpunto seguido\b': '. ',
        r'\bseguido\b': '. ',
        
        # Puntuación básica
        r'\bpunto\b': '.',
        r'\bcoma\b': ',',
        r'\bdos puntos\b': ':',
        r'\bpunto y coma\b': ';',
        
        # Símbolos
        r'\bparéntesis abre\b': '(',
        r'\bparéntesis cierra\b': ')',
        r'\binterrogación abre\b': '¿',
        r'\binterrogación cierra\b': '?',
    }
    
    texto_procesado = texto
    for patron, reemplazo in comandos.items():
        texto_procesado = re.sub(patron, reemplazo, texto_procesado, flags=re.IGNORECASE)
    
    # PASO 2: CONVERSIÓN AUTOMÁTICA DE GRADOS A NÚMEROS ROMANOS
    conversiones_grado = {
        r'\bgrado\s+1\b': 'grado I',
        r'\bgrado\s+2\b': 'grado II',
        r'\bgrado\s+3\b': 'grado III',
        r'\bgrado\s+4\b': 'grado IV',
    }
    
    for patron, reemplazo in conversiones_grado.items():
        texto_procesado = re.sub(patron, reemplazo, texto_procesado, flags=re.IGNORECASE)
    
    # PASO 3: LIMPIAR ARTEFACTOS DE WHISPER
    texto_procesado = re.sub(r',\s*\.\s*,', '.\n', texto_procesado)
    texto_procesado = re.sub(r'\.\s*,\s*\n', '.\n', texto_procesado)
    texto_procesado = re.sub(r',\s*\.\s*\n', '.\n', texto_procesado)
    texto_procesado = re.sub(r',\s*\.\s*', '.\n', texto_procesado)
    texto_procesado = re.sub(r'\.\s*,\s*', '.\n', texto_procesado)
    texto_procesado = re.sub(r'\.\s*\.\s*', '.\n', texto_procesado)
    texto_procesado = re.sub(r',\s*\n', '\n', texto_procesado)
    texto_procesado = re.sub(r'\s+\n', '\n', texto_procesado)
    texto_procesado = re.sub(r'\n\s+', '\n', texto_procesado)
    texto_procesado = re.sub(r'\n{3,}', '\n\n', texto_procesado)
    
    return texto_procesado.strip()


# ========================================
# VERSIÓN NUEVA (RÁPIDA): Regex precompilados
# ========================================

# Pre-compilar patrones de comandos de voz
REGEX_COMANDOS_VOZ = {
    'nueva_linea': re.compile(r'\bnueva línea\b', re.IGNORECASE),
    'nueva_linea_sin_acento': re.compile(r'\bnueva linea\b', re.IGNORECASE),
    'salto_linea': re.compile(r'\bsalto de línea\b', re.IGNORECASE),
    'salto_linea_sin_acento': re.compile(r'\bsalto de linea\b', re.IGNORECASE),
    'punto_aparte': re.compile(r'\bpunto y aparte\b', re.IGNORECASE),
    'parrafo_nuevo': re.compile(r'\bpárrafo nuevo\b', re.IGNORECASE),
    'punto_seguido': re.compile(r'\bpunto seguido\b', re.IGNORECASE),
    'seguido': re.compile(r'\bseguido\b', re.IGNORECASE),
    'punto': re.compile(r'\bpunto\b', re.IGNORECASE),
    'coma': re.compile(r'\bcoma\b', re.IGNORECASE),
    'dos_puntos': re.compile(r'\bdos puntos\b', re.IGNORECASE),
    'punto_coma': re.compile(r'\bpunto y coma\b', re.IGNORECASE),
    'parentesis_abre': re.compile(r'\bparéntesis abre\b', re.IGNORECASE),
    'parentesis_cierra': re.compile(r'\bparéntesis cierra\b', re.IGNORECASE),
    'interrogacion_abre': re.compile(r'\binterrogación abre\b', re.IGNORECASE),
    'interrogacion_cierra': re.compile(r'\binterrogación cierra\b', re.IGNORECASE),
}

REGEX_GRADOS = {
    'grado_1': re.compile(r'\bgrado\s+1\b', re.IGNORECASE),
    'grado_2': re.compile(r'\bgrado\s+2\b', re.IGNORECASE),
    'grado_3': re.compile(r'\bgrado\s+3\b', re.IGNORECASE),
    'grado_4': re.compile(r'\bgrado\s+4\b', re.IGNORECASE),
}

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
}


def procesar_comandos_voz_nuevo(texto: str) -> str:
    """Versión nueva con regex precompilados"""
    if not texto:
        return texto
    
    texto_procesado = texto
    
    # PASO 1: Reemplazar comandos de voz literales usando regex precompilados
    comandos_reemplazos = [
        (REGEX_COMANDOS_VOZ['nueva_linea'], '\n'),
        (REGEX_COMANDOS_VOZ['nueva_linea_sin_acento'], '\n'),
        (REGEX_COMANDOS_VOZ['salto_linea'], '\n'),
        (REGEX_COMANDOS_VOZ['salto_linea_sin_acento'], '\n'),
        (REGEX_COMANDOS_VOZ['punto_aparte'], '.\n\n'),
        (REGEX_COMANDOS_VOZ['parrafo_nuevo'], '\n\n'),
        (REGEX_COMANDOS_VOZ['punto_seguido'], '. '),
        (REGEX_COMANDOS_VOZ['seguido'], '. '),
        (REGEX_COMANDOS_VOZ['punto'], '.'),
        (REGEX_COMANDOS_VOZ['coma'], ','),
        (REGEX_COMANDOS_VOZ['dos_puntos'], ':'),
        (REGEX_COMANDOS_VOZ['punto_coma'], ';'),
        (REGEX_COMANDOS_VOZ['parentesis_abre'], '('),
        (REGEX_COMANDOS_VOZ['parentesis_cierra'], ')'),
        (REGEX_COMANDOS_VOZ['interrogacion_abre'], '¿'),
        (REGEX_COMANDOS_VOZ['interrogacion_cierra'], '?'),
    ]
    
    for patron_compilado, reemplazo in comandos_reemplazos:
        texto_procesado = patron_compilado.sub(reemplazo, texto_procesado)
    
    # PASO 2: CONVERSIÓN AUTOMÁTICA DE GRADOS A NÚMEROS ROMANOS
    grados_reemplazos = [
        (REGEX_GRADOS['grado_1'], 'grado I'),
        (REGEX_GRADOS['grado_2'], 'grado II'),
        (REGEX_GRADOS['grado_3'], 'grado III'),
        (REGEX_GRADOS['grado_4'], 'grado IV'),
    ]
    
    for patron_compilado, reemplazo in grados_reemplazos:
        texto_procesado = patron_compilado.sub(reemplazo, texto_procesado)
    
    # PASO 3: LIMPIAR ARTEFACTOS DE WHISPER
    limpiezas = [
        (REGEX_LIMPIEZA['coma_punto_coma'], '.\n'),
        (REGEX_LIMPIEZA['punto_coma_newline'], '.\n'),
        (REGEX_LIMPIEZA['coma_punto_newline'], '.\n'),
        (REGEX_LIMPIEZA['coma_punto'], '.\n'),
        (REGEX_LIMPIEZA['punto_coma'], '.\n'),
        (REGEX_LIMPIEZA['doble_punto'], '.\n'),
        (REGEX_LIMPIEZA['coma_newline'], '\n'),
        (REGEX_LIMPIEZA['espacios_antes_newline'], '\n'),
        (REGEX_LIMPIEZA['espacios_despues_newline'], '\n'),
        (REGEX_LIMPIEZA['newlines_multiples'], '\n\n'),
    ]
    
    for patron_compilado, reemplazo in limpiezas:
        texto_procesado = patron_compilado.sub(reemplazo, texto_procesado)
    
    return texto_procesado.strip()


# ========================================
# CASOS DE PRUEBA
# ========================================

TEXTOS_PRUEBA = [
    # Caso 1: Texto médico corto con comandos de voz
    "ligamento cruzado anterior íntegro punto menisco externo sin lesiones coma menisco interno conservado punto seguido articulación femorotibial sin alteraciones nueva línea cartílago articular preservado",
    
    # Caso 2: Texto con múltiples comandos y grados
    "se observa lesión grado 1 en menisco punto nueva linea incremento de señal grado 2 punto seguido presencia de cambios degenerativos grado 3 coma sin evidencia de rotura completa",
    
    # Caso 3: Texto largo realista
    "resonancia magnética de rodilla derecha punto técnica punto se realizaron secuencias sagitales t1 y t2 coma coronales t2 y axiales punto seguido hallazgos punto ligamento cruzado anterior íntegro coma de morfología y señal conservadas punto nueva línea ligamento cruzado posterior sin alteraciones punto menisco externo punto se identifica señal anormal en el cuerno posterior compatible con lesión horizontal grado 2 punto nueva línea menisco interno punto sin evidencia de lesiones significativas coma si bien se observa señal lineal en cuerno posterior que podría corresponder a cambios degenerativos incipientes grado 1 punto seguido cartílago articular punto se evidencia adelgazamiento focal del cartílago en cóndilo femoral externo punto nueva línea derrame articular escaso punto conclusión punto lesión meniscal horizontal grado 2 en cuerno posterior de menisco externo punto cambios degenerativos incipientes en menisco interno punto cartílago femoral externo con áreas de adelgazamiento",
    
    # Caso 4: Texto con artefactos de Whisper
    "hallazgo uno., hallazgo dos. , hallazgo tres,. hallazgo cuatro",
    
    # Caso 5: Texto con muchos comandos repetidos
    "observación punto observación dos punto observación tres punto observación cuatro punto observación cinco punto nueva línea hallazgo uno nueva línea hallazgo dos nueva línea hallazgo tres",
]


def ejecutar_benchmark(funcion, nombre: str, textos: List[str], iteraciones: int = 100) -> Tuple[float, float, float]:
    """
    Ejecuta benchmark de una función
    
    Returns:
        Tuple[float, float, float]: (tiempo_promedio, tiempo_min, tiempo_max)
    """
    tiempos = []
    
    for texto in textos:
        for _ in range(iteraciones):
            inicio = time.perf_counter()
            _ = funcion(texto)
            fin = time.perf_counter()
            tiempos.append((fin - inicio) * 1000)  # Convertir a ms
    
    tiempo_promedio = statistics.mean(tiempos)
    tiempo_min = min(tiempos)
    tiempo_max = max(tiempos)
    tiempo_mediana = statistics.median(tiempos)
    desviacion = statistics.stdev(tiempos) if len(tiempos) > 1 else 0
    
    print(f"\n{'='*60}")
    print(f"📊 BENCHMARK: {nombre}")
    print(f"{'='*60}")
    print(f"  Iteraciones totales: {len(tiempos)}")
    print(f"  Tiempo promedio:     {tiempo_promedio:.4f} ms")
    print(f"  Tiempo mediana:      {tiempo_mediana:.4f} ms")
    print(f"  Tiempo mínimo:       {tiempo_min:.4f} ms")
    print(f"  Tiempo máximo:       {tiempo_max:.4f} ms")
    print(f"  Desviación estándar: {desviacion:.4f} ms")
    
    return tiempo_promedio, tiempo_min, tiempo_max


def main():
    print("\n" + "="*60)
    print("🚀 BENCHMARK FASE 3: REGEX PRECOMPILADOS")
    print("="*60)
    print(f"\n📝 Casos de prueba: {len(TEXTOS_PRUEBA)}")
    print(f"🔁 Iteraciones por caso: 100")
    print(f"📏 Total de ejecuciones por versión: {len(TEXTOS_PRUEBA) * 100}")
    
    # Ejecutar benchmarks
    tiempo_anterior, _, _ = ejecutar_benchmark(
        procesar_comandos_voz_anterior,
        "VERSIÓN ANTERIOR (sin optimización)",
        TEXTOS_PRUEBA,
        iteraciones=100
    )
    
    tiempo_nuevo, _, _ = ejecutar_benchmark(
        procesar_comandos_voz_nuevo,
        "VERSIÓN NUEVA (regex precompilados)",
        TEXTOS_PRUEBA,
        iteraciones=100
    )
    
    # Calcular mejora
    mejora_absoluta = tiempo_anterior - tiempo_nuevo
    mejora_porcentual = ((tiempo_anterior - tiempo_nuevo) / tiempo_anterior) * 100
    
    print(f"\n{'='*60}")
    print(f"📈 RESULTADO FINAL")
    print(f"{'='*60}")
    print(f"  Versión anterior: {tiempo_anterior:.4f} ms")
    print(f"  Versión nueva:    {tiempo_nuevo:.4f} ms")
    print(f"  Mejora absoluta:  {mejora_absoluta:.4f} ms más rápido")
    print(f"  Mejora relativa:  {mejora_porcentual:.1f}% más rápido")
    print(f"  Factor:           {tiempo_anterior/tiempo_nuevo:.2f}x")
    print(f"{'='*60}")
    
    # Verificar que los resultados sean idénticos
    print(f"\n🔍 VERIFICACIÓN DE RESULTADOS")
    print(f"{'='*60}")
    for i, texto in enumerate(TEXTOS_PRUEBA[:3], 1):
        resultado_anterior = procesar_comandos_voz_anterior(texto)
        resultado_nuevo = procesar_comandos_voz_nuevo(texto)
        iguales = resultado_anterior == resultado_nuevo
        simbolo = "✅" if iguales else "❌"
        print(f"  Caso {i}: {simbolo} {'Idénticos' if iguales else 'DIFERENCIAS'}")
    
    print(f"\n✅ Benchmark completado exitosamente\n")
    
    return mejora_porcentual


if __name__ == "__main__":
    mejora = main()
    
    # Verificar que cumple objetivo de 30-50%
    if mejora >= 30:
        print(f"🎯 OBJETIVO CUMPLIDO: Mejora de {mejora:.1f}% (objetivo: 30-50%)")
    else:
        print(f"⚠️ Mejora de {mejora:.1f}% menor al objetivo de 30%")
