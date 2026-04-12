# 🏗️ ARQUITECTURA DEL SISTEMA - DICTADO INTELIGENTE CON IA

## 📐 DIAGRAMA DE FLUJO PRINCIPAL

```
┌─────────────────────────────────────────────────────────────────┐
│                    USUARIO (Médico Radiólogo)                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│           FRONTEND - dictado_rapido_whisper.html                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Grabar     │  │   Preview    │  │  Historial   │          │
│  │   Audio      │  │ Tiempo Real  │  │ LocalStorage │          │
│  │ (MediaRec.)  │  │ (WebSpeech)  │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND - Django Views                       │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  API 1: transcribir_audio_whisper                      │    │
│  │  • Recibe: audio base64                                │    │
│  │  • Procesa comandos de voz                             │    │
│  │  • Devuelve: texto transcrito                          │    │
│  └───────────────────┬────────────────────────────────────┘    │
│                      │                                          │
│                      ▼                                          │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  API 2: mejorar_texto_ia                               │    │
│  │  • Recibe: texto + modo (FIEL/ESTRUCTURADO)            │    │
│  │  • Aplica diccionario médico                           │    │
│  │  • Envía a IA con ejemplos de aprendizaje              │    │
│  │  • Devuelve: texto mejorado                            │    │
│  └───────────────────┬────────────────────────────────────┘    │
│                      │                                          │
│                      ▼                                          │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  API 3: guardar_correccion_aprendizaje                 │    │
│  │  • Recibe: texto_ia + texto_final                       │    │
│  │  • Calcula diferencias con difflib                      │    │
│  │  • Analiza semánticamente (score 0-100)                │    │
│  │  • Guarda en BD                                         │    │
│  │  • Invalida caché del usuario                          │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AIService - ai_services.py                    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  transcribe_audio() - Whisper                           │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │ 1. Verificar caché (MD5 hash Audio) - 1h        │   │   │
│  │  │ 2. Si no está cacheado: llamar OpenAI Whisper   │   │   │
│  │  │ 3. Guardar en caché                              │   │   │
│  │  │ 4. Retornar transcripción                        │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  improve_medical_text() - GPT-4o-mini/Groq              │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │ 1. Hash (texto+modo+usuario)                     │   │   │
│  │  │ 2. Verificar caché - 30min                       │   │   │
│  │  │ 3. Si no está cacheado:                          │   │   │
│  │  │    a. Obtener ejemplos de aprendizaje (caché)    │   │   │
│  │  │    b. Construir prompt optimizado                │   │   │
│  │  │    c. Llamar LLM (GPT-4o-mini prioritario)       │   │   │
│  │  │    d. Fallback a Groq si falla                   │   │   │
│  │  │ 4. Guardar en caché                              │   │   │
│  │  │ 5. Retornar texto mejorado                       │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────┬───────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    APIs EXTERNAS                                │
│  ┌──────────────────┐         ┌────────────────────────────┐   │
│  │  OpenAI Whisper  │         │  GPT-4o-mini / Groq LLM    │   │
│  │  • Transcripción │         │  • Mejora de texto         │   │
│  │  • Speech-to-Text│         │  • Modo FIEL/ESTRUCTURADO  │   │
│  └──────────────────┘         └────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BASE DE DATOS (SQLite/PostgreSQL)            │
│                                                                 │
│  ┌──────────────────┐  ┌─────────────────────────────────┐     │
│  │  TerminoMedico   │  │  CorreccionAprendizaje          │     │
│  │  • 200+ términos │  │  • Textos: original/ia/final    │     │
│  │  • Correcciones  │  │  • Cambios detectados (JSON)    │     │
│  │  • Frecuencia    │  │  • Score semántico              │     │
│  └──────────────────┘  │  • Categoría                    │     │
│                        └─────────────────────────────────┘     │
│  ┌──────────────────┐  ┌─────────────────────────────────┐     │
│  │ PlantillaInforme │  │  Informe (opcional)             │     │
│  │  • Por tipo      │  │  • Datos paciente               │     │
│  │  • Contenido     │  │  • Estado, firma                │     │
│  └──────────────────┘  └─────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SISTEMA DE CACHÉ (Django Cache)              │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Capa 1: Transcripciones (1 hora)                      │    │
│  │  • Key: whisper_transcription_{md5_audio}              │    │
│  │  • Evita re-transcribir mismo audio                    │    │
│  └────────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Capa 2: Mejoras de texto (30 min)                     │    │
│  │  • Key: mejora_texto_{hash}                            │    │
│  │  • Hash = texto + modo + usuario                       │    │
│  └────────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Capa 3: Ejemplos de aprendizaje (10 min)             │    │
│  │  • Key: ejemplos_aprendizaje_{user_id}                │    │
│  │  • Invalida al guardar nueva corrección               │    │
│  └────────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Capa 4: Ejemplos de estilo (15 min) ⚠️ NO USADO      │    │
│  │  • Key: ejemplos_estilo_{user_id}                      │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 FLUJO DETALLADO - PASO A PASO

### **FASE 1: Grabación y Transcripción**

```
1. Usuario presiona botón de micrófono
   ↓
