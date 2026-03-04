# Guía de GitHub Copilot CLI para el Proyecto

## 📦 Instalación
✅ Ya instalado: `@github/copilot@0.0.421`

## � Idioma
⚠️ **IMPORTANTE**: La CLI de Copilot solo está disponible en inglés actualmente. No hay opción para cambiar el idioma, pero esta guía traduce todos los comandos y mensajes importantes.
## 🤔 ¿Cuándo Usar Qué? VS Code Chat vs CLI

### 💬 **Usa VS Code Chat (donde estás ahora)** cuando:

✅ **Quieres conversar y explorar:**
- "¿Cómo debería implementar esta funcionalidad?"
- "Explícame cómo funciona este código"
- "¿Qué alternativas tengo para resolver X?"

✅ **Necesitas contexto visual:**
- Estás viendo un archivo y quieres modificarlo
- Quieres ver errores en tiempo real
- Necesitas iterar sobre cambios (hacer → revisar → ajustar)

✅ **Cambios incrementales e interactivos:**
- Modificar un archivo específico que tienes abierto
- Debugging paso a paso
- Aprender mientras trabajas

✅ **Tareas complejas que requieren discusión:**
- "Ayúdame a diseñar la arquitectura de este módulo"
- "Revisa este código y sugiere mejoras"
- "¿Hay algún problema de seguridad aquí?"

**Ejemplo típico:**
```
Tú: "El modal de duplicados no funciona bien, ayúdame a mejorarlo"
Yo: [Analizo el código, explico el problema, implemento la solución]
Tú: "Perfecto, pero el ancho es muy grande"
Yo: [Ajusto el ancho y optimizo]
```

### ⚡ **Usa la CLI de Copilot** cuando:

✅ **Tareas automatizables y directas:**
- "Agregar campo al modelo y crear migración"
- "Crear tests para este módulo"
- "Refactorizar esta función"

✅ **Planificación de cambios grandes:**
```bash
/plan "refactorizar liquidación/views.py separando lógica en services"
# Te muestra el esquema ANTES de ejecutar
```

✅ **Delegar tareas y olvidarte:**
```bash
/delegate "documentar todas las funciones de liquidacion/models.py con docstrings"
# Se ejecuta en background, puedes seguir trabajando
```

✅ **Comparar estrategias entre modelos:**
```bash
/model "optimizar query de pedidos pendientes"
# GPT-4 vs Claude vs otros modelos te dan diferentes enfoques
```

✅ **Tareas repetitivas en múltiples archivos:**
```bash
/fleet "agregar type hints a todos los models" "actualizar docstrings en views" "crear tests para forms"
# Múltiples tareas en paralelo
```

**Ejemplo típico:**
```bash
/plan "agregar campo telefono al modelo Paciente"
→ Te muestra: "Voy a modificar estos 3 archivos..."
→ Tú: "OK" (Enter)
→ Listo, cambios aplicados automáticamente
```

## 🚀 Múltiples Agentes: El Concepto `/fleet`

### ¿Qué es `/fleet`?

**Concepto:** Imagina que puedes "clonar" a Copilot en 3 o 4 versiones que trabajan simultáneamente en tareas diferentes.

### Ejemplo Práctico:

**Escenario:** Tienes que mejorar 3 módulos de tu proyecto

**❌ Forma tradicional (secuencial):**
```bash
# Tarea 1 → esperas 5 min → termina
/plan "agregar tests a liquidacion"
# Tarea 2 → esperas 5 min → termina  
/plan "documentar consultorios"
# Tarea 3 → esperas 5 min → termina
/plan "optimizar queries en pedidos"
# Total: 15 minutos
```

**✅ Con `/fleet` (paralelo):**
```bash
/fleet "agregar tests a liquidacion" "documentar consultorios" "optimizar queries en pedidos"

# Copilot lanza 3 "agentes" simultáneos:
Agent 1: Working on tests...     ████████░░ 80%
Agent 2: Working on docs...      ████████░░ 80%  
Agent 3: Working on queries...   ██████░░░░ 60%

# Total: ~5-7 minutos (en paralelo)
```

### Cuándo Usar `/fleet`:

