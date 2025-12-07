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
Si editas el texto mejorado y haces clic en **"Guardar Aprendizaje"**:
- Sistema detecta cambios con `difflib` (palabra por palabra)
- Guarda en modelo `CorreccionAprendizaje`
- Ejemplo guardado:
  ```json
  {
    "tipo": "reemplazo",
    "de": "tricompartimental",
    "a": "tricompartamental"
  }
  ```

### 5. Próxima Transcripción
La IA **automáticamente** recibe estos ejemplos en su prompt:
```
APRENDE DE ESTAS CORRECCIONES ANTERIORES DEL USUARIO:
❌ tricompartimental → ✅ tricompartamental
❌ meniscos normales → ✅ meniscos de configuración habitual
```

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

## 🔧 Gestión en Admin Django

### Ver Correcciones
1. Admin → **Correcciones de Aprendizaje**
2. Filtra por usuario, fecha, tipo de estudio
3. Ve las diferencias visuales (rojo/verde)

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
4. **Guardas aprendizaje**: ✅ Corrección guardada! 3 cambios detectados
5. **Dicta de nuevo**: "meniscos normales"
6. **Resultado IA**: "Meniscos de configuración habitual" ← **Aplicó tu corrección!**

### Verificación en Admin:
1. Admin → Correcciones de Aprendizaje
2. Selecciona alguna corrección
3. Acción: **"Ver ejemplos usados en prompt IA"**
4. Verás el texto exacto que la IA recibe

## 📈 Límites y Configuración

- **Ejemplos máximos por prompt**: 10 (configurable en `obtener_ejemplos_aprendizaje`)
- **Ejemplos únicos mostrados**: 20 líneas máximo
- **Ordenamiento**: Más recientes primero
- **Scope**: Por usuario (personalizado)

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