2. MediaRecorder captura audio (WebM/Opus)
   ↓
3. [OPCIONAL] Web Speech API muestra preview en tiempo real
   ↓
4. Usuario suelta botón
   ↓
5. Audio se codifica en Base64
   ↓
6. POST a /api/transcribir-whisper/
   {
     audio: "data:audio/webm;base64,..."
   }
   ↓
7. Backend decodifica Base64 → bytes
   ↓
8. AIService.transcribe_audio()
   ├── Calcula MD5 del audio
   ├── Busca en caché (whisper_transcription_{hash})
   │   ├── SI EXISTE → retorna del caché ⚡
   │   └── SI NO EXISTE:
   │       ├── Llama OpenAI Whisper API
   │       ├── Guarda en caché (1 hora)
   │       └── Retorna transcripción
   ↓
9. TerminoMedico.procesar_comandos_voz()
   ├── Reemplaza "punto" → "."
   ├── Reemplaza "nueva línea" → "\n"
   ├── Convierte "grado 1" → "grado I"
   └── Limpia artefactos
   ↓
10. Retorna JSON:
    {
      success: true,
      texto_transcrito: "...",
      confianza: 0.95
    }
```

### **FASE 2: Mejora con IA**

```
11. Frontend recibe texto transcrito
    ↓
12. Usuario puede editar o presionar "Mejorar con IA"
    ↓
13. POST a /api/mejorar-texto/
    {
      texto_original: "...",
      modo: "FIEL",  // o "ESTRUCTURADO"
      tipo_estudio: "RES"
    }
    ↓
14. TerminoMedico.aplicar_correcciones()
    ├── Busca términos incorrectos en BD
    ├── Reemplaza usando regex (case-insensitive)
    ├── Incrementa frecuencia_uso
    └── Retorna texto corregido + lista de correcciones
    ↓
15. AIService.improve_medical_text()
    ├── Calcula hash: MD5(texto + modo + user_id)
    ├── Busca en caché (mejora_texto_{hash})
    │   ├── SI EXISTE → retorna del caché ⚡
    │   └── SI NO EXISTE:
    │       ├── Obtener ejemplos aprendizaje (10 min cache)
    │       │   └── CorreccionAprendizaje.obtener_ejemplos_aprendizaje()
    │       │       ├── Trae correcciones del usuario
    │       │       ├── Extrae cambios con score > 60
    │       │       ├── Ordena por score (mayor = más importante)
    │       │       └── Retorna top 20 ejemplos
    │       ├── Construir prompt según modo:
    │       │   ├── FIEL: "Corrige solo ortografía"
    │       │   └── ESTRUCTURADO: "Crea informe con plantilla"
    │       ├── Agregar ejemplos al prompt
    │       ├── Llamar LLM (GPT-4o-mini prioritario)
    │       │   └── Si falla → Fallback a Groq (gratis)
    │       ├── Guardar en caché (30 min)
    │       └── Retorna texto mejorado
    ↓
16. Retorna JSON:
    {
      success: true,
      texto_mejorado: "...",
      confianza: 0.90,
      correcciones_aplicadas: [...]
    }
```

### **FASE 3: Aprendizaje Automático**

```
17. Frontend muestra texto mejorado
    ↓
18. Usuario edita el texto (opcional)
    ↓
19. Usuario presiona "Copiar Texto"
    ↓