✅ **Múltiples tareas INDEPENDIENTES:**
- Agregar tests a 3 módulos diferentes
- Documentar varios archivos
- Pequeñas refactorizaciones en módulos separados

❌ **NO usar para tareas DEPENDIENTES:**
- "Crear modelo → Crear migración → Actualizar formulario"
  (Estas deben hacerse en orden, usa `/plan` normal)

### Límites:
- Máximo 4-5 agentes simultáneos
- Cada agente puede usar un modelo diferente (GPT-4, Claude, etc.)
- Revisa resultados en la pestaña "Agents" de VS Code

## 📊 Comparativa Visual: VS Code Chat vs CLI

| Aspecto | VS Code Chat (yo) | Copilot CLI |
|---------|-------------------|-------------|
| **Interactividad** | 🟢 Alta (conversacional) | 🟡 Media (comandos directos) |
| **Velocidad** | 🟡 Iterativa | 🟢 Rápida (ejecuta directamente) |
| **Contexto visual** | 🟢 Ve tu código abierto | 🟡 Solo archivos que le indiques |
| **Explicaciones** | 🟢 Puedes preguntar "¿por qué?" | 🟡 Solo ejecuta |
| **Tareas paralelas** | ❌ No (una a la vez) | 🟢 Sí (con `/fleet`) |
| **Planificación previa** | 🟡 Puedes pedirla | 🟢 Automática con `/plan` |
| **Aprendizaje** | 🟢 Excelente (explica todo) | 🟡 Limitado |
| **Automatización** | 🟡 Manual | 🟢 Automática |
| **Delegación** | ❌ Tienes que estar presente | 🟢 Asignas y te olvidas |

## 🎯 Estrategia Recomendada (Cómo Combinarlas)

### Flujo de Trabajo Ideal:

```
1. 💬 Planea en VS Code Chat (conmigo):
   "Quiero agregar validación de email a los formularios, ¿qué me recomiendas?"
   → Discutimos opciones, arquitectura, etc.

2. ⚡ Ejecuta en CLI:
   /plan "implementar validación de email según lo discutido"
   → Aplica los cambios rápidamente

3. 💬 Revisa y ajusta en VS Code Chat:
   "El validador funciona pero quiero que sea más estricto"
   → Refinamos el código

4. ⚡ Tareas repetitivas en CLI:
   /fleet "agregar tests" "actualizar docs" "crear ejemplos"
   → Tareas automatizables en paralelo
```

### Para Tu Proyecto Específico:

**📝 Caso 1: Nueva Funcionalidad Grande**
```
VS Code Chat: "Quiero agregar sistema de notificaciones push"
→ Discutimos arquitectura, modelos, vistas
→ Diseñamos la solución

CLI: /plan "implementar sistema de notificaciones según diseño"
→ Genera todos los archivos automáticamente

VS Code Chat: "Revisa el código generado"
→ Refinamos detalles
```

**🐛 Caso 2: Bug Fixing**
```
VS Code Chat: "El modal de duplicados no funciona"
→ Analizo el problema
→ Implemento la solución
→ Explicamos el fix
```

**🧪 Caso 3: Testing Masivo**
```
CLI: /fleet "tests para liquidacion" "tests para pedidos" "tests para consultorios"
→ Genera tests en paralelo para 3 módulos
```

**📚 Caso 4: Documentación**
```
CLI: /delegate "agregar docstrings a todos los modelos del proyecto"
→ Se ejecuta en background
→ Puedes seguir trabajando en otra cosa
```

## 🎬 Ejemplos Reales con Tu Proyecto

### Ejemplo 1: Mejorar el Sistema de Preinformes

**Situación:** Quieres agregar un campo "observaciones" al preinforme

