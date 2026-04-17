# 🧠 Sistema de Aprendizaje Automático - Dictado Médico

## 📋 Resumen

El sistema aprende automáticamente de tus correcciones manuales y las aplica en futuras transcripciones.

## 🔄 Flujo Completo

### 1. Dictar con Whisper
- Hablas al micrófono (mínimo 0.3 segundos)
- **Whisper transcribe** con alta precisión médica
- Ejemplo transcrito: `"gonartrosis tricompartimental grado 3"`

### 2. Procesamiento Automático
- **Diccionario médico** se aplica primero
- **Comandos de voz** se procesan (nueva línea, punto seguido, etc.)
- **Conversiones automáticas**: `"grado 3"` → `"grado III"`
- **Saltos inteligentes**: Detecta estructuras anatómicas y separa conceptos

### 3. Mejora con IA (Groq - Modo FIEL)
- **Lee ejemplos de aprendizaje** de la base de datos
- Aplica correcciones aprendidas de ti
- Corrige solo ortografía, respeta formato
- Resultado: `"Gonartrosis tricompartimental grado III"`

### 4. Tu Edición Manual (Opcional)
Si editas el texto mejorado y copias el resultado, el sistema te pregunta si quieres guardar esa corrección para aprendizaje.

Al confirmar:
- Sistema detecta cambios con `difflib` (palabra por palabra)
- Guarda en modelo `CorreccionAprendizaje`
- Clasifica la corrección por calidad para decidir si entra al prompt automático
- Ejemplo guardado:
  ```json
  {
    "tipo": "reemplazo",
    "de": "tricompartimental",
    "a": "tricompartamental"
  }
  ```

### 5. Próxima Transcripción
La IA **automáticamente** recibe en su prompt solo ejemplos aptos (no atípicos):
```
APRENDE DE ESTAS CORRECCIONES ANTERIORES DEL USUARIO:
❌ tricompartimental → ✅ tricompartamental
❌ meniscos normales → ✅ meniscos de configuración habitual
```

## 🛡️ Filtro de Seguridad del Aprendizaje

Para evitar contaminación por ediciones accidentales o groseras, cada corrección se evalúa antes de usarse en prompts automáticos:

- Se guarda todo en historial (trazabilidad completa)
- Solo se usa en prompt si `es_apta_para_prompt(...)` devuelve True
- Se descarta del prompt si detecta:
   - divergencia excesiva texto_ia vs texto_final
   - texto repetitivo/ruidoso (ej: "asdf asdf..." o "random random...")
   - patrón de cambios de bajo valor clínico

Además, para estilo completo (`es_apta_para_estilo(...)`) se exige estructura mínima (COMENTARIO + CONCLUSIÓN) para no aprender formato pobre.

## 🎯 Ventajas

✅ **Aprendizaje automático**: No necesitas configurar nada manualmente
✅ **Personalizado por usuario**: Cada médico tiene sus propias correcciones
✅ **Mejora continua**: Más correcciones = más precisión
✅ **Transparente**: Puedes ver los ejemplos activos en el Admin de Django

## 📊 Indicadores en la UI

Cuando tienes ejemplos de aprendizaje activos, verás:

```
🧠 Aprendizaje Activo: 15 ejemplos activos mejorando tus transcripciones
```

Nota: "activos" significa ejemplos aptos para prompt, no el total bruto guardado en historial.

## 🔧 Gestión en Admin Django

### Ver Correcciones
1. Admin → **Correcciones de Aprendizaje**
2. Filtra por usuario, fecha, tipo de estudio
3. Ve las diferencias visuales (rojo/verde)
4. Revisa textos atípicos: pueden estar guardados pero no entrar en aprendizaje automático

### Acciones Disponibles
- **✅ Marcar como aplicada**: Marca correcciones ya usadas
- **🔄 Recalcular diferencias**: Regenera análisis con difflib
- **📥 Exportar para entrenamiento**: Descarga JSON para fine-tuning
- **👁️ Ver ejemplos usados en prompt IA**: Muestra qué se está enviando a la IA

## 🔍 Cómo Verificar que Funciona

### Test Manual:
1. **Dicta**: "meniscos normales"
2. **Resultado IA**: "Meniscos normales"
3. **Editas**: "Meniscos de configuración habitual"
4. **Copias y confirmas aprendizaje**: ✅ Corrección guardada
5. **Dicta de nuevo**: "meniscos normales"
6. **Resultado IA**: "Meniscos de configuración habitual" ← **Aplicó tu corrección!**

### Test de descarte (anti-ruido):
1. Crear una edición claramente inválida/ruidosa
2. Verificar que se guarda en admin
3. Confirmar que no aparece en ejemplos activos para prompt

### Verificación en Admin:
1. Admin → Correcciones de Aprendizaje
2. Selecciona alguna corrección
3. Acción: **"Ver ejemplos usados en prompt IA"**
4. Verás el texto exacto que la IA recibe

## 📈 Límites y Configuración

- **Ejemplos máximos por prompt**: 10 (configurable en `obtener_ejemplos_aprendizaje`)
- **Filtro de calidad**: automático (`es_apta_para_prompt` y `es_apta_para_estilo`)
- **Ordenamiento**: priorizado por score semántico
- **Scope**: por usuario (personalizado)

## 🐛 Debug

Si la IA no aplica tus correcciones:

1. **Verifica que se guardaron**:
   ```python
   CorreccionAprendizaje.objects.filter(usuario=tu_usuario).count()
   ```

2. **Ve los ejemplos generados**:
   ```python
   from dictado_informes.models import CorreccionAprendizaje
   ejemplos = CorreccionAprendizaje.obtener_ejemplos_aprendizaje(usuario=tu_usuario)
   print(ejemplos)
   ```

3. **Revisa logs del servidor**:
   ```
   [INFO] 📝 Modo FIEL - solo corregir ortografía
   [INFO] Ejemplos de aprendizaje: 5 activos
   ```

## 🚀 Próximas Mejoras

- [ ] Fine-tuning del modelo con tus correcciones
- [ ] Ranking de correcciones por votos de utilidad
- [ ] Sugerencias proactivas basadas en patrones
- [ ] Exportación automática para entrenamiento periódico