20. Al copiar, se guarda automáticamente:
    POST a /api/guardar-aprendizaje/
    {
      texto_original: "transcripción Whisper",
      texto_ia: "texto mejorado por IA",
      texto_final: "texto editado por usuario"
    }
    ↓
21. CorreccionAprendizaje.create()
    ├── Guarda textos en BD
    └── Llama calcular_diferencias()
        ↓
22. calcular_diferencias()
    ├── Usa difflib.SequenceMatcher
    ├── Detecta: reemplazos, agregados, eliminados
    ├── Para cada cambio:
    │   ├── _categorizar_cambio()
    │   │   ├── ortografia (acentos, mayúsculas)
    │   │   ├── terminologia (palabras similares)
    │   │   ├── clasificacion (grados)
    │   │   ├── estructural (texto +50% más largo)
    │   │   └── semantico (significado diferente)
    │   └── _calcular_score_importancia()
    │       ├── Score base según categoría
    │       ├── +10 si contiene términos críticos
    │       └── -30 si cambio muy pequeño
    ├── Guarda en cambios_detectados (JSON)
    └── Invalida caché del usuario
    ↓
23. Próxima transcripción:
    ├── Ejemplos con score > 60 se incluyen en prompt
    ├── IA aprende automáticamente del usuario
    └── Ciclo de mejora continua
```

---

## 📊 MODELO DE DATOS - RELACIONES

```
┌──────────────────────────────────────────────────────────────────┐
│                         User (Django Auth)                       │
├──────────────────────────────────────────────────────────────────┤
│  • username                                                      │
│  • email                                                         │
│  • is_superuser                                                  │
└────────┬─────────────────────────────────────┬───────────────────┘
         │                                     │
         │ medico                 usuario      │
         │                                     │
         ▼                                     ▼
┌─────────────────────────┐      ┌─────────────────────────────┐
│    Informe ⚠️ POCO USADO│      │  CorreccionAprendizaje ✅   │
├─────────────────────────┤      ├─────────────────────────────┤
│ • nombre_paciente       │      │ • texto_original            │
│ • dni_paciente          │      │ • texto_ia                  │
│ • tipo_estudio [FK]     │      │ • texto_final               │
│ • numero_estudio        │      │ • cambios_detectados (JSON) │
│ • fecha_estudio         │      │   [                         │
│ • hallazgos             │      │     {tipo, de, a, score}    │
│ • conclusion            │      │   ]                         │
│ • estado [FK]           │      │ • fue_aplicada              │
│ • medico [FK User]      │      │ • votos_utilidad            │
│ • procesado_con_ia ✓    │      │ • usuario [FK User]         │
│ • confianza_ia          │      │ • tipo_estudio [FK]         │
│ • sugerencias_ia (JSON) │      │ • fecha_creacion            │
└────────┬────────────────┘      └─────────────────────────────┘
         │                                     │
         │ informe                             │
         ▼                                     │
┌─────────────────────────┐                   │
│ AudioTranscripcion      │                   │
│ ⚠️ POCO USADO           │                   │
├─────────────────────────┤                   │
│ • archivo_audio         │                   │
│ • duracion_segundos     │                   │
│ • texto_original        │                   │
│ • texto_mejorado        │                   │
│ • servicio_transcripcion│                   │
│ • confianza_transcripcion│                  │
│ • informe [FK]          │                   │
│ • grabado_por [FK User] │                   │
└─────────────────────────┘                   │
                                              │
┌─────────────────────────────────────────────┼───────────────────┐
│                    TerminoMedico ✅ ACTIVO  │                   │
├─────────────────────────────────────────────┤                   │
│ • termino_incorrecto (UNIQUE)               │                   │
│ • termino_correcto                          │                   │
│ • categoria [FK CategoriaTerminoMedico]     │                   │
│ • frecuencia_uso (auto-increment)           │                   │
│ • activo ✓                                  │                   │
│ • notas                                     │                   │
│                                             │                   │
│ Métodos:                                    │                   │
│ • aplicar_correcciones(texto) [STATIC]      │                   │
│ • procesar_comandos_voz(texto) [STATIC]     │                   │
└─────────────────────────────────────────────┘                   │
                                                                  │