```
┌──────────────────────────────────────────────────┐
│ VS Code Chat (para diseño y arquitectura)       │
└──────────────────────────────────────────────────┘

Tú: "Quiero agregar un campo 'observaciones' al preinforme 
     para que el residente pueda poner notas internas. 
     ¿Dónde debería ir y qué tipo de campo usar?"

Yo: "Recomiendo:
     - Campo TextField en preinformes/models.py
     - Debe ser blank=True, null=True (opcional)
     - Agregarlo al formulario PreinformeForm
     - Mostrarlo en la vista de revisión
     ¿Quieres que lo implemente?"

Tú: "Sí, pero no lo muestres en el export a EGES"

Yo: [Implemento considerando esa restricción]

┌──────────────────────────────────────────────────┐
│ CLI (para tareas automatizables después)         │
└──────────────────────────────────────────────────┘

# Ahora que ya está implementado, automatizar:
/fleet "crear tests para campo observaciones" "documentar el nuevo campo" "agregar validación de longitud"
```

### Ejemplo 2: Optimización General del Sistema

**Situación:** Quieres optimizar varios módulos

```
┌──────────────────────────────────────────────────┐
│ VS Code Chat (para análisis)                     │
└──────────────────────────────────────────────────┘

Tú: "¿Qué módulos de mi proyecto podrían optimizarse?"

Yo: [Analizo el código]
    "He identificado:
     1. liquidacion/views.py - queries N+1
     2. pedidos/models.py - sin índices en campos de búsqueda
     3. consultorios/utils.py - lógica duplicada"

┌──────────────────────────────────────────────────┐
│ CLI (para ejecutar en paralelo)                   │
└──────────────────────────────────────────────────┘

/fleet "optimizar queries en liquidacion/views.py con select_related" "agregar índices a pedidos/models.py" "refactorizar consultorios/utils.py eliminando duplicación"

# 3 agentes trabajan simultáneamente
```

### Ejemplo 3: Agregar Tests a Todo el Proyecto

**Situación:** Necesitas más cobertura de tests

```
┌──────────────────────────────────────────────────┐
│ VS Code Chat (para estrategia)                   │
└──────────────────────────────────────────────────┘

Tú: "Mi coverage de tests está bajo, ¿por dónde empiezo?"

Yo: "Prioridad:
     1. liquidacion (crítico - dinero)
     2. pedidos_estudios (automatización)
     3. preinformes (nuevo, poco testeado)
     
     Te recomiendo usar pytest-django con fixtures"

┌──────────────────────────────────────────────────┐
│ CLI (para generar tests en masa)                  │
└──────────────────────────────────────────────────┘

# Tests en paralelo:
/fleet "tests completos para liquidacion/models.py" "tests para pedidos_estudios/views.py" "tests para preinformes/forms.py"

# Mientras se ejecutan, sigues trabajando en otra cosa
```

### Ejemplo 4: Debugging de un Problema Específico

**Situación:** Un error que no entiendes

```
┌──────────────────────────────────────────────────┐
│ VS Code Chat SOLAMENTE (debugging interactivo)   │
└──────────────────────────────────────────────────┘

Tú: "El cálculo de liquidación da un resultado incorrecto 
     cuando hay bonificaciones"

Yo: [Analizo liquidacion/models.py]
    "El problema está en la línea 145, el orden de operaciones
     está aplicando la bonificación antes del descuento"
    
Tú: "¿Cómo lo arreglo?"

Yo: [Explico y muestro código corregido]

Tú: "¿Podría pasar en otros lugares?"

Yo: [Busco patrones similares en el código]

# ⚠️ NO usar CLI aquí - debugging requiere conversación
```

### Ejemplo 5: Refactorización Grande y Planificada

**Situación:** Separar views.py en servicios

```
┌──────────────────────────────────────────────────┐
│ VS Code Chat (planear primero)                   │
└──────────────────────────────────────────────────┘

Tú: "La liquidacion/views.py tiene 1000 líneas, 
     quiero separar la lógica de cálculo"

Yo: "Propongo esta estructura:
     - liquidacion/services/
       - calculadora.py (lógica de cálculo)
       - validador.py (validaciones)
       - reportes.py (generación de PDFs)
     - views.py solo llama a los servicios
     
     ¿Te parece bien esta arquitectura?"

Tú: "Sí, pero mantén reportes.py en otro lado"

┌──────────────────────────────────────────────────┐
│ CLI (ejecutar el refactor)                        │
└──────────────────────────────────────────────────┘

/plan "refactorizar liquidacion/views.py:
       - crear liquidacion/services/calculadora.py con lógica de cálculo
       - crear liquidacion/services/validador.py con validaciones
       - mantener reportes en liquidacion/utils.py
       - actualizar imports en views.py
       - mantener compatibilidad con tests existentes"

# Te muestra el plan completo ANTES de ejecutar
# Puedes revisarlo y aprobar o rechazar
```