┌─────────────────────────────────────────────────────────────────┘
│              PlantillaInforme ⚠️ POCO USADO
├─────────────────────────────────────────────┐
│ • nombre                                    │
│ • tipo_estudio [FK TipoEstudio]             │
│ • contenido (TEXT)                          │
│ • variables (JSON)                          │
│ • activa ✓                                  │
│ • creada_por [FK User]                      │
└─────────────────────────────────────────────┘

[FK] = Foreign Key
✅ = En uso activo
⚠️ = Uso parcial o poco frecuente
```

---

## 🎨 INTERFACES DE USUARIO

### **1. Dashboard Principal**
```
/dictado_informes/
│
├── [HERO] Bienvenido al Sistema de Dictado IA
├── [STATS]
│   ├── Total Informes: 42
│   ├── Pendientes: 5
│   ├── Finalizados: 30
│   ├── Firmados: 7
│   └── Plantillas: 8
├── [CHART] Informes por tipo de estudio
└── [LIST] Informes recientes (últimos 10)
```

### **2. Dictado Rápido (Principal) ✅**
```
/dictado_informes/dictado-rapido/
│
├── [HEADER]
│   ├── Título: "Dictado Rápido con Whisper AI"
│   ├── Powered by: Whisper + Groq IA
│   └── Botón Historial (contador)
│
├── [CONTROLS]
│   ├── Toggle: Preview Tiempo Real
│   ├── Toggle: Modo Automático
│   └── Toggle: Copiado Automático
│
├── [RECORDING AREA]
│   ├── Botón Micrófono (grande, rojo)
│   ├── Timer: 00:00.0s
│   └── Estado: "Listo para grabar"
│
├── [PREVIEW] (si está activado)
│   └── Texto en tiempo real (Web Speech API)
│
├── [RESULTS]
│   ├── Panel 1: Transcripción Whisper
│   │   └── Texto con correcciones del diccionario
│   ├── Panel 2: Texto Mejorado por IA
│   │   └── Con aplicación de aprendizaje
│   └── Botones:
│       ├── Copiar Texto (guarda aprendizaje auto)
│       └── Guardar Manual (opcional)
│
├── [NOTIFICATION]
│   └── "✅ Aprendizaje guardado: 3 cambios detectados"
│
└── [TIPS]
    └── Cómo dictar para mejores resultados
```

### **3. Diccionario Médico**
```
/dictado_informes/diccionario/
│
├── [STATS]
│   ├── Total: 215 términos
│   ├── Activos: 198
│   └── Top 5 más usados
│
├── [FILTERS]
│   ├── Categoría: [Dropdown]
│   ├── Estado: Activo/Inactivo
│   └── Búsqueda
│
├── [TABLE]
│   ├── Término Incorrecto
│   ├── Término Correcto
│   ├── Categoría
│   ├── Frecuencia
│   └── Acciones
│
└── [BUTTON] + Agregar Término
```

### **4. Admin - Correcciones de Aprendizaje**
```
/admin/dictado_informes/correccionaprendizaje/
│
├── [FILTERS]
│   ├── Usuario
│   ├── Tipo de Estudio
│   ├── Aplicada: Sí/No
│   └── Fecha
│
├── [ACTIONS]
│   ├── ✅ Marcar como aplicada
│   ├── 🔄 Recalcular diferencias
│   ├── 📥 Exportar para entrenamiento
│   └── 👁️ Ver ejemplos usados en prompt IA
│
└── [DETAIL VIEW]
    ├── Textos (preview + completo)
    ├── Análisis de cambios
    │   ├── Diferencias visuales (rojo/verde)
    │   ├── Categorías
    │   └── Scores
    └── Metadatos
```

---

## 🔧 CONFIGURACIÓN Y DEPENDENCIAS

### **Variables de Entorno Requeridas**
```bash
# .env
OPENAI_API_KEY=sk-...          # Para Whisper (transcripción) + GPT-4o-mini (LLM)
GROQ_API_KEY=gsk_...           # OPCIONAL: Fallback gratuito para LLM
```

### **Configuración de Proveedores**

```python
# Prioridad de LLM:
# 1. OpenAI GPT-4o-mini (PRIORITARIO)
#    - Mejor calidad médica
#    - Costo: ~$0.0003 USD/informe
# 2. Groq Llama-3.3-70b (FALLBACK)
#    - Gratis (14,400 req/día)
#    - Si OpenAI falla o no está configurado

# Transcripción:
# - OpenAI Whisper (ÚNICO)
#   - Mejor precisión médica
#   - Incluye $5 gratis al crear cuenta
```

### **Dependencias Python**
```python
# requirements.txt (relacionadas con dictado)
openai==1.x.x           # Cliente para Whisper + GPT
python-decouple         # Manejo de .env
django-cache            # Sistema de caché
```

### **Configuración Django**
```python
# settings.py
INSTALLED_APPS = [
    # ...
    'dictado_informes.apps.DictadoInformesConfig',
]

TEMPLATES = [
    {
        'OPTIONS': {
            'context_processors': [
                'dictado_informes.context_processors.terminos_activos',
            ],
        },
    },
]

# Caché (default: local-memory)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
```

---

## 📈 MÉTRICAS DE PERFORMANCE

### **Tiempos de Respuesta (Promedio)**

| Operación | Sin Caché | Con Caché | Mejora |
|-----------|-----------|-----------|--------|
| Transcripción Whisper | 2-4s | 0.05s | 98% ⚡ |
| Mejora con IA (modo FIEL) | 1-2s | 0.05s | 97% ⚡ |
| Mejora con IA (modo ESTRUCTURADO) | 3-5s | 0.05s | 99% ⚡ |
| Aplicar diccionario médico | 0.1s | N/A | - |
| Guardar aprendizaje | 0.3s | N/A | - |

### **Uso de Caché (Estimado)**

- **Hit Rate esperado:** 40-60% (depende de repetición de contenido)
- **Reducción de llamadas API:** ~60% según documentación
- **Ahorro de costos:** ~$3-5 USD/mes (30 informes/día)

### **Límites de API**

**OpenAI:**
- Whisper: Sin límite específico (pago por uso)
- GPT-4o-mini: 
  - Input: $0.15 / 1M tokens
  - Output: $0.60 / 1M tokens
  - Estimado/informe: ~$0.0003 USD

**Groq (Fallback gratis):**
- 14,400 requests/día
- 30 requests/minuto
- 20,000 tokens/minuto

---

## 🔐 SEGURIDAD Y PERMISOS

### **Restricciones de Acceso**

```python
# Todas las vistas requieren:
LoginRequiredMixin + SuperuserRequiredMixin

# Solo superusuarios pueden:
- Dictar informes
- Ver dashboard
- Gestionar diccionario médico
- Acceder a admin de correcciones
```

### **Datos Sensibles**

- ✅ Audios NO se almacenan permanentemente (solo en memoria)
- ✅ Textos de correcciones se almacenan por usuario
- ⚠️ NO hay anonimización de datos del paciente (si se implementa guardar informes)

### **CSRF Protection**

```html
<!-- Todas las APIs AJAX usan CSRF token -->
<input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">

fetch('/api/...', {
    headers: {
        'X-CSRFToken': getCookie('csrftoken')
    }
})
```

---

## 📚 REFERENCIAS TÉCNICAS

### **Algoritmos Clave**

1. **difflib.SequenceMatcher** - Detección de cambios
   - Usado en `CorreccionAprendizaje.calcular_diferencias()`
   - Detecta: replace, insert, delete

2. **MD5 Hashing** - Caché de audio/texto
   - Audio: `hashlib.md5(audio_bytes).hexdigest()`
   - Texto: `hashlib.md5(text_string.encode()).hexdigest()`

3. **Análisis Semántico** - Categorización automática
   - Ortografía: similitud > 95% sin acentos
   - Terminología: similitud 60-95%
   - Clasificación: contiene "grado", "tipo", etc.

### **Prompts de IA**

**Ubicación:** `ai_services.py:245-700`

**3 Modos implementados:**

1. **MODO FIEL** (80% más corto)
   - Solo corrige ortografía
   - Mantiene formato original
   - Incluye ejemplos de aprendizaje

2. **MODO ESTRUCTURADO**
   - Crea informe con plantilla específica
   - Reemplaza hallazgos anormales
   - Conserva líneas normales no mencionadas

3. **MODO PLANTILLA**
   - Completa campos de plantilla existente
   - Respeta estructura pre-definida
   - No modifica campos ya completos

---

**Última actualización:** 8 de marzo de 2026  
**Autor:** Análisis generado por GitHub Copilot (Claude Sonnet 4.5)