## 🎪 ¿Cuándo Usar `/delegate` vs `/plan`?

### `/plan` - "Quiero ver antes de ejecutar"
```bash
/plan "agregar campo email al modelo Paciente"

# Te muestra:
📋 Plan:
   1. Edit: preinformes/models.py
      - Add email field (EmailField)
   2. Create: preinformes/migrations/0018_add_email.py
   3. Edit: preinformes/forms.py
      - Add email to PreinformeForm
   4. Edit: preinformes/admin.py
      - Add email to list_display

Do you want to proceed? (Y/n)
```
✅ Usarlo: Cuando quieres REVISAR antes de aplicar

### `/delegate` - "Hazlo y avísame cuando termines"
```bash
/delegate "agregar docstrings tipo Google a todos los modelos"

# Se ejecuta en background
✓ Task delegated. Check Agents panel for progress.
  → "Tarea delegada. Revisa el panel Agentes para ver progreso"

# Sigues trabajando, te avisa cuando termina
```
✅ Usarlo: Tareas repetitivas que no necesitan supervisión

## 💡 Regla de Oro

**🤔 ¿Necesitas pensar, discutir, aprender?** → VS Code Chat (yo)

**⚡ ¿Sabes exactamente qué hacer y solo quieres ejecutar?** → CLI

**🚀 ¿Muchas tareas repetitivas independientes?** → CLI con `/fleet`

**🔍 ¿Quieres ver el plan antes de ejecutar?** → CLI con `/plan`

**🎯 ¿Tarea automatizable sin supervisión?** → CLI con `/delegate`
## 🔐 Autenticación (Primer Uso)

**1. Iniciar sesión:**
```bash
copilot
# Luego escribe: /login
```

**Qué hacer:**
1. Se abrirá tu navegador en GitHub
2. Copia el código que aparece en el terminal (ejemplo: `A1B2-C3D4`)
3. Pégalo en la página de GitHub que se abrió
4. Haz clic en "Authorize" (Autorizar)
5. ✅ Vuelve al terminal, verás: `✓ You are now logged in`

**Mensaje de éxito:**
```
✓ You are now logged in
```
Traducción: "Ya has iniciado sesión"

**Si aparece un error:**
```
✗ Not authenticated. Please login first.
```
Traducción: "No autenticado. Por favor inicia sesión primero."
→ Solución: Ejecuta `/login` nuevamente

## 🚀 Primeros Pasos Después del Login

**Paso 1: Verificar que detectó el archivo de instrucciones**
```bash
# La CLI debería mostrar:
● Found copilot-instructions.md in project root
  → "Encontrado copilot-instructions.md en la raíz del proyecto"
```

Si dice `No copilot instructions found`, escribe `/init` para crearlo.

**Paso 2: Probar tu primer comando**
```bash
# Escribe en el terminal de copilot:
/plan "agregar un campo de teléfono al modelo de paciente"
```

Verás algo como:
```
📋 Generating plan... (wait a few seconds)
  → "Generando plan... (espera unos segundos)"

Plan to add phone field to patient model:

1. Edit: preinformes/models.py
   - Add phone field to Preinforme model
   
2. Create: preinformes/migrations/0017_add_phone_field.py
   - Generate migration

3. Edit: preinformes/forms.py
   - Add phone field to form

Do you want to proceed with this plan? (Y/n)
  → "¿Quieres proceder con este plan? (S/n)"
```

**Paso 3: Revisar y aprobar (o rechazar)**
- Escribe `Y` (o `S`) para aplicar los cambios
- Escribe `n` para cancelar
- Presiona `Ctrl+C` para abortar completamente

## 🎯 Comandos Principales (Traducidos)

### 1. `/plan` - Planificar Cambios Grandes
Genera un esquema revisable antes de modificar múltiples archivos.

**Ejemplo aplicado a tu proyecto:**
```bash
copilot /plan "refactorizar el módulo de liquidación para separar la lógica de cálculo en servicios independientes"
```

**Ventajas:**
- Ve un resumen de todos los archivos que se modificarán
- Revisa la estrategia antes de ejecutar
- Previene errores en cambios complejos

### 2. `/model` - Comparar Modelos
Compara diferentes estrategias entre modelos de IA.

**Ejemplo:**
```bash
copilot /model "optimizar la consulta de pedidos pendientes en pedidos_estudios"
```

**Ventajas:**
- Obtén diferentes perspectivas sobre el mismo problema
- Compara Claude vs GPT-4 vs otros modelos
- Elige la mejor solución

### 3. `/delegate` - Delegar Tareas
Asigna trabajo específico manteniendo el contexto.

**Ejemplo aplicado a tu proyecto:**
```bash
copilot /delegate "crear tests unitarios para el módulo de liquidacion/models.py"
```

**Ventajas:**
- El agente trabaja de forma autónoma
- Puedes revisar el resultado en la pestaña Agentes
- Mantiene el historial visible

### 4. `/fleet` - Subagentes Paralelos
Ejecuta múltiples tareas en paralelo.

**Ejemplo:**
```bash
copilot /fleet "agregar validaciones a formularios de pedidos" "optimizar queries en consultorios" "actualizar tests de agenda"
```

**Ventajas:**
- Múltiples tareas simultáneas
- Más rápido para cambios independientes
- Cada subagente puede usar un modelo diferente

### 5. `/init` - Crear AGENTS.md
Genera un archivo de configuración para estandarizar el comportamiento.

**Ejemplo:**
```bash
copilot /init
```

**Crea un archivo con reglas como:**
```markdown
# Agent Instructions

## Django Best Practices
- Siempre usar timezone-aware datetimes (django.utils.timezone.now())
- Seguir estructura de apps Django estándar
- Validaciones en modelos Y formularios
- Tests con pytest-django

## Proyecto Específico
- El sistema gestiona servicios médicos
- Apps principales: liquidacion, pedidos_estudios, consultorios, agenda
- Base de datos: SQLite local, PostgreSQL en producción
- Usar decoradores personalizados en accounts/decorators.py
```

## 🚀 Casos de Uso para Tu Proyecto

### Caso 1: Refactorización Segura de Liquidación
```bash
# 1. Planificar primero
copilot /plan "mover lógica de cálculo de liquidacion/views.py a liquidacion/services.py"

# 2. Revisar el plan
# 3. Ejecutar si se ve bien
```

### Caso 2: Agregar Feature Nueva
```bash
# Delegar la creación de una nueva funcionalidad
copilot /delegate "crear módulo de notificaciones push para avisos de pedidos urgentes"
```

### Caso 3: Debugging Complejo
```bash
# Comparar soluciones entre modelos
copilot /model "resolver el problema de race condition en procesamiento automático de pedidos"
```

### Caso 4: Trabajo en Equipo
```bash
# 1. Crear AGENTS.md con reglas del proyecto
copilot /init

# 2. Commitearlo al repo
# 3. Todo el equipo tendrá el mismo comportamiento de Copilot
```

## 🎯 Ventajas Principales

### Para Ti Solo
- **Planificación**: Ve todo el cambio antes de ejecutarlo
- **Seguridad**: Menos riesgo de romper código
- **Velocidad**: Delega tareas repetitivas

### Para Trabajo en Equipo
- **Estandarización**: Todos los devs usan las mismas reglas
- **Documentación**: AGENTS.md documenta las prácticas del proyecto
- **Consistencia**: Copilot se comporta igual para todos

## 📝 Próximos Pasos

1. **Crear AGENTS.md para este proyecto**
   ```bash
   copilot
   /init
   ```

2. **Probar `/plan` en una refactorización pequeña**
   ```bash
   copilot
   /plan "agregar índice a campo fecha_estudio en pedidos"
   ```

3. **Usar `/delegate` para tareas específicas**
   ```bash
   copilot
   /delegate "documentar la API de liquidacion en docstrings"
   ```

## 📖 Diccionario de Mensajes Comunes (Inglés → Español)

### Mensajes de Estado
| Inglés | Español |
|--------|---------|
| `You must be logged in` | Debes iniciar sesión |
| `Please run /login` | Por favor ejecuta /login |
| `You are now logged in` | Ya has iniciado sesión |
| `Not authenticated` | No autenticado |
| `Environment loaded: Visual Studio Code connected` | Entorno cargado: VS Code conectado |
| `No copilot instructions found` | No se encontraron instrucciones de copilot |
| `Run /init to generate a copilot-instructions.md file` | Ejecuta /init para generar el archivo |

### Comandos del Terminal
| Comando | Traducción | Descripción |
|---------|------------|-------------|
| `/login` | Iniciar sesión | Autenticarte con GitHub |
| `/logout` | Cerrar sesión | Salir de tu cuenta |
| `/init` | Inicializar | Crear archivo de instrucciones |
| `/plan <prompt>` | Planificar | Ver esquema de cambios |
| `/delegate <prompt>` | Delegar | Asignar tarea a Copilot |
| `/model` | Modelo | Comparar modelos de IA |
| `/fleet` | Flota | Tareas paralelas |
| `/help` | Ayuda | Ver todos los comandos |
| `/clear` o `/new` | Limpiar | Nueva conversación |
| `/exit` | Salir | Cerrar la CLI |
| `/context` | Contexto | Ver uso de tokens |
| `/diff` | Diferencias | Ver cambios realizados |
| `/cwd` o `/cd` | Cambiar directorio | Ver o cambiar carpeta actual |

### Prompts de Confirmación
| Inglés | Español |
|--------|---------|
| `Are you sure?` | ¿Estás seguro? |
| `Do you want to continue?` | ¿Quieres continuar? |
| `Yes` | Sí |
| `No` | No |
| `Cancel` | Cancelar |
| `Please select an option` | Por favor selecciona una opción |
| `Enter to select` | Enter para seleccionar |
| `Esc to cancel` | Esc para cancelar |

### Mensajes de Progreso
| Inglés | Español |
|--------|---------|
| `Processing...` | Procesando... |
| `Generating plan...` | Generando plan... |
| `Analyzing code...` | Analizando código... |
| `Creating files...` | Creando archivos... |
| `Writing changes...` | Escribiendo cambios... |
| `Done!` | ¡Listo! |
| `Error:` | Error: |
| `Warning:` | Advertencia: |

## 🗣️ Ejemplo de Conversación (con Traducción)

```bash
❯ copilot
╭────────────────────────────────────────────╮
│          GitHub Copilot v0.0.421           │
│     Copilot uses AI. Check for mistakes    │
╰────────────────────────────────────────────╯

● Environment loaded: Visual Studio Code connected
  → "Entorno cargado: VS Code conectado"

● 💡 No copilot instructions found. Run /init
  → "No se encontraron instrucciones. Ejecuta /init"

❯ /init
  → "Inicializar instrucciones del proyecto"

✓ Created copilot-instructions.md
  → "✓ Creado copilot-instructions.md"

❯ /plan "agregar validación a formulario de pedidos"
  → "Planificar: agregar validación a formulario de pedidos"

📋 Plan:
  1. Edit: pedidos_estudios/forms.py
  2. Edit: pedidos_estudios/tests.py
  3. Add validation logic
  
Do you want to proceed? (Y/n)
  → "¿Quieres proceder? (S/n)"

❯ Y

✓ Changes applied successfully
  → "✓ Cambios aplicados exitosamente"
```

## 💡 Tips para Usar la CLI en Inglés

1. **Los prompts pueden ser en español:**
   ```bash
   /plan "agregar campo email al modelo Paciente"
   ```
   Copilot entiende español perfectamente en tus instrucciones.

2. **Usa Ctrl+C para cancelar en cualquier momento**

3. **Usa Tab para autocompletar comandos**

4. **Usa ↑↓ para navegar por el historial de comandos**

5. **Lee los mensajes clave:**
   - `✓` = Éxito
   - `✗` = Error
   - `●` = Información
   - `⚠` = Advertencia

## 🔧 Comandos de Terminal

**Iniciar CLI interactiva:**
```bash
copilot
```

**Ejecutar comando directo:**
```bash
copilot /plan "descripción del cambio"
```

**Ver ayuda:**
```bash
copilot --help
```

## 📊 Comparación: Antes vs Después

### Antes (solo VS Code Copilot)
- ✅ Chat con Copilot en VS Code
- ✅ Modificar archivos uno por uno
- ❌ Sin planificación previa visible
- ❌ Sin delegar tareas complejas
- ❌ Sin estandarización de equipo

### Después (con CLI)
- ✅ Chat con Copilot en VS Code
- ✅ Modificar archivos uno por uno
- ✅ **Planificar cambios grandes con `/plan`**
- ✅ **Delegar tareas con `/delegate`**
- ✅ **Estandarizar con AGENTS.md**
- ✅ **Comparar modelos con `/model`**
- ✅ **Paralelizar con `/fleet`**

## 🎓 Recursos
- [Documentación CLI](https://docs.github.com/copilot/using-github-copilot/copilot-cli)
- [Agent Skills](https://docs.github.com/copilot/customizing-copilot/agent-skills)
- [SDK Copilot](https://docs.github.com/copilot/building-copilot-extensions)

## 🆘 Solución de Problemas Comunes

### Problema 1: "You must be logged in"
```
✗ You must be logged in to send messages. Please run /login
```
**Solución:**
1. Escribe `/login` en el terminal de copilot
2. Copia el código que aparece
3. Pégalo en la página de GitHub que se abrió automáticamente
4. Autoriza y vuelve al terminal

### Problema 2: "No copilot instructions found"
```
● 💡 No copilot instructions found. Run /init
```
**Solución:**
Ya tienes el archivo `copilot-instructions.md` creado, pero la CLI no lo detecta. Esto puede pasar si:
1. No estás en el directorio correcto
2. El archivo no está en la raíz del proyecto

**Verifica:**
```bash
/cwd
# Debería mostrar: C:\Dev\GitHub\gestion_servicio

# Si no estás ahí:
/cd C:\Dev\GitHub\gestion_servicio
```

### Problema 3: La CLI se cierra sola
**Causa:** Probablemente presionaste `Ctrl+C` dos veces

**Solución:** Vuelve a abrir:
```bash
copilot
```

### Problema 4: Los comandos no funcionan
**Verifica que estás escribiendo el `/` antes del comando:**
```bash
# ✗ Incorrecto:
plan "mi tarea"

# ✓ Correcto:
/plan "mi tarea"
```

### Problema 5: "Error: Not found"
```
✗ Error: Not found
```
**Causa:** Comando mal escrito o no existe

**Solución:** Ver lista de comandos:
```bash
/help
```

### Problema 6: Quiero empezar de nuevo
**Solución:** Limpiar la conversación:
```bash
/clear
# o
/new
```

### Problema 7: No entiendo el inglés
**Solución:** 
1. Esta guía traduce todo lo importante
2. Tus prompts pueden ser en español:
   ```bash
   /plan "mi tarea en español"
   ```
3. Siempre puedes preguntarme aquí en VS Code Chat

## 🔑 Atajos de Teclado en la CLI

| Atajo | Acción |
|-------|--------|
| `Tab` | Autocompletar comando |
| `↑` `↓` | Navegar historial de comandos |
| `Ctrl + C` | Cancelar operación actual |
| `Ctrl + C` (x2) | Salir de la CLI |
| `Esc` | Cancelar selección |
| `Enter` | Confirmar/Seleccionar |
| `Shift + Enter` | Nueva línea en prompt multilínea |

## 📌 Resumen Rápido

**Para empezar HOY:**
```bash
# 1. Abrir la CLI
copilot

# 2. Hacer login (solo la primera vez)
/login

# 3. Tu primer comando
/plan "agregar campo al modelo"

# 4. Salir cuando termines
/exit
```

**Recuerda:**
- ✅ La interfaz está en inglés pero entiendes español
- ✅ Tus instrucciones pueden ser en español
- ✅ Ya tienes `copilot-instructions.md` configurado
- ✅ Siempre puedes volver a VS Code Chat (yo) si tienes dudas

## 🎯 Cheat Sheet: ¿Qué Herramienta Usar?

```
┌─────────────────────────────────────────────────────┐
│ ESCENARIO → HERRAMIENTA RECOMENDADA                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│ 💬 "No sé cómo hacer esto"                          │
│    → VS Code Chat (diseño y exploración)           │
│                                                     │
│ ⚡ "Sé qué hacer, solo hazlo rápido"                │
│    → CLI con /plan                                  │
│                                                     │
│ 🚀 "Hacer 3-4 cosas similares a la vez"             │
│    → CLI con /fleet                                 │
│                                                     │
│ 🎯 "Tarea repetitiva, no urgente"                   │
│    → CLI con /delegate                              │
│                                                     │
│ 🐛 "Hay un bug y no entiendo por qué"               │
│    → VS Code Chat (debugging interactivo)          │
│                                                     │
│ 🔍 "Quiero ver QUÉ va a cambiar antes"              │
│    → CLI con /plan (muestra esquema primero)       │
│                                                     │
│ 📚 "Necesito entender este código"                  │
│    → VS Code Chat (explicaciones)                  │
│                                                     │
│ ⚙️ "Cambio grande que afecta varios archivos"       │
│    1. VS Code Chat: diseñar                        │
│    2. CLI /plan: ejecutar                          │
│                                                     │
│ 🧪 "Necesito tests para TODO el proyecto"           │
│    → CLI con /fleet (tests paralelos)              │
│                                                     │
│ 💡 "¿Cuál es la mejor manera de hacer X?"           │
│    → VS Code Chat (comparar opciones)              │
│                                                     │
│ 📝 "Documentar todo el código con docstrings"       │
│    → CLI con /delegate (automatizar)               │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## 🔄 Workflow Híbrido Recomendado

```
       ┌─────────────────────────────────────┐
       │  INICIO: ¿Qué quiero lograr?        │
       └──────────────┬──────────────────────┘
                      │
         ┌────────────┴───────────┐
         │                        │
         ▼                        ▼
    ¿Sé cómo                 ¿Necesito
     hacerlo?                 ayuda?
         │                        │
         │ SÍ                     │ SÍ
         ▼                        ▼
    ┌─────────┐           ┌──────────────┐
    │   CLI   │           │  VS Code     │
    │         │           │  Chat (yo)   │
    │ /plan   │           │              │
    │ /fleet  │◄──────────│  Diseñamos   │
    │ /delegate│          │  Exploramos  │
    └─────────┘           │  Aprendemos  │
         │                └──────────────┘
         │                        │
         │                   ¿Listo para
         │                   implementar?
         │                        │
         │                        │ SÍ
         └────────────┬───────────┘
                      ▼
              ┌──────────────┐
              │   RESULTADO  │
              │   ✓ Código   │
              │   ✓ Tests    │
              │   ✓ Docs     │
              └──────────────┘
```

## 🎓 Próxima Vez Que Trabajes

**Pregúntate:**

1. **"¿Estoy aprendiendo o ejecutando?"**
   - Aprendiendo → VS Code Chat
   - Ejecutando → CLI

2. **"¿Es una tarea o muchas tareas?"**
   - Una tarea → `/plan`
   - Muchas tareas independientes → `/fleet`

3. **"¿Necesito revisar antes de aplicar?"**
   - Sí → `/plan` (muestra esquema)
   - No → `/delegate` (ejecuta directamente)

4. **"¿Puedo describir exactamente qué hacer?"**
   - Sí → CLI
   - No estoy seguro → VS Code Chat primero

**Ejemplo Práctico Hoy:**

```
Tú piensas: "Quiero agregar validación de email"

❓ ¿Sé qué tipo de validación usar?
   NO → VS Code Chat: "¿Qué validación de email recomiendas?"

❓ ¿Es una sola cosa o muchas?
   Una → /plan

❓ ¿Quiero ver qué va a cambiar?
   SÍ → /plan "agregar validación de email al formulario"

✅ Ejecuto en CLI:
   /plan "agregar validación de email al formulario de preinformes"
```

¡Ahora sí, a probar la CLI! 🚀
